"""What a backend must provide.

Deliberately primitives, not a planner. Planning lives in
:mod:`zotero_core.plan` so that every route decides the same way; a backend
only has to say what is in the library and do what it is told.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..identity import LibraryItem
from ..plan.models import CollectionRef


@runtime_checkable
class Backend(Protocol):
    name: str

    def snapshot_library(self) -> list[LibraryItem]:
        """Every regular item, flattened to what matching needs."""

    def list_collections(self) -> list[CollectionRef]:
        """Every collection, with its parent."""

    def ensure_collection(self, name: str, parent_key: str | None) -> str:
        """Return the key of the named collection under ``parent_key``, creating it if absent."""

    def create_items(self, payloads: list[tuple[dict, str]]) -> list[str]:
        """Create items from ``(work payload, target collection key)`` pairs."""

    def add_to_collection(self, item_key: str, collection_key: str) -> None:
        """File an existing item into a collection, leaving its other collections alone."""
