"""A backend that knows nothing, for planning with no credential."""

from __future__ import annotations

from ..identity import LibraryItem
from ..plan.models import CollectionRef


class NullBackend:
    """Reports an empty library and refuses every write.

    Planning against this is the offline dry run: it needs no API key, no
    network, and no Zotero installation, and it still produces a complete plan.
    """

    name = "null"

    def snapshot_library(self) -> list[LibraryItem]:
        return []

    def list_collections(self) -> list[CollectionRef]:
        return []

    def ensure_collection(self, name: str, parent_key: str | None) -> str:
        raise NotImplementedError("NullBackend never writes; plan only")

    def create_items(self, payloads: list[tuple[dict, str]]) -> list[str]:
        raise NotImplementedError("NullBackend never writes; plan only")

    def add_to_collection(self, item_key: str, collection_key: str) -> None:
        raise NotImplementedError("NullBackend never writes; plan only")
