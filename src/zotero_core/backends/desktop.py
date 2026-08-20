"""The Zotero Desktop backend, via the Zotero CLI Bridge.

The bridge is an out-of-band component that is **not distributed** with this
package; see ``docs/backends.md``. When it is missing, this module says so in
those words rather than reporting a connection problem -- Zotero answering on
the port and the bridge being installed are different facts with different
remedies, and conflating them is the most confusing failure this tooling has.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from ..errors import BridgeError, BridgeNotInstalled, ZoteroUnavailable
from ..identity import LibraryItem, citation_key_from_extra
from ..plan.models import CollectionRef

CONNECTOR_BASE = "http://127.0.0.1:23119"
BRIDGE_PATH = "/cli-bridge/eval"
USER_AGENT = "zotero-core/0.1"

# Copied verbatim from the connector's importer. Reading the DOI out of Extra
# as well as the DOI field is not optional: DOIs stashed in Extra are routine
# for reports and preprints, and dropping that read degrades matching
# silently, which writes real duplicates into a real library.
JS_HELPERS = r"""
const cleanDOI = value => (Zotero.Utilities.cleanDOI(value || "") || "").toLowerCase();
const doiOf = item => cleanDOI(item.getField("DOI") || item.getExtraField("DOI"));
const yearOf = item => {
    const parsed = Zotero.Date.strToDate(item.getField("date") || "");
    if (parsed && parsed.year) return String(parsed.year);
    const match = (item.getField("date") || "").match(/\b(19|20)\d{2}\b/);
    return match ? match[0] : "";
};
"""

_SNAPSHOT_JS = (
    JS_HELPERS
    + r"""
const lib = Zotero.Libraries.userLibraryID;
const collectionsByID = new Map(
    Zotero.Collections.getByLibrary(lib, true).map(c => [c.id, c.key])
);
const items = (await Zotero.Items.getAll(lib, true)).filter(
    item => item && typeof item.isRegularItem === "function" && item.isRegularItem() && !item.deleted
);
return items.map(item => ({
    key: item.key,
    title: item.getField("title") || "",
    year: yearOf(item),
    doi: doiOf(item),
    firstCreator: item.getField("firstCreator") || "",
    extra: item.getField("extra") || "",
    collectionKeys: item.getCollections().map(id => collectionsByID.get(id)).filter(Boolean),
}));
"""
)

_COLLECTIONS_JS = r"""
const lib = Zotero.Libraries.userLibraryID;
const all = Zotero.Collections.getByLibrary(lib, true);
const byID = new Map(all.map(c => [c.id, c.key]));
return all.map(c => ({
    name: c.name,
    key: c.key,
    parentKey: c.parentID ? (byID.get(c.parentID) || null) : null,
}));
"""

_ENSURE_COLLECTION_JS = r"""
const lib = Zotero.Libraries.userLibraryID;
const all = Zotero.Collections.getByLibrary(lib, true);
const parent = parentKey ? all.find(c => c.key === parentKey) : null;
if (parentKey && !parent) throw new Error("Parent collection not found: " + parentKey);
const parentID = parent ? parent.id : null;
const matches = all.filter(c => c.name === name && (c.parentID || null) === parentID);
if (matches.length > 1) throw new Error("Duplicate sibling collections named: " + name);
if (matches.length === 1) return matches[0].key;
const collection = new Zotero.Collection();
collection.libraryID = lib;
collection.name = name;
if (parentID) collection.parentID = parentID;
await collection.saveTx();
return collection.key;
"""

_CREATE_ITEMS_JS = r"""
const lib = Zotero.Libraries.userLibraryID;
const byKey = new Map(Zotero.Collections.getByLibrary(lib, true).map(c => [c.key, c]));
const created = [];
await Zotero.DB.executeTransaction(async () => {
    for (const row of rows) {
        const target = byKey.get(row.targetKey);
        if (!target) throw new Error("Target collection not found: " + row.targetKey);
        const item = new Zotero.Item(row.entry.itemType);
        item.libraryID = lib;
        for (const [field, value] of Object.entries(row.entry.fields)) {
            const fieldID = Zotero.ItemFields.getID(field);
            if (fieldID && Zotero.ItemFields.isValidForType(fieldID, item.itemTypeID)) {
                item.setField(field, value);
            }
        }
        item.setCreators(row.entry.creators);
        item.setCollections([target.id]);
        await item.save();
        created.push(item.key);
    }
});
if (shouldSync) await Zotero.Sync.Runner.sync({background: true});
return created;
"""

_ADD_TO_COLLECTION_JS = r"""
const lib = Zotero.Libraries.userLibraryID;
const collection = Zotero.Collections.getByLibrary(lib, true).find(c => c.key === collectionKey);
if (!collection) throw new Error("Collection not found: " + collectionKey);
const item = Zotero.Items.getByLibraryAndKey(lib, itemKey);
if (!item) throw new Error("Item not found: " + itemKey);
const collections = item.getCollections();
if (!collections.includes(collection.id)) {
    item.setCollections([...collections, collection.id]);
    await item.saveTx();
}
return true;
"""


def _const(**values) -> str:
    """Bind script parameters as JS consts, JSON-encoded."""
    return "".join(
        f"const {name} = {json.dumps(value, ensure_ascii=False)};\n"
        for name, value in values.items()
    )


def evaluate(script: str, timeout: float = 120.0):
    """Run one script inside Zotero and return its JSON result."""
    request = urllib.request.Request(
        CONNECTOR_BASE + BRIDGE_PATH,
        data=script.encode("utf-8"),
        headers={"Content-Type": "text/plain", "User-Agent": USER_AGENT},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read())
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise BridgeNotInstalled(
                "Zotero is running, but the Zotero CLI Bridge endpoint "
                f"({BRIDGE_PATH}) is not installed, so write commands are "
                "unavailable. See docs/backends.md."
            ) from exc
        body = exc.read().decode("utf-8", errors="replace")
        try:
            error = json.loads(body).get("error", body)
        except json.JSONDecodeError:
            error = body or str(exc)
        raise BridgeError(error) from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise ZoteroUnavailable(
            "Zotero Desktop is not running, or is not listening on "
            f"{CONNECTOR_BASE}. Start Zotero and try again."
        ) from exc

    if isinstance(payload, dict) and payload.get("error"):
        raise BridgeError(payload["error"])
    return payload


def bridge_ping() -> dict:
    return evaluate(
        "return {version: Zotero.version, libraryID: Zotero.Libraries.userLibraryID};",
        timeout=10,
    )


def sync_library() -> dict:
    return evaluate(
        "const started = Date.now();\n"
        "await Zotero.Sync.Runner.sync({background: true});\n"
        "return {ok: true, elapsedMs: Date.now() - started};",
        timeout=120,
    )


class DesktopBridgeBackend:
    name = "desktop"

    def __init__(self, *, timeout: float = 180.0, sync_after_write: bool = True) -> None:
        self.timeout = timeout
        self.sync_after_write = sync_after_write

    def snapshot_library(self) -> list[LibraryItem]:
        return [
            LibraryItem(
                key=row["key"],
                title=row.get("title", ""),
                year=row.get("year", ""),
                doi=row.get("doi", ""),
                first_creator=row.get("firstCreator", ""),
                citation_key=citation_key_from_extra(row.get("extra", "")),
                collection_keys=tuple(row.get("collectionKeys") or ()),
            )
            for row in evaluate(_SNAPSHOT_JS, timeout=self.timeout)
        ]

    def list_collections(self) -> list[CollectionRef]:
        return [
            CollectionRef(name=row["name"], key=row["key"], parent_key=row.get("parentKey"))
            for row in evaluate(_COLLECTIONS_JS, timeout=self.timeout)
        ]

    def ensure_collection(self, name: str, parent_key: str | None) -> str:
        script = _const(name=name, parentKey=parent_key) + _ENSURE_COLLECTION_JS
        return evaluate(script, timeout=self.timeout)

    def create_items(self, payloads: list[tuple[dict, str]]) -> list[str]:
        rows = [{"entry": work, "targetKey": target} for work, target in payloads]
        script = (
            _const(rows=rows, shouldSync=bool(self.sync_after_write)) + _CREATE_ITEMS_JS
        )
        return evaluate(script, timeout=self.timeout)

    def add_to_collection(self, item_key: str, collection_key: str) -> None:
        script = (
            _const(itemKey=item_key, collectionKey=collection_key) + _ADD_TO_COLLECTION_JS
        )
        evaluate(script, timeout=self.timeout)
