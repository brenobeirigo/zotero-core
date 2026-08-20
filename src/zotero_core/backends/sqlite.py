"""A read-only snapshot source backed by Zotero's local SQLite database.

This is the concrete payoff of keeping all four routes in one package: an
import can be planned against the real library without the CLI Bridge, without
an API key, and without a full-library dump over HTTP. It is a *snapshot*
source, not a backend -- it cannot write, and it never pretends it can.
"""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from pathlib import Path

from ..errors import ZoteroCoreError
from ..identity import LibraryItem
from ..local.datadir import find_data_dir
from ..local.db import open_read_only
from ..local.items import load_items
from ..plan.models import CollectionRef


def _item_collection_keys(connection: sqlite3.Connection) -> dict[int, list[str]]:
    keys: dict[int, list[str]] = defaultdict(list)
    for item_id, key in connection.execute(
        """
        SELECT ci.itemID, c.key
        FROM collectionItems ci JOIN collections c ON c.collectionID = ci.collectionID
        """
    ):
        keys[item_id].append(key)
    return keys


def read_collections(connection: sqlite3.Connection) -> list[CollectionRef]:
    rows = list(
        connection.execute(
            "SELECT collectionID, key, collectionName, parentCollectionID FROM collections"
        )
    )
    by_id = {collection_id: key for collection_id, key, _, _ in rows}
    return [
        CollectionRef(
            name=name,
            key=key,
            parent_key=by_id.get(parent_id) if parent_id else None,
        )
        for _, key, name, parent_id in rows
    ]


def read_snapshot(
    database: str | Path | None = None,
) -> tuple[list[LibraryItem], list[CollectionRef], str]:
    """Return ``(items, collections, database_mode)`` from the local database."""
    if database is None:
        data_dir = find_data_dir()
        if data_dir is None:
            raise ZoteroCoreError(
                "Could not locate the Zotero data directory; pass an explicit "
                "path to zotero.sqlite."
            )
        database = data_dir / "zotero.sqlite"
    connection, mode = open_read_only(database)
    try:
        collection_keys = _item_collection_keys(connection)
        items = [
            LibraryItem(
                key=item.key,
                title=item.title,
                year=item.year,
                doi=item.doi,
                first_creator=item.first_creator,
                citation_key=item.citation_key,
                collection_keys=tuple(collection_keys.get(item.item_id, ())),
            )
            for item in load_items(
                connection, with_attachments=False, with_tags=False
            )
        ]
        return items, read_collections(connection), mode
    finally:
        connection.close()
