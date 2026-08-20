"""Read regular items out of Zotero's SQLite database.

The two front-ends that used to own copies of this query projected different
subsets of the same rows. :class:`LocalItem` is the superset; each front-end
keeps its own small projector rather than the whole query.
"""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from ..identity import citation_key_from_extra, parse_year
from .attachments import resolve_attachment

#: Zotero item types that are not works in their own right.
NON_REGULAR = ("attachment", "note", "annotation")

_FIELD_MAP = {
    "title": "title",
    "date": "date",
    "DOI": "doi",
    "url": "url",
    "extra": "extra",
    "abstractNote": "abstract",
    "publicationTitle": "venue",
    "proceedingsTitle": "venue",
    "conferenceName": "venue",
}


@dataclass
class LocalAttachment:
    attachment_key: str
    raw_path: str
    content_type: str = ""
    path: Path | None = None

    @property
    def exists(self) -> bool:
        return bool(self.path and self.path.is_file())


@dataclass
class LocalItem:
    item_id: int
    key: str
    item_type: str = ""
    title: str = ""
    date: str = ""
    doi: str = ""
    url: str = ""
    extra: str = ""
    abstract: str = ""
    venue: str = ""
    authors: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    attachments: list[LocalAttachment] = field(default_factory=list)

    @property
    def year(self) -> str:
        return parse_year(self.date)

    @property
    def citation_key(self) -> str:
        return citation_key_from_extra(self.extra)

    @property
    def zotero_uri(self) -> str:
        return f"zotero://select/library/items/{self.key}"

    @property
    def first_creator(self) -> str:
        return self.authors[0].split()[-1] if self.authors else ""


def load_items(
    connection: sqlite3.Connection,
    *,
    data_dir: Path | None = None,
    attachment_root: Path | None = None,
    with_attachments: bool = True,
    with_tags: bool = True,
) -> list[LocalItem]:
    items: dict[int, LocalItem] = {}
    placeholders = ",".join("?" for _ in NON_REGULAR)
    rows = connection.execute(
        f"""
        SELECT i.itemID, i.key, it.typeName, f.fieldName, v.value
        FROM items i
        JOIN itemTypes it ON it.itemTypeID = i.itemTypeID
        LEFT JOIN itemData d ON d.itemID = i.itemID
        LEFT JOIN fields f ON f.fieldID = d.fieldID
        LEFT JOIN itemDataValues v ON v.valueID = d.valueID
        WHERE it.typeName NOT IN ({placeholders})
        """,
        NON_REGULAR,
    )
    for item_id, key, item_type, field_name, value in rows:
        item = items.get(item_id)
        if item is None:
            item = items[item_id] = LocalItem(item_id=item_id, key=key, item_type=item_type)
        attribute = _FIELD_MAP.get(field_name)
        if attribute and value and not getattr(item, attribute):
            setattr(item, attribute, value)

    creators: dict[int, list[str]] = defaultdict(list)
    for item_id, first, last in connection.execute(
        """
        SELECT ic.itemID, c.firstName, c.lastName
        FROM itemCreators ic JOIN creators c ON c.creatorID = ic.creatorID
        ORDER BY ic.itemID, ic.orderIndex
        """
    ):
        creators[item_id].append(" ".join(part for part in (first, last) if part))
    for item_id, names in creators.items():
        if item_id in items:
            items[item_id].authors = names

    if with_tags:
        tags: dict[int, list[str]] = defaultdict(list)
        for item_id, tag in connection.execute(
            "SELECT it.itemID, t.name FROM itemTags it JOIN tags t ON t.tagID = it.tagID"
        ):
            tags[item_id].append(tag)
        for item_id, names in tags.items():
            if item_id in items:
                items[item_id].tags = sorted(names, key=str.casefold)

    if with_attachments:
        for parent_id, attachment_key, raw, content_type in connection.execute(
            """
            SELECT a.parentItemID, i.key, a.path, a.contentType
            FROM itemAttachments a JOIN items i ON i.itemID = a.itemID
            WHERE a.parentItemID IS NOT NULL AND a.path IS NOT NULL
            """
        ):
            item = items.get(parent_id)
            if item is None:
                continue
            item.attachments.append(
                LocalAttachment(
                    attachment_key=attachment_key,
                    raw_path=raw,
                    content_type=content_type or "",
                    path=resolve_attachment(raw, attachment_key, data_dir, attachment_root),
                )
            )

    return list(items.values())


def fulltext_item_ids(connection: sqlite3.Connection, tokens: list[str]) -> dict[int, set[str]]:
    """Parent item ids whose attachment full text contains each token."""
    found: dict[int, set[str]] = defaultdict(set)
    if not tokens:
        return found
    placeholders = ",".join("?" for _ in tokens)
    for parent_id, word in connection.execute(
        f"""
        SELECT a.parentItemID, lower(w.word)
        FROM fulltextItemWords fw
        JOIN fulltextWords w ON w.wordID = fw.wordID
        JOIN itemAttachments a ON a.itemID = fw.itemID
        WHERE lower(w.word) IN ({placeholders})
          AND a.parentItemID IS NOT NULL
        """,
        tokens,
    ):
        found[parent_id].add(word)
    return found
