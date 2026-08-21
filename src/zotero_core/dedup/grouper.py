"""Find the works a library holds more than once.

This walks the same match ladder the importer walks, so a group found here is
a group the importer would also have refused to duplicate. Running the two
against one library can therefore never disagree about what "the same work"
means -- which is the whole reason identity lives in one module.
"""

from __future__ import annotations

from ..identity import (
    CITEKEY,
    DOI,
    MATCH_RULES,
    TITLE_YEAR,
    TITLE_YEAR_CREATOR,
    LibraryItem,
    identity_slug,
    normalize_doi,
)
from .models import MERGE, REVIEW, DuplicateGroup, MergePlan

#: Rules whose groups may be merged without a person looking first. A DOI or a
#: user-assigned citation key identifies a work; a title does not. Two papers
#: can share a title, an erratum shares its title with the article it corrects,
#: and a book and its review often share both title and year.
CONFIDENT_RULES = (DOI, CITEKEY)

_RULE_REASON = {
    DOI: "same DOI",
    CITEKEY: "same citation key",
    TITLE_YEAR_CREATOR: "same title, year and first creator, and no DOI to confirm it",
    TITLE_YEAR: "same title and year, with no creator or DOI to confirm it",
}


def _identity_for(rule: str, item: LibraryItem) -> str:
    """The value that makes this item a member of a group under ``rule``."""
    if rule == DOI:
        return normalize_doi(item.doi)
    if rule == CITEKEY:
        return item.citation_key
    slug = identity_slug(item.title)
    if not slug or not item.year:
        return ""
    if rule == TITLE_YEAR_CREATOR:
        creator = identity_slug(item.first_creator)
        return f"{slug}|{item.year}|{creator}" if creator else ""
    return f"{slug}|{item.year}"


def choose_master(items: list[LibraryItem]) -> LibraryItem:
    """Pick the item the others should fold into.

    The order is about what would break if the item disappeared, strongest
    first: a citation key is written down in someone's .bib file and breaks a
    document when it moves; a DOI is how every other tool will find the item
    again; collection membership is where a person put it by hand. The key
    itself is the final tiebreak only so that two runs over an unchanged
    library always choose the same master.
    """
    return sorted(
        items,
        key=lambda item: (
            0 if item.citation_key else 1,
            0 if normalize_doi(item.doi) else 1,
            -len(item.collection_keys),
            item.key,
        ),
    )[0]


def find_duplicates(
    items: list[LibraryItem],
    *,
    confident_rules: tuple[str, ...] = CONFIDENT_RULES,
) -> MergePlan:
    """Group a library snapshot into duplicate sets, strongest rule first.

    An item joins at most one group. Because the rules are walked in
    confidence order, an item that a DOI already grouped is never regrouped by
    its title -- so a weak rule can widen the search but can never override a
    strong one's answer.
    """
    plan = MergePlan(library_size=len(items))
    claimed: set[str] = set()

    for rule in MATCH_RULES:
        buckets: dict[str, list[LibraryItem]] = {}
        for item in items:
            if item.key in claimed:
                continue
            identity = _identity_for(rule, item)
            if not identity:
                continue
            buckets.setdefault(identity, []).append(item)

        for identity, members in buckets.items():
            if len(members) < 2:
                continue
            confident = rule in confident_rules
            group = DuplicateGroup(
                rule=rule,
                identity=identity,
                items=members,
                action=MERGE if confident else REVIEW,
                master_key=choose_master(members).key,
                reason=_RULE_REASON.get(rule, rule),
            )
            plan.groups.append(group)
            claimed.update(group.keys)

    plan.groups.sort(key=lambda g: (MATCH_RULES.index(g.rule), -len(g.items), g.identity))
    return plan
