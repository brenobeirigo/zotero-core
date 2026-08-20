import pytest

from zotero_core.identity import (
    CITEKEY,
    DOI,
    TITLE_YEAR,
    TITLE_YEAR_CREATOR,
    LibraryIndex,
    LibraryItem,
    citation_key_from_extra,
    format_citation_key,
    identity_slug,
    match_work,
    normalize_doi,
    normalize_title,
    parse_year,
    rules_for,
)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("10.1287/TRSC.2021.1", "10.1287/trsc.2021.1"),
        ("https://doi.org/10.1287/trsc.2021.1", "10.1287/trsc.2021.1"),
        ("https://dx.doi.org/10.1287/trsc.2021.1", "10.1287/trsc.2021.1"),
        ("doi: 10.1287/trsc.2021.1", "10.1287/trsc.2021.1"),
        (None, ""),
    ],
)
def test_normalize_doi(raw, expected):
    assert normalize_doi(raw) == expected


def test_normalize_title_folds_accents():
    # The desktop route compares these against JS-normalized library items,
    # where NFKD has already stripped the umlaut. Disagreeing here is a
    # silent dedup miss that writes a real duplicate.
    assert normalize_title("Zurich") == normalize_title("Zürich")


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Dynamic Routing: Under Uncertainty!", "dynamic routing under uncertainty"),
        ("a_b", "a b"),
        ("", ""),
    ],
)
def test_normalize_title(raw, expected):
    assert normalize_title(raw) == expected


def test_identity_slug_drops_spaces():
    assert identity_slug("Dynamic Routing") == "dynamicrouting"


@pytest.mark.parametrize(
    "raw,expected", [("2021-06-01", "2021"), ("n.d.", ""), ("", ""), (None, "")]
)
def test_parse_year(raw, expected):
    assert parse_year(raw) == expected


def test_citation_key_requires_its_own_line():
    # The unanchored pattern this replaces reads "unknown" out of this note.
    assert citation_key_from_extra("no Citation Key: unknown") == ""
    assert citation_key_from_extra("Citation Key: doe2021\nPMID: 7") == "doe2021"
    assert citation_key_from_extra("citation key: doe2021") == "doe2021"


def test_format_citation_key_is_unchanged():
    assert format_citation_key("doe2021") == "Citation Key: doe2021"


def test_rules_skip_title_heuristics_when_a_doi_is_present():
    # A DOI is authoritative: matching a DOI-bearing entry to a differently
    # identified item by title is a guess, and it has always been refused.
    assert rules_for("10.1/x", "doe2021", "Doe") == [DOI, CITEKEY]
    assert rules_for("", "doe2021", "Doe") == [CITEKEY, TITLE_YEAR_CREATOR]
    assert rules_for("", "", "") == [TITLE_YEAR]


def _index():
    return LibraryIndex(
        [
            LibraryItem(key="A", title="Dynamic Routing", year="2021",
                        doi="10.1287/trsc.1", first_creator="Doe",
                        citation_key="doe2021"),
            LibraryItem(key="B", title="Untitled Report", year="",
                        first_creator="Lab", citation_key="lab2020"),
        ]
    )


def test_match_by_doi():
    result = match_work(doi="https://doi.org/10.1287/TRSC.1", index=_index())
    assert result.rule == DOI and result.item.key == "A"


def test_match_by_citekey_is_library_wide():
    # The bug this replaces scoped the citation-key check to one target
    # collection, so renaming a stream re-imported the whole bibliography.
    result = match_work(citekey="doe2021", index=_index())
    assert result.rule == CITEKEY and result.item.key == "A"


def test_match_by_title_year_creator():
    result = match_work(title="dynamic  routing", year="2021", creator="Doe", index=_index())
    assert result.rule == TITLE_YEAR_CREATOR and result.item.key == "A"


def test_match_without_year_is_low_confidence():
    result = match_work(title="Untitled Report", year="", creator="Lab", index=_index())
    assert result.rule == TITLE_YEAR_CREATOR
    assert result.low_confidence is True


def test_ambiguous_match_is_reported_not_resolved():
    index = LibraryIndex(
        [
            LibraryItem(key="A", title="Same Title", year="2021", first_creator="Doe"),
            LibraryItem(key="B", title="Same Title", year="2021", first_creator="Doe"),
        ]
    )
    result = match_work(title="Same Title", year="2021", creator="Doe", index=index)
    assert result.ambiguous is True and result.item is None


def test_no_match_returns_no_rule():
    assert match_work(doi="10.9999/nope", index=_index()).rule is None
