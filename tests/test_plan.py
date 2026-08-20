import pytest

from zotero_core.bib.loader import load_bib_streams
from zotero_core.identity import LibraryItem
from zotero_core.plan.applier import apply_plan
from zotero_core.plan.models import (
    ADD_EXISTING,
    ALREADY_PRESENT,
    CREATE,
    NEEDS_REVIEW,
    PRESERVE_EXISTING_LEAF,
    CollectionRef,
)
from zotero_core.plan.planner import plan_import

from conftest import CORPUS, FakeBackend


def works():
    return load_bib_streams(CORPUS)


def test_plans_offline_with_no_backend_and_no_credential():
    # The property the skill's dry run always promised. It is now a property
    # of the planner, not of a stub standing in for a client.
    plan = plan_import(works(), "Project")
    assert plan.offline is True
    assert plan.ok is True
    assert plan.counts[CREATE] == plan.parsed
    assert [c.name for c in plan.collections] == ["Project", "edge-cases", "stream-one"]
    assert all(not c.exists for c in plan.collections)


def test_flat_still_assigns_a_target_collection():
    # The bug this replaces left item["collections"] unset under --flat, so
    # items landed loose in the library root.
    plan = plan_import(works(), "Project", flat=True)
    assert [c.name for c in plan.collections] == ["Project"]
    assert {row.target_collection for row in plan.rows} == {"Project"}


def test_existing_item_in_the_target_is_already_present():
    parent = CollectionRef(name="Project", key="P")
    stream = CollectionRef(name="stream-one", key="S", parent_key="P")
    snapshot = [
        LibraryItem(key="I1", doi="10.1287/trsc.2021.1234", collection_keys=("S",))
    ]
    plan = plan_import(
        works(), "Project", snapshot=snapshot, collections=[parent, stream]
    )
    row = next(r for r in plan.rows if r.citation_key == "doe2021routing")
    assert row.action == ALREADY_PRESENT and row.item_key == "I1"


def test_existing_item_outside_the_project_is_filed_not_duplicated():
    parent = CollectionRef(name="Project", key="P")
    stream = CollectionRef(name="stream-one", key="S", parent_key="P")
    snapshot = [LibraryItem(key="I1", doi="10.1287/trsc.2021.1234", collection_keys=("Z",))]
    plan = plan_import(works(), "Project", snapshot=snapshot, collections=[parent, stream])
    row = next(r for r in plan.rows if r.citation_key == "doe2021routing")
    assert row.action == ADD_EXISTING and row.matched_by == "doi"


def test_existing_item_in_another_project_leaf_is_preserved():
    parent = CollectionRef(name="Project", key="P")
    stream = CollectionRef(name="stream-one", key="S", parent_key="P")
    other = CollectionRef(name="other-stream", key="O", parent_key="P")
    snapshot = [LibraryItem(key="I1", doi="10.1287/trsc.2021.1234", collection_keys=("O",))]
    plan = plan_import(
        works(), "Project", snapshot=snapshot, collections=[parent, stream, other]
    )
    row = next(r for r in plan.rows if r.citation_key == "doe2021routing")
    assert row.action == PRESERVE_EXISTING_LEAF
    assert row.existing_project_collections == ["other-stream"]


def test_ambiguous_match_becomes_a_conflict_not_a_write():
    snapshot = [
        LibraryItem(key="I1", doi="10.1287/trsc.2021.1234"),
        LibraryItem(key="I2", doi="10.1287/trsc.2021.1234"),
    ]
    plan = plan_import(works(), "Project", snapshot=snapshot, collections=[])
    assert plan.ok is False
    assert plan.conflicts[0].reason == "ambiguous-global-match"
    with pytest.raises(ValueError, match="unresolved conflict"):
        apply_plan(plan, FakeBackend())


def test_low_confidence_match_needs_review():
    snapshot = [LibraryItem(key="I1", title="Our Locations", year="", first_creator="International Maritime Organization")]
    plan = plan_import(works(), "Project", snapshot=snapshot, collections=[])
    row = next(r for r in plan.rows if r.citation_key == "imo2023locations")
    assert row.action == NEEDS_REVIEW and "by hand" in row.note


def test_require_parent_refuses_a_missing_project():
    with pytest.raises(ValueError, match="Parent collection not found"):
        plan_import(works(), "Nope", snapshot=[], collections=[], require_parent=True)


def test_duplicate_sibling_collections_are_refused():
    from zotero_core.errors import AmbiguousMatch

    collections = [
        CollectionRef(name="Project", key="P"),
        CollectionRef(name="stream-one", key="S1", parent_key="P"),
        CollectionRef(name="stream-one", key="S2", parent_key="P"),
    ]
    with pytest.raises(AmbiguousMatch, match="Duplicate child collections"):
        plan_import(works(), "Project", snapshot=[], collections=collections)


def test_offline_plan_may_not_be_applied():
    plan = plan_import(works(), "Project")
    with pytest.raises(ValueError, match="computed offline"):
        apply_plan(plan, FakeBackend())


def _apply_once(backend):
    plan = plan_import(works(), "Project", backend=backend)
    return apply_plan(plan, backend)


def test_apply_creates_collections_and_items():
    backend = FakeBackend()
    plan = _apply_once(backend)
    assert plan.applied is True
    assert len(backend.created) == plan.parsed
    assert all(target for _, target in backend.created)
    assert all(row.item_key for row in plan.rows)


def test_rerunning_after_a_stream_rename_creates_nothing(tmp_path):
    # The failure this proves fixed: dedup used to be scoped to the target
    # sub-collection, so renaming a stream file re-imported the whole
    # bibliography as duplicates.
    backend = FakeBackend()
    first = plan_import(works(), "Project", backend=backend)
    apply_plan(first, backend)

    by_name = {c.name: c for c in first.collections}
    for row, (payload, target) in zip(
        [r for r in first.rows], backend.created
    ):
        backend._items.append(
            LibraryItem(
                key=row.item_key,
                title=payload["title"],
                year=payload["year"],
                doi=payload["doi"],
                first_creator=payload["matchCreator"],
                citation_key=payload["citationKey"],
                collection_keys=(target,),
            )
        )

    renamed = tmp_path / "renamed"
    renamed.mkdir()
    for source in sorted(CORPUS.glob("*.bib")):
        if source.stem == "uncited-backup":
            continue
        (renamed / f"renamed-{source.name}").write_text(
            source.read_text(encoding="utf-8"), encoding="utf-8"
        )

    second = plan_import(load_bib_streams(renamed), "Project", backend=backend)
    assert second.counts[CREATE] == 0
    assert by_name  # the original collections are still what was created
