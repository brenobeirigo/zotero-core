import pytest

from zotero_core.bib.loader import load_bib_directory, load_bib_streams

from conftest import CORPUS


def test_streams_are_keyed_by_file_stem():
    works = load_bib_streams(CORPUS)
    assert {work.stream for work in works} == {"stream-one", "edge-cases"}


def test_uncited_backup_is_skipped_by_default():
    assert all(work.stream != "uncited-backup" for work in load_bib_streams(CORPUS))


def test_uncited_backup_can_be_included():
    works = load_bib_streams(CORPUS, include_uncited=True)
    assert any(work.stream == "uncited-backup" for work in works)


def test_nonstandard_entry_types_are_parsed():
    # bibtexparser drops @bachelorthesis unless ignore_nonstandard_types is off.
    works = {work.citation_key: work for work in load_bib_streams(CORPUS)}
    assert works["muller2018zurich"].item_type == "thesis"
    assert works["muller2018zurich"].fields["thesisType"] == "Bachelor's thesis"


def test_field_mapping_is_the_union_of_both_importers():
    works = {work.citation_key: work for work in load_bib_streams(CORPUS)}
    article = works["doe2021routing"]
    assert article.fields["publicationTitle"] == "Transportation Science"
    assert article.fields["issue"] == "3"
    assert article.fields["pages"] == "1-20"  # en dash normalized
    assert article.fields["language"] == "english"
    assert works["roe2020fleets"].fields["place"] == "Delft"
    assert works["lab2020report"].fields["reportNumber"] == "TR-2020-07"
    assert works["imo2023locations"].fields["accessDate"] == "2026-08-19"
    assert works["smith2022learning"].fields["archiveID"] == "2201.01234"
    assert works["smith2022learning"].fields["repository"] == "arXiv"


def test_every_work_carries_its_type_reason():
    works = {work.citation_key: work for work in load_bib_streams(CORPUS)}
    assert works["smith2022learning"].item_type_reason == "misc-eprint"
    assert works["imo2023locations"].item_type_reason == "misc-url"
    assert works["anon2015note"].item_type_reason == "misc-fallback"
    assert works["doe2021routing"].item_type_reason == "type-map:article"


def test_citation_key_is_written_into_extra():
    works = {work.citation_key: work for work in load_bib_streams(CORPUS)}
    assert works["doe2021routing"].fields["extra"] == "Citation Key: doe2021routing"


def test_duplicate_staged_work_is_refused(tmp_path):
    entry = (
        "@article{a2021,\n title={Same Work},\n author={Doe, Jane},\n"
        " year={2021},\n doi={10.1/x}\n}\n"
    )
    (tmp_path / "one.bib").write_text(entry, encoding="utf-8")
    (tmp_path / "two.bib").write_text(entry.replace("a2021", "b2021"), encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate staged work"):
        load_bib_streams(tmp_path)


def test_empty_directory_is_refused(tmp_path):
    with pytest.raises(ValueError, match="No .bib files"):
        load_bib_streams(tmp_path)


def test_wire_shape_keeps_the_bridge_field_names():
    payload = load_bib_directory(CORPUS)[0]
    assert set(payload) >= {
        "citationKey", "stream", "itemType", "title", "year", "doi",
        "matchCreator", "fields", "creators",
    }


def test_stream_order_puts_the_argument_first():
    # A paper's streams run in the order its argument runs, which is not
    # alphabetical. Unnamed stems follow, sorted.
    works = load_bib_streams(CORPUS, stream_order=["stream-one"])
    streams = list(dict.fromkeys(work.stream for work in works))
    assert streams == ["stream-one", "edge-cases"]


def test_stream_order_may_name_a_file_that_does_not_exist_yet():
    works = load_bib_streams(CORPUS, stream_order=["not-written-yet", "stream-one"])
    assert list(dict.fromkeys(w.stream for w in works)) == ["stream-one", "edge-cases"]


def test_default_order_is_alphabetical():
    works = load_bib_streams(CORPUS)
    assert list(dict.fromkeys(w.stream for w in works)) == ["edge-cases", "stream-one"]
