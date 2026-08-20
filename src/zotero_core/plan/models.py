"""The import plan: what would happen, decided before anything is written."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..bib.models import Work

CREATE = "create"
ADD_EXISTING = "add-existing"
ALREADY_PRESENT = "already-present"
PRESERVE_EXISTING_LEAF = "preserve-existing-project-leaf"
NEEDS_REVIEW = "needs-review"

#: Actions that write something when the plan is applied.
WRITING_ACTIONS = (CREATE, ADD_EXISTING)


@dataclass
class CollectionRef:
    name: str
    key: str | None = None
    parent_key: str | None = None

    @property
    def exists(self) -> bool:
        return self.key is not None


@dataclass
class Conflict:
    citation_key: str
    title: str
    reason: str
    item_keys: list[str] = field(default_factory=list)


@dataclass
class PlanRow:
    citation_key: str
    title: str
    stream: str
    action: str
    item_type: str
    item_type_reason: str
    target_collection: str
    item_key: str | None = None
    matched_by: str | None = None
    existing_project_collections: list[str] = field(default_factory=list)
    note: str = ""
    work: Work | None = None

    def to_dict(self) -> dict:
        return {
            "citationKey": self.citation_key,
            "title": self.title,
            "stream": self.stream,
            "action": self.action,
            "itemType": self.item_type,
            "itemTypeReason": self.item_type_reason,
            "targetCollection": self.target_collection,
            "itemKey": self.item_key,
            "matchedBy": self.matched_by,
            "existingProjectCollections": list(self.existing_project_collections),
            "note": self.note,
        }


@dataclass
class ImportPlan:
    parent_name: str
    parent_key: str | None = None
    parsed: int = 0
    rows: list[PlanRow] = field(default_factory=list)
    conflicts: list[Conflict] = field(default_factory=list)
    collections: list[CollectionRef] = field(default_factory=list)
    applied: bool = False
    offline: bool = False

    @property
    def ok(self) -> bool:
        return not self.conflicts

    @property
    def counts(self) -> dict[str, int]:
        counts = {
            CREATE: 0,
            ADD_EXISTING: 0,
            ALREADY_PRESENT: 0,
            PRESERVE_EXISTING_LEAF: 0,
            NEEDS_REVIEW: 0,
        }
        for row in self.rows:
            counts[row.action] = counts.get(row.action, 0) + 1
        return counts

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "applied": self.applied,
            "offline": self.offline,
            "parentName": self.parent_name,
            "parentKey": self.parent_key,
            "parsed": self.parsed,
            "counts": self.counts,
            "collections": [
                {"name": c.name, "key": c.key, "existed": c.exists} for c in self.collections
            ],
            "conflicts": [
                {
                    "citationKey": c.citation_key,
                    "title": c.title,
                    "reason": c.reason,
                    "itemKeys": list(c.item_keys),
                }
                for c in self.conflicts
            ],
            "plan": [row.to_dict() for row in self.rows],
        }
