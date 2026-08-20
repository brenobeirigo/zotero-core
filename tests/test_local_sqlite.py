"""The local SQLite layer, exercised with no Zotero installed.

Neither front-end that owned a copy of this code had a single test.
"""

from zotero_core.backends.sqlite import read_collections, read_snapshot
from zotero_core.local.attachments import resolve_attachment
from zotero_core.local.db import READ_ONLY, open_read_only
from zotero_core.local.items import fulltext_item_ids, load_items


def test_opens_read_only(zotero_db):
    connection, mode = open_read_only(zotero_db)
    try:
        assert mode == READ_ONLY
    finally:
        connection.close()


def test_loads_regular_items_only(zotero_db):
    connection, _ = open_read_only(zotero_db)
    try:
        items = load_items(connection, data_dir=zotero_db.parent)
    finally:
        connection.close()
    assert {item.key for item in items} == {"AAAA1111", "BBBB2222"}


def test_projects_the_superset_both_front_ends_need(zotero_db):
    connection, _ = open_read_only(zotero_db)
    try:
        items = {i.key: i for i in load_items(connection, data_dir=zotero_db.parent)}
    finally:
        connection.close()
    article = items["AAAA1111"]
    assert article.item_type == "journalArticle"
    assert article.title == "Dynamic Routing under Uncertainty"
    assert article.year == "2021"
    assert article.doi == "10.1287/trsc.2021.1234"
    assert article.citation_key == "doe2021routing"
    assert article.authors == ["Jane Doe"]
    assert article.tags == ["routing"]
    assert article.zotero_uri.endswith("AAAA1111")
    assert article.first_creator == "Doe"


def test_resolves_storage_attachments(zotero_db):
    connection, _ = open_read_only(zotero_db)
    try:
        items = {i.key: i for i in load_items(connection, data_dir=zotero_db.parent)}
    finally:
        connection.close()
    attachment = items["AAAA1111"].attachments[0]
    assert attachment.path.name == "paper.pdf"
    assert "storage" in attachment.path.parts
    assert attachment.exists is False


def test_linked_attachment_needs_a_root(tmp_path):
    assert resolve_attachment("attachments:a.pdf", "K", tmp_path, None) is None
    assert resolve_attachment("attachments:a.pdf", "K", tmp_path, tmp_path).name == "a.pdf"


def test_relative_path_has_no_anchor(tmp_path):
    assert resolve_attachment("a.pdf", "K", tmp_path, None) is None


def test_fulltext_index_lookup(zotero_db):
    connection, _ = open_read_only(zotero_db)
    try:
        found = fulltext_item_ids(connection, ["routing", "uncertainty"])
    finally:
        connection.close()
    assert found[1] == {"routing", "uncertainty"}


def test_collections_carry_their_parent(zotero_db):
    connection, _ = open_read_only(zotero_db)
    try:
        collections = {c.name: c for c in read_collections(connection)}
    finally:
        connection.close()
    assert collections["Project"].parent_key is None
    assert collections["stream-one"].parent_key == "COLL0001"


def test_snapshot_from_sqlite_carries_collection_membership(zotero_db):
    items, collections, mode = read_snapshot(zotero_db)
    assert mode == READ_ONLY
    article = next(item for item in items if item.key == "AAAA1111")
    assert article.collection_keys == ("COLL0002",)
    assert {c.name for c in collections} == {"Project", "stream-one"}


def test_venue_follows_the_item_type_not_sqlite_row_order(zotero_db):
    """A conference paper reports its proceedings title, not the event name.

    Reading the three venue fields into one column let SQLite row order pick
    the winner, so the same item could report two different venues on two
    runs. One real library item has proceedingsTitle "Computer Science in
    Cars Symposium" and conferenceName "CSCS '20: Computer Science in Cars
    Symposium"; the accident used to return the second.
    """
    from zotero_core.local.items import LocalItem

    paper = LocalItem(
        item_id=1,
        key="K",
        item_type="conferencePaper",
        proceedings_title="Computer Science in Cars Symposium",
        conference_name="CSCS '20: Computer Science in Cars Symposium",
        publication_title="A Stale Journal Name",
    )
    assert paper.venue == "Computer Science in Cars Symposium"

    article = LocalItem(
        item_id=2,
        key="K2",
        item_type="journalArticle",
        publication_title="Transportation Science",
        proceedings_title="A Stale Proceedings Name",
    )
    assert article.venue == "Transportation Science"

    assert LocalItem(item_id=3, key="K3", item_type="book").venue == ""
