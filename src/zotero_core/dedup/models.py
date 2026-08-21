"""The merge plan: which library items are one work, decided before any write.

An import plan answers "does this work already exist?". This answers the
question that is left over once a library has been imported into more than
once: "which of the items already here are the same work, and which single
item should survive?".

The two are deliberately separate. Import planning may never merge -- an
ambiguous match there is a conflict and stops the run -- because repairing
history is a decision a person makes, not a side effect of an import.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..identity import LibraryItem

#: Fold the group into one item and trash the rest.
MERGE = "merge"
#: Trash every item in the group without merging. For artifacts, not works.
TRASH = "trash"
#: A person has to decide. Never written.
REVIEW = "review"
#: Deliberately left alone.
SKIP = "skip"

ACTIONS = (MERGE, TRASH, REVIEW, SKIP)

#: Actions that write something when the plan is applied.
WRITING_ACTIONS = (MERGE, TRASH)


@dataclass
class DuplicateGroup:
    """Items that one match rule says are the same work."""

    rule: str
    identity: str
    items: list[LibraryItem] = field(default_factory=list)
    action: str = REVIEW
    master_key: str | None = None
    reason: str = ""

    @property
    def keys(self) -> list[str]:
        return [item.key for item in self.items]

    @property
    def other_keys(self) -> list[str]:
        return [key for key in self.keys if key != self.master_key]

    @property
    def master(self) -> LibraryItem | None:
        for item in self.items:
            if item.key == self.master_key:
                return item
        return None

    @property
    def title(self) -> str:
        for item in self.items:
            if item.title:
                return item.title
        return ""

    def to_dict(self) -> dict:
        return {
            "rule": self.rule,
            "identity": self.identity,
            "action": self.action,
            "masterKey": self.master_key,
            "reason": self.reason,
            "items": [
                {
                    "key": item.key,
                    "title": item.title,
                    "year": item.year,
                    "doi": item.doi,
                    "citationKey": item.citation_key,
                    "collectionKeys": list(item.collection_keys),
                }
                for item in self.items
            ],
        }

    @classmethod
    def from_dict(cls, payload: dict) -> DuplicateGroup:
        return cls(
            rule=payload["rule"],
            identity=payload.get("identity", ""),
            action=payload.get("action", REVIEW),
            master_key=payload.get("masterKey"),
            reason=payload.get("reason", ""),
            items=[
                LibraryItem(
                    key=row["key"],
                    title=row.get("title", ""),
                    year=row.get("year", ""),
                    doi=row.get("doi", ""),
                    citation_key=row.get("citationKey", ""),
                    collection_keys=tuple(row.get("collectionKeys") or ()),
                )
                for row in payload.get("items", [])
            ],
        )


@dataclass
class MergePlan:
    """Every duplicate group found in one library, and what to do with each."""

    groups: list[DuplicateGroup] = field(default_factory=list)
    applied: bool = False
    library_size: int = 0

    @property
    def counts(self) -> dict[str, int]:
        counts = {action: 0 for action in ACTIONS}
        for group in self.groups:
            counts[group.action] = counts.get(group.action, 0) + 1
        return counts

    @property
    def items_removed(self) -> int:
        """How many items stop being visible if this plan is applied."""
        total = 0
        for group in self.groups:
            if group.action == MERGE:
                total += len(group.other_keys)
            elif group.action == TRASH:
                total += len(group.keys)
        return total

    def validate(self) -> None:
        """Reject a plan that cannot be applied safely.

        A plan is editable by hand, which is the point -- so every assumption
        the applier makes has to be checked here rather than trusted.
        """
        seen: dict[str, str] = {}
        for group in self.groups:
            if group.action not in ACTIONS:
                raise ValueError(
                    f"Unknown action {group.action!r}; expected one of {', '.join(ACTIONS)}"
                )
            if len(group.items) < 2:
                raise ValueError(
                    f"Group {group.identity!r} holds {len(group.items)} item(s); "
                    "a duplicate group needs at least two"
                )
            if group.action == MERGE:
                if not group.master_key:
                    raise ValueError(f"Group {group.identity!r} is a merge with no master")
                if group.master_key not in group.keys:
                    raise ValueError(
                        f"Master {group.master_key} is not one of the items in "
                        f"group {group.identity!r}"
                    )
            for key in group.keys:
                if key in seen and seen[key] != group.identity:
                    raise ValueError(
                        f"Item {key} appears in two groups ({seen[key]!r} and "
                        f"{group.identity!r}); merging both would fold unrelated works"
                    )
                seen[key] = group.identity

    def to_dict(self) -> dict:
        return {
            "applied": self.applied,
            "librarySize": self.library_size,
            "counts": self.counts,
            "itemsRemoved": self.items_removed,
            "groups": [group.to_dict() for group in self.groups],
        }

    @classmethod
    def from_dict(cls, payload: dict) -> MergePlan:
        return cls(
            applied=bool(payload.get("applied", False)),
            library_size=int(payload.get("librarySize", 0)),
            groups=[DuplicateGroup.from_dict(row) for row in payload.get("groups", [])],
        )
