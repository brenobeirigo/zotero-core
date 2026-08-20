"""The Zotero Web API backend.

The credential rule is the one the skill established and is not negotiable
here: the API key is read from the ``ZOTERO_API_KEY`` environment variable
only. It is never accepted as an argument, never written to a file, and never
printed. There is likewise **no default library id** -- a built-in default
means someone else's install silently writes at your library.
"""

from __future__ import annotations

import os

from ..errors import BackendUnavailable
from ..identity import LibraryItem, citation_key_from_extra, parse_year
from ..plan.models import CollectionRef

_NON_REGULAR = {"attachment", "note", "annotation"}
_CHUNK = 50


def _pyzotero():
    try:
        from pyzotero import zotero
    except ModuleNotFoundError as exc:  # pragma: no cover - exercised by the offline test
        raise BackendUnavailable(
            "The Web API backend needs pyzotero. Install it with:\n"
            "    python -m pip install \"zotero-core[web]\""
        ) from exc
    return zotero


def resolve_library_id(explicit: str | None = None) -> str:
    library_id = explicit or os.environ.get("ZOTERO_USER_ID")
    if not library_id:
        raise BackendUnavailable(
            "No Zotero library id. Pass --library-id, or set ZOTERO_USER_ID.\n"
            "Find yours at https://www.zotero.org/settings/keys (\"Your userID for use in API calls\")."
        )
    return library_id


def resolve_api_key() -> str:
    api_key = os.environ.get("ZOTERO_API_KEY")
    if not api_key:
        raise BackendUnavailable(
            "Set ZOTERO_API_KEY in your environment first; it is never read from a "
            "file or an argument.\n"
            "    PowerShell:  $env:ZOTERO_API_KEY = \"<write-enabled key>\"\n"
            "    bash:        export ZOTERO_API_KEY=\"<write-enabled key>\"\n"
            "Create one at https://www.zotero.org/settings/keys"
        )
    return api_key


class WebApiBackend:
    name = "web"

    def __init__(self, library_id: str | None = None, library_type: str = "user") -> None:
        zotero = _pyzotero()
        self.library_id = resolve_library_id(library_id)
        self.library_type = library_type
        self._zot = zotero.Zotero(self.library_id, library_type, resolve_api_key())
        self._templates: dict[str, dict] = {}
        self._collections: list[CollectionRef] | None = None

    def snapshot_library(self) -> list[LibraryItem]:
        items: list[LibraryItem] = []
        for record in self._zot.everything(self._zot.items()):
            data = record.get("data", {})
            if data.get("itemType") in _NON_REGULAR:
                continue
            items.append(
                LibraryItem(
                    key=data.get("key", ""),
                    title=data.get("title", ""),
                    year=parse_year(data.get("date", "")),
                    doi=data.get("DOI", ""),
                    first_creator=_first_creator(data.get("creators") or []),
                    citation_key=citation_key_from_extra(data.get("extra", "")),
                    collection_keys=tuple(data.get("collections") or ()),
                )
            )
        return items

    def list_collections(self) -> list[CollectionRef]:
        if self._collections is None:
            self._collections = [
                CollectionRef(
                    name=record["data"]["name"],
                    key=record["data"]["key"],
                    parent_key=record["data"].get("parentCollection") or None,
                )
                for record in self._zot.everything(self._zot.collections())
            ]
        return list(self._collections)

    def ensure_collection(self, name: str, parent_key: str | None) -> str:
        for collection in self.list_collections():
            if collection.name == name and collection.parent_key == parent_key:
                return collection.key
        payload = {"name": name}
        if parent_key:
            payload["parentCollection"] = parent_key
        key = self._zot.create_collections([payload])["successful"]["0"]["data"]["key"]
        assert self._collections is not None
        self._collections.append(CollectionRef(name=name, key=key, parent_key=parent_key))
        return key

    def create_items(self, payloads: list[tuple[dict, str]]) -> list[str]:
        batch = [self._to_item(work, target) for work, target in payloads]
        keys: list[str] = []
        for start in range(0, len(batch), _CHUNK):
            response = self._zot.create_items(batch[start : start + _CHUNK])
            successful = response.get("successful", {})
            keys.extend(
                successful[index]["data"]["key"] for index in sorted(successful, key=int)
            )
        return keys

    def add_to_collection(self, item_key: str, collection_key: str) -> None:
        item = self._zot.item(item_key)
        collections = list(item["data"].get("collections") or [])
        if collection_key in collections:
            return
        collections.append(collection_key)
        item["data"]["collections"] = collections
        self._zot.update_item(item)

    def _template(self, item_type: str) -> dict:
        if item_type not in self._templates:
            self._templates[item_type] = self._zot.item_template(item_type)
        return self._templates[item_type]

    def _to_item(self, work: dict, target_key: str) -> dict:
        item = dict(self._template(work["itemType"]))
        for field, value in work["fields"].items():
            if field in item and value:
                item[field] = value
        if work.get("creators"):
            item["creators"] = work["creators"]
        item["collections"] = [target_key]
        return item


def _first_creator(creators: list[dict]) -> str:
    if not creators:
        return ""
    first = creators[0]
    return first.get("lastName") or first.get("name") or ""
