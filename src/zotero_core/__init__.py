"""Shared Zotero library core.

One definition of what a work is, one BibTeX mapping, one read-only local
database reader, and one plan that every backend applies the same way.
"""

from __future__ import annotations

__version__ = "0.1.0"

from .errors import (
    AmbiguousMatch,
    BackendUnavailable,
    BridgeError,
    BridgeNotInstalled,
    IncompleteEntry,
    UnsupportedEntryType,
    ZoteroCoreError,
    ZoteroUnavailable,
)
from .hashing import file_sha256
from .identity import (
    CITATION_KEY_RE,
    MATCH_RULES,
    LibraryIndex,
    LibraryItem,
    citation_key_from_extra,
    format_citation_key,
    identity_slug,
    match_work,
    normalize_doi,
    normalize_title,
    parse_year,
)

__all__ = [
    "CITATION_KEY_RE",
    "MATCH_RULES",
    "AmbiguousMatch",
    "BackendUnavailable",
    "BridgeError",
    "BridgeNotInstalled",
    "IncompleteEntry",
    "LibraryIndex",
    "LibraryItem",
    "UnsupportedEntryType",
    "ZoteroCoreError",
    "ZoteroUnavailable",
    "__version__",
    "citation_key_from_extra",
    "file_sha256",
    "format_citation_key",
    "identity_slug",
    "match_work",
    "normalize_doi",
    "normalize_title",
    "parse_year",
]
