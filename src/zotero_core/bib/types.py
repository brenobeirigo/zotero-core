"""BibTeX entry type -> Zotero item type, and what each item type requires."""

from __future__ import annotations

from ..errors import IncompleteEntry, UnsupportedEntryType

#: The union of the two tables that used to disagree. `misc` is absent on
#: purpose -- see :func:`resolve_item_type`.
TYPE_MAP = {
    "article": "journalArticle",
    "inproceedings": "conferencePaper",
    "conference": "conferencePaper",
    "incollection": "bookSection",
    "inbook": "bookSection",
    "book": "book",
    "phdthesis": "thesis",
    "mastersthesis": "thesis",
    "bachelorthesis": "thesis",
    "thesis": "thesis",
    "techreport": "report",
    "report": "report",
    "online": "webpage",
    "www": "webpage",
}

#: Item types for which a missing year means an incomplete record. A company
#: "Locations" page genuinely has no publication year, and demanding one just
#: invites a fabricated value into a library that backs a paper.
YEAR_REQUIRED = frozenset(
    {"journalArticle", "conferencePaper", "bookSection", "book", "thesis", "report"}
)

_VENUE_FIELDS = ("journal", "journaltitle", "booktitle")


def resolve_item_type(entry: dict, *, strict: bool = False) -> tuple[str, str]:
    """Return ``(item_type, reason)`` for one parsed BibTeX entry.

    `@misc` is dispatched on its contents rather than mapped to a fixed type.
    The two tools that fed this package disagreed about it because they hold
    different corpora, not different opinions: one is full of arXiv entries
    carrying an `eprint`, the other of institutional web sources carrying a
    `url`. Either fixed mapping silently mistypes the other's corpus.

    ``strict`` turns the final fallback into an error instead of a guess.
    """
    entry_type = (entry.get("ENTRYTYPE") or "").casefold()

    mapped = TYPE_MAP.get(entry_type)
    if mapped:
        return mapped, f"type-map:{entry_type}"

    if entry_type == "misc":
        if entry.get("eprint") or entry.get("archiveprefix"):
            return "preprint", "misc-eprint"
        if entry.get("url") and not any(entry.get(f) for f in _VENUE_FIELDS):
            return "webpage", "misc-url"
        if strict:
            raise UnsupportedEntryType(
                f"@misc entry {entry.get('ID')!r} has neither an eprint nor a bare url; "
                "--strict-types refuses to guess between preprint, webpage and document"
            )
        return "document", "misc-fallback"

    raise UnsupportedEntryType(
        f"unsupported BibTeX type {entry_type!r} for {entry.get('ID')!r}"
    )


def check_required(item_type: str, citation_key: str, title: str, year: str) -> None:
    if not title:
        raise IncompleteEntry(f"BibTeX entry {citation_key!r} requires a title")
    if not year and item_type in YEAR_REQUIRED:
        raise IncompleteEntry(
            f"BibTeX entry {citation_key!r} is a {item_type} and requires a year"
        )
