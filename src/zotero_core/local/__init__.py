"""Read-only access to a local Zotero installation."""

from .attachments import resolve_attachment
from .datadir import find_data_dir, machine_attachment_root
from .db import IMMUTABLE, READ_ONLY, open_read_only
from .items import LocalAttachment, LocalItem, fulltext_item_ids, load_items

__all__ = [
    "IMMUTABLE",
    "READ_ONLY",
    "LocalAttachment",
    "LocalItem",
    "find_data_dir",
    "fulltext_item_ids",
    "load_items",
    "machine_attachment_root",
    "open_read_only",
    "resolve_attachment",
]
