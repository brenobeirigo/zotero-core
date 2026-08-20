import pytest

from zotero_core.bib.types import TYPE_MAP, check_required, resolve_item_type
from zotero_core.errors import IncompleteEntry, UnsupportedEntryType


def test_misc_with_an_eprint_is_a_preprint():
    entry = {"ENTRYTYPE": "misc", "ID": "x", "eprint": "2201.01", "archiveprefix": "arXiv"}
    assert resolve_item_type(entry) == ("preprint", "misc-eprint")


def test_misc_with_a_bare_url_is_a_webpage():
    entry = {"ENTRYTYPE": "misc", "ID": "x", "url": "https://example.org"}
    assert resolve_item_type(entry) == ("webpage", "misc-url")


def test_misc_with_a_url_and_a_venue_is_not_a_webpage():
    entry = {"ENTRYTYPE": "misc", "ID": "x", "url": "https://example.org",
             "journal": "Transportation Science"}
    assert resolve_item_type(entry) == ("document", "misc-fallback")


def test_bare_misc_falls_back_to_document():
    assert resolve_item_type({"ENTRYTYPE": "misc", "ID": "x"}) == ("document", "misc-fallback")


def test_strict_types_refuses_to_guess():
    with pytest.raises(UnsupportedEntryType):
        resolve_item_type({"ENTRYTYPE": "misc", "ID": "x"}, strict=True)


def test_strict_types_still_accepts_evidence():
    entry = {"ENTRYTYPE": "misc", "ID": "x", "url": "https://example.org"}
    assert resolve_item_type(entry, strict=True)[0] == "webpage"


@pytest.mark.parametrize(
    "entry_type,item_type",
    [
        ("article", "journalArticle"),
        ("inproceedings", "conferencePaper"),
        ("incollection", "bookSection"),
        ("bachelorthesis", "thesis"),
        ("thesis", "thesis"),
        ("report", "report"),
        ("techreport", "report"),
        ("online", "webpage"),
    ],
)
def test_type_map_is_the_union_of_both_tables(entry_type, item_type):
    assert TYPE_MAP[entry_type] == item_type


def test_unknown_entry_type_is_refused():
    with pytest.raises(UnsupportedEntryType):
        resolve_item_type({"ENTRYTYPE": "sonnet", "ID": "x"})


def test_a_webpage_may_have_no_year():
    check_required("webpage", "x", "Our Locations", "")


def test_a_journal_article_may_not():
    with pytest.raises(IncompleteEntry):
        check_required("journalArticle", "x", "A Paper", "")


def test_a_title_is_always_required():
    with pytest.raises(IncompleteEntry):
        check_required("webpage", "x", "", "2020")
