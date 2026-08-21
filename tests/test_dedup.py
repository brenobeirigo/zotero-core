import pytest

from zotero_core.dedup import (
    MERGE,
    REVIEW,
    SKIP,
    TRASH,
    MergePlan,
    apply_merge_plan,
    choose_master,
    find_duplicates,
    review_backlog,
)
from zotero_core.identity import CITEKEY, DOI, TITLE_YEAR, TITLE_YEAR_CREATOR, LibraryItem

from conftest import FakeBackend


def item(key, **fields):
    return LibraryItem(key=key, **fields)


# The library this repair path was written for: one conference paper imported
# three times on the same day, before global dedup existed. All three carry
# the same DOI, so no heuristic is needed to know they are one work.
ASYMTRE = [
    item(
        "B7WKDLMX",
        title="ASyMTRe: Automated Synthesis of Multi-Robot Task Solutions",
        year="2005",
        doi="10.1109/ROBOT.2005.1570327",
        first_creator="Tang",
        citation_key="tang2005asymtre",
        collection_keys=("INTERACT1",),
    ),
    item(
        "AMV7KCYM",
        title="ASyMTRe: Automated Synthesis of Multi-Robot Task Solutions",
        year="2005",
        doi="10.1109/ROBOT.2005.1570327",
        first_creator="Tang",
    ),
    item(
        "N8Y8RF82",
        title="ASyMTRe: Automated Synthesis of Multi-Robot Task Solutions",
        year="2005",
        doi="10.1109/ROBOT.2005.1570327",
        first_creator="Tang",
        collection_keys=("COALITION1",),
    ),
]


def test_groups_three_copies_of_one_doi_and_marks_them_mergeable():
    plan = find_duplicates(ASYMTRE)

    assert len(plan.groups) == 1
    group = plan.groups[0]
    assert group.rule == DOI
    assert group.action == MERGE
    assert sorted(group.keys) == ["AMV7KCYM", "B7WKDLMX", "N8Y8RF82"]
    assert plan.items_removed == 2


def test_master_is_the_copy_a_bib_file_points_at():
    # Losing the item that owns the citation key would break every document
    # citing it, so the citation key outranks everything else.
    assert choose_master(ASYMTRE).key == "B7WKDLMX"


def test_master_prefers_a_doi_then_collections_then_a_stable_key():
    no_citekeys = [
        item("ZZZZ0001", title="A", year="2020"),
        item("AAAA0002", title="A", year="2020", collection_keys=("C1", "C2")),
        item("MMMM0003", title="A", year="2020", doi="10.1/x"),
    ]
    assert choose_master(no_citekeys).key == "MMMM0003"

    without_doi = [row for row in no_citekeys if not row.doi]
    assert choose_master(without_doi).key == "AAAA0002"

    tied = [item("ZZZZ0001", title="A", year="2020"), item("AAAA0002", title="A", year="2020")]
    assert choose_master(tied).key == "AAAA0002"
    assert choose_master(list(reversed(tied))).key == "AAAA0002"


def test_a_title_match_is_never_merged_without_a_person_looking():
    # Two different papers can share a title and a year; an erratum shares
    # both with the article it corrects.
    plan = find_duplicates(
        [
            item("K1", title="Robust optimization", year="2011", first_creator="Bertsimas"),
            item("K2", title="Robust Optimization", year="2011", first_creator="Bertsimas"),
        ]
    )
    assert plan.groups[0].rule == TITLE_YEAR_CREATOR
    assert plan.groups[0].action == REVIEW
    assert plan.items_removed == 0


def test_a_strong_rule_claims_an_item_before_a_weak_one_can():
    items = [
        item("D1", title="Same Title", year="2020", doi="10.1/a", first_creator="Ng"),
        item("D2", title="Same Title", year="2020", doi="10.1/a", first_creator="Ng"),
        item("T3", title="Same Title", year="2020", first_creator="Ng"),
    ]
    plan = find_duplicates(items)

    doi_groups = [g for g in plan.groups if g.rule == DOI]
    assert len(doi_groups) == 1
    assert sorted(doi_groups[0].keys) == ["D1", "D2"]
    # T3 is left ungrouped rather than folded into the DOI pair by its title.
    assert all("T3" not in group.keys for group in doi_groups)
    assert not [g for g in plan.groups if g.rule in (TITLE_YEAR, TITLE_YEAR_CREATOR)]


def test_a_citation_key_groups_items_that_have_no_doi():
    plan = find_duplicates(
        [
            item("C1", title="One", year="2019", citation_key="ng2019one"),
            item("C2", title="Another Spelling", year="2019", citation_key="ng2019one"),
        ]
    )
    assert plan.groups[0].rule == CITEKEY
    assert plan.groups[0].action == MERGE


def test_a_single_copy_is_not_a_group():
    plan = find_duplicates([item("S1", title="Alone", year="2020", doi="10.1/z")])
    assert plan.groups == []
    assert plan.library_size == 1


def test_items_with_no_identity_at_all_are_left_alone():
    plan = find_duplicates([item("N1"), item("N2")])
    assert plan.groups == []


def test_apply_merges_into_the_master_and_leaves_review_groups_untouched():
    plan = find_duplicates(ASYMTRE)
    plan.groups.append(
        find_duplicates(
            [
                item("R1", title="Maybe Same", year="2020", first_creator="Lee"),
                item("R2", title="Maybe same", year="2020", first_creator="Lee"),
            ]
        ).groups[0]
    )
    backend = FakeBackend()

    apply_merge_plan(plan, backend)

    assert backend.merged == [("B7WKDLMX", ["AMV7KCYM", "N8Y8RF82"])]
    assert backend.trashed == []
    assert plan.applied is True
    assert [g.keys for g in review_backlog(plan)] == [["R1", "R2"]]


def test_apply_trashes_a_group_marked_trash_without_merging_it():
    plan = find_duplicates(
        [
            item("E1", title="EBSCO", year="2026"),
            item("E2", title="EBSCO", year="2026"),
        ]
    )
    plan.groups[0].action = TRASH
    backend = FakeBackend()

    apply_merge_plan(plan, backend)

    assert backend.trashed == ["E1", "E2"]
    assert backend.merged == []


def test_apply_writes_nothing_for_a_skipped_group():
    plan = find_duplicates(ASYMTRE)
    plan.groups[0].action = SKIP
    backend = FakeBackend()

    apply_merge_plan(plan, backend)

    assert backend.merged == []
    assert backend.trashed == []


def test_a_master_outside_its_own_group_is_refused():
    plan = find_duplicates(ASYMTRE)
    plan.groups[0].master_key = "SOMETHINGELSE"
    with pytest.raises(ValueError, match="not one of the items"):
        apply_merge_plan(plan, FakeBackend())


def test_a_merge_with_no_master_is_refused():
    plan = find_duplicates(ASYMTRE)
    plan.groups[0].master_key = None
    with pytest.raises(ValueError, match="merge with no master"):
        apply_merge_plan(plan, FakeBackend())


def test_an_unknown_action_is_refused_rather_than_ignored():
    plan = find_duplicates(ASYMTRE)
    plan.groups[0].action = "delete-forever"
    with pytest.raises(ValueError, match="Unknown action"):
        apply_merge_plan(plan, FakeBackend())


def test_one_item_in_two_groups_is_refused():
    # Only reachable through a hand-edited plan, which is exactly why it is
    # checked: folding both groups would merge two unrelated works.
    plan = find_duplicates(ASYMTRE)
    plan.groups.append(
        find_duplicates(
            [
                item("N8Y8RF82", title="Other", year="1999", citation_key="k"),
                item("XX", title="Other", year="1999", citation_key="k"),
            ]
        ).groups[0]
    )
    with pytest.raises(ValueError, match="appears in two groups"):
        apply_merge_plan(plan, FakeBackend())


def test_a_hand_edited_plan_round_trips_through_json():
    original = find_duplicates(ASYMTRE)
    restored = MergePlan.from_dict(original.to_dict())

    assert restored.to_dict() == original.to_dict()
    assert restored.groups[0].master_key == "B7WKDLMX"
    assert restored.groups[0].items[0].collection_keys == ("INTERACT1",)

    backend = FakeBackend()
    apply_merge_plan(restored, backend)
    assert backend.merged == [("B7WKDLMX", ["AMV7KCYM", "N8Y8RF82"])]


def test_counts_report_what_an_apply_would_and_would_not_do():
    plan = find_duplicates(ASYMTRE + [item("R1", title="X", year="2020", first_creator="Lee"),
                                      item("R2", title="X", year="2020", first_creator="Lee")])
    assert plan.counts[MERGE] == 1
    assert plan.counts[REVIEW] == 1
    assert plan.items_removed == 2
