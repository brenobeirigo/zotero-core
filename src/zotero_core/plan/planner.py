"""Compute an import plan in pure Python, for every backend.

This is the change that made a shared core possible. The desktop route used to
decide the whole plan inside a JS blob running in Zotero, and the Web API route
decided its own in Python; the two could not share a line. Now both hand over a
library snapshot and get the same plan object back, and a snapshot can come
from the bridge, the Web API, or the read-only SQLite database.
"""

from __future__ import annotations

from ..bib.models import Work
from ..errors import AmbiguousMatch
from ..identity import LibraryIndex, LibraryItem, match_work
from .models import (
    ADD_EXISTING,
    ALREADY_PRESENT,
    CREATE,
    NEEDS_REVIEW,
    PRESERVE_EXISTING_LEAF,
    CollectionRef,
    Conflict,
    ImportPlan,
    PlanRow,
)


def _collection_tree(
    collections: list[CollectionRef], parent_name: str
) -> tuple[CollectionRef | None, set[str], dict[str, CollectionRef]]:
    """Return the project collection, its descendant keys, and its children by name."""
    parent = next(
        (c for c in collections if c.name == parent_name and c.parent_key is None), None
    )
    if parent is None or parent.key is None:
        return None, set(), {}

    descendants: set[str] = set()
    frontier = [parent.key]
    while frontier:
        current = frontier.pop(0)
        for collection in collections:
            if collection.parent_key == current and collection.key not in descendants:
                if collection.key is None:
                    continue
                descendants.add(collection.key)
                frontier.append(collection.key)

    children: dict[str, CollectionRef] = {}
    for collection in collections:
        if collection.parent_key != parent.key:
            continue
        if collection.name in children:
            raise AmbiguousMatch(
                f"Duplicate child collections under project {parent_name!r}: {collection.name}"
            )
        children[collection.name] = collection
    return parent, descendants, children


def plan_import(
    works: list[Work],
    parent_name: str,
    *,
    backend=None,
    snapshot: list[LibraryItem] | None = None,
    collections: list[CollectionRef] | None = None,
    flat: bool = False,
    require_parent: bool = False,
) -> ImportPlan:
    """Decide what an import would do, writing nothing.

    With ``backend=None`` and no snapshot this plans against an empty library:
    a complete, reviewable plan with no credential, no network, and no Zotero
    installed. That offline property is what the skill's dry run has always
    promised, and it is now a property of the planner rather than of a stub
    object standing in for a client.
    """
    offline = backend is None and snapshot is None
    if snapshot is None:
        snapshot = backend.snapshot_library() if backend is not None else []
    if collections is None:
        collections = backend.list_collections() if backend is not None else []

    index = LibraryIndex(snapshot)
    parent, descendants, children = _collection_tree(collections, parent_name)
    if parent is None and require_parent:
        raise ValueError(f"Parent collection not found: {parent_name}")

    parent_ref = parent or CollectionRef(name=parent_name)
    plan = ImportPlan(
        parent_name=parent_name,
        parent_key=parent_ref.key,
        parsed=len(works),
        offline=offline,
    )

    stream_names = sorted({work.stream for work in works if work.stream}) if not flat else []
    targets: dict[str, CollectionRef] = {}
    for name in stream_names:
        targets[name] = children.get(name) or CollectionRef(name=name, parent_key=parent_ref.key)
    plan.collections = [parent_ref] + [targets[name] for name in stream_names]

    for work in works:
        target = parent_ref if flat or not work.stream else targets[work.stream]
        result = match_work(
            doi=work.doi,
            citekey=work.citation_key,
            title=work.title,
            year=work.year,
            creator=work.match_creator,
            index=index,
        )
        if result.ambiguous:
            plan.conflicts.append(
                Conflict(
                    citation_key=work.citation_key,
                    title=work.title,
                    reason="ambiguous-global-match",
                    item_keys=[item.key for item in result.items],
                )
            )
            continue

        existing = result.item
        row = PlanRow(
            citation_key=work.citation_key,
            title=work.title,
            stream=work.stream,
            action=CREATE,
            item_type=work.item_type,
            item_type_reason=work.item_type_reason,
            target_collection=target.name,
            matched_by=result.rule,
            work=work,
        )

        if existing is None:
            plan.rows.append(row)
            continue

        row.item_key = existing.key
        if result.low_confidence:
            row.action = NEEDS_REVIEW
            row.note = (
                "matched on title without a year; confirm by hand before merging"
            )
            plan.rows.append(row)
            continue

        project_keys = [
            key
            for key in existing.collection_keys
            if key == parent_ref.key or key in descendants
        ]
        other_leaves = [key for key in project_keys if key != target.key]
        row.existing_project_collections = [
            c.name for c in collections if c.key in other_leaves and c.key != parent_ref.key
        ]
        if target.key and target.key in project_keys:
            row.action = ALREADY_PRESENT
        elif any(key != parent_ref.key for key in other_leaves):
            row.action = PRESERVE_EXISTING_LEAF
        else:
            row.action = ADD_EXISTING
        plan.rows.append(row)

    return plan
