"""Fixtures. Nothing here touches a real Zotero, a network, or a credential."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

CORPUS = Path(__file__).parent / "corpus"

_SCHEMA = """
CREATE TABLE itemTypes (itemTypeID INTEGER PRIMARY KEY, typeName TEXT);
CREATE TABLE fields (fieldID INTEGER PRIMARY KEY, fieldName TEXT);
CREATE TABLE itemDataValues (valueID INTEGER PRIMARY KEY, value TEXT);
CREATE TABLE items (itemID INTEGER PRIMARY KEY, key TEXT, itemTypeID INTEGER);
CREATE TABLE itemData (itemID INTEGER, fieldID INTEGER, valueID INTEGER);
CREATE TABLE creators (creatorID INTEGER PRIMARY KEY, firstName TEXT, lastName TEXT);
CREATE TABLE itemCreators (itemID INTEGER, creatorID INTEGER, orderIndex INTEGER);
CREATE TABLE tags (tagID INTEGER PRIMARY KEY, name TEXT);
CREATE TABLE itemTags (itemID INTEGER, tagID INTEGER);
CREATE TABLE itemAttachments (
    itemID INTEGER, parentItemID INTEGER, path TEXT, contentType TEXT
);
CREATE TABLE collections (
    collectionID INTEGER PRIMARY KEY, key TEXT, collectionName TEXT,
    parentCollectionID INTEGER
);
CREATE TABLE collectionItems (collectionID INTEGER, itemID INTEGER);
CREATE TABLE fulltextWords (wordID INTEGER PRIMARY KEY, word TEXT);
CREATE TABLE fulltextItemWords (wordID INTEGER, itemID INTEGER);
"""

_TYPES = ["journalArticle", "webpage", "attachment", "note"]
_FIELDS = [
    "title", "date", "DOI", "url", "extra", "abstractNote",
    "publicationTitle", "proceedingsTitle", "conferenceName",
]


@pytest.fixture
def zotero_db(tmp_path: Path) -> Path:
    """A synthetic zotero.sqlite holding two items, a collection, and an attachment."""
    database = tmp_path / "zotero.sqlite"
    connection = sqlite3.connect(database)
    connection.executescript(_SCHEMA)
    connection.executemany(
        "INSERT INTO itemTypes VALUES (?, ?)", list(enumerate(_TYPES, start=1))
    )
    connection.executemany(
        "INSERT INTO fields VALUES (?, ?)", list(enumerate(_FIELDS, start=1))
    )
    field_id = {name: index for index, name in enumerate(_FIELDS, start=1)}

    connection.execute("INSERT INTO items VALUES (1, 'AAAA1111', 1)")
    connection.execute("INSERT INTO items VALUES (2, 'BBBB2222', 2)")
    connection.execute("INSERT INTO items VALUES (3, 'CCCC3333', 3)")

    values = {
        (1, "title"): "Dynamic Routing under Uncertainty",
        (1, "date"): "2021-06-01",
        (1, "DOI"): "10.1287/trsc.2021.1234",
        (1, "extra"): "Citation Key: doe2021routing",
        (2, "title"): "Mobility Patterns in Zurich",
        (2, "date"): "2018",
        (2, "url"): "https://example.org/zurich",
    }
    value_id = 0
    for (item_id, name), value in values.items():
        value_id += 1
        connection.execute("INSERT INTO itemDataValues VALUES (?, ?)", (value_id, value))
        connection.execute(
            "INSERT INTO itemData VALUES (?, ?, ?)", (item_id, field_id[name], value_id)
        )

    connection.execute("INSERT INTO creators VALUES (1, 'Jane', 'Doe')")
    connection.execute("INSERT INTO itemCreators VALUES (1, 1, 0)")
    connection.execute("INSERT INTO tags VALUES (1, 'routing')")
    connection.execute("INSERT INTO itemTags VALUES (1, 1)")
    connection.execute(
        "INSERT INTO itemAttachments VALUES (3, 1, 'storage:paper.pdf', 'application/pdf')"
    )
    connection.execute("INSERT INTO collections VALUES (10, 'COLL0001', 'Project', NULL)")
    connection.execute("INSERT INTO collections VALUES (11, 'COLL0002', 'stream-one', 10)")
    connection.execute("INSERT INTO collectionItems VALUES (11, 1)")
    connection.executemany(
        "INSERT INTO fulltextWords VALUES (?, ?)", [(1, "routing"), (2, "uncertainty")]
    )
    connection.executemany("INSERT INTO fulltextItemWords VALUES (?, ?)", [(1, 3), (2, 3)])
    connection.commit()
    connection.close()
    return database


class FakeBackend:
    """An in-memory backend. Records writes; never leaves the process."""

    name = "fake"

    def __init__(self, items=None, collections=None):
        self._items = list(items or [])
        self._collections = list(collections or [])
        self.created: list[tuple[dict, str]] = []
        self.filed: list[tuple[str, str]] = []
        self._next = 0

    def snapshot_library(self):
        return list(self._items)

    def list_collections(self):
        return list(self._collections)

    def ensure_collection(self, name, parent_key):
        from zotero_core.plan.models import CollectionRef

        for collection in self._collections:
            if collection.name == name and collection.parent_key == parent_key:
                return collection.key
        self._next += 1
        key = f"NEWCOLL{self._next}"
        self._collections.append(CollectionRef(name=name, key=key, parent_key=parent_key))
        return key

    def create_items(self, payloads):
        keys = []
        for work, target in payloads:
            self._next += 1
            key = f"NEWITEM{self._next}"
            self.created.append((work, target))
            keys.append(key)
        return keys

    def add_to_collection(self, item_key, collection_key):
        self.filed.append((item_key, collection_key))


@pytest.fixture
def fake_backend():
    return FakeBackend
