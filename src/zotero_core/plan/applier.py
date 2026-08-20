"""Execute an approved plan through a backend."""

from __future__ import annotations

from .models import ADD_EXISTING, CREATE, ImportPlan


def apply_plan(plan: ImportPlan, backend) -> ImportPlan:
    """Create the missing collections, then the items, then file the rest.

    Refuses to write anything while the plan holds a conflict: an ambiguous
    global match is exactly the case where guessing produces a duplicate in a
    real library.
    """
    if not plan.ok:
        raise ValueError(
            f"Refusing to apply a plan with {len(plan.conflicts)} unresolved conflict(s)"
        )
    if plan.offline:
        raise ValueError("Refusing to apply a plan computed offline; re-plan against a backend")

    for collection in plan.collections:
        if collection.key is None:
            collection.key = backend.ensure_collection(collection.name, collection.parent_key)
            if collection.parent_key is None and collection.name == plan.parent_name:
                plan.parent_key = collection.key
                for child in plan.collections:
                    if child is not collection and child.parent_key is None:
                        child.parent_key = collection.key
    # A child created before its parent had a key needs a second pass.
    for collection in plan.collections:
        if collection.key is None:
            collection.key = backend.ensure_collection(collection.name, collection.parent_key)

    by_name = {collection.name: collection for collection in plan.collections}

    pending: list[tuple] = []
    for row in plan.rows:
        target = by_name.get(row.target_collection)
        if target is None or target.key is None:
            continue
        if row.action == ADD_EXISTING and row.item_key:
            backend.add_to_collection(row.item_key, target.key)
        elif row.action == CREATE and row.work is not None:
            pending.append((row, target.key))

    if pending:
        payloads = [
            (row.work.to_payload(), target_key) for row, target_key in pending
        ]
        keys = backend.create_items(payloads)
        for (row, _), key in zip(pending, keys):
            row.item_key = key

    plan.applied = True
    return plan
