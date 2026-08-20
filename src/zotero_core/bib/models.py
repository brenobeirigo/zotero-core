"""The staged work: one BibTeX entry, resolved to Zotero's vocabulary."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Work:
    citation_key: str
    stream: str
    item_type: str
    item_type_reason: str
    title: str
    year: str = ""
    doi: str = ""
    match_creator: str = ""
    fields: dict[str, str] = field(default_factory=dict)
    creators: list[dict] = field(default_factory=list)

    def to_payload(self) -> dict:
        """The wire shape the desktop bridge consumes.

        Kept in the connector's original camelCase so its JS applier needs no
        change beyond where the plan is computed.
        """
        return {
            "citationKey": self.citation_key,
            "stream": self.stream,
            "itemType": self.item_type,
            "itemTypeReason": self.item_type_reason,
            "title": self.title,
            "year": self.year,
            "doi": self.doi,
            "matchCreator": self.match_creator,
            "fields": dict(self.fields),
            "creators": list(self.creators),
        }
