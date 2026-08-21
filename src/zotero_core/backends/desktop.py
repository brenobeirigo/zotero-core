"""The Zotero Desktop backend, via the Zotero CLI Bridge.

The bridge is a third-party Zotero plugin, not part of this package and not
ours to ship; ``docs/cli-bridge.md`` says where it comes from and how to
install it. When it is missing, this module says so in those words rather than
reporting a connection problem -- Zotero answering on the port and the bridge
being installed are different facts with different remedies, and conflating
them is the most confusing failure this tooling has.
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

#: The plugin that provides :data:`BRIDGE_PATH`. Pinned by id so that an
#: endpoint answering under some other plugin's name is reported rather than
#: assumed to behave the same way.
BRIDGE_ADDON_ID = "cli-bridge@cli-anything.dev"

#: Where that plugin comes from. It is distributed inside the PyPI package
#: ``cli-anything-zotero``, which builds the .xpi and prints its path.
BRIDGE_PACKAGE = "cli-anything-zotero"
BRIDGE_HOMEPAGE = "https://github.com/PiaoyangGuohai1/cli-anything-zotero"

#: The oldest bridge this package is known to work against. Bumped only after
#: testing, never to match whatever happens to be installed.
MIN_BRIDGE_VERSION = (1, 2, 0)

#: The Zotero range the bridge's own manifest declares support for.
SUPPORTED_ZOTERO_VERSIONS = (7, 9)

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

# Zotero's merge records the replacement relation, which is why this calls it
# rather than deleting the losers outright. It does *not* reliably reparent
# their child items: observed against Zotero 9.0.6, the attachments stayed on
# the losing items and followed them into the trash. An attachment hanging off
# a duplicate is routinely the only copy of that PDF, so this moves the
# children across explicitly first and does not depend on merge to do it.
# Collections are unioned onto the master for the same reason.
#
# Already-trashed children are left where they are: the person who trashed
# them meant it, and a merge is no reason to resurrect them.
_MERGE_ITEMS_JS = r"""
const lib = Zotero.Libraries.userLibraryID;
const master = Zotero.Items.getByLibraryAndKey(lib, masterKey);
if (!master) throw new Error("Master item not found: " + masterKey);
const others = [];
for (const key of otherKeys) {
    const item = Zotero.Items.getByLibraryAndKey(lib, key);
    if (!item) throw new Error("Item not found: " + key);
    if (item.id === master.id) throw new Error("Master listed among its own duplicates: " + key);
    if (item.itemTypeID !== master.itemTypeID) {
        throw new Error(
            "Refusing to merge across item types: " + key + " is a "
            + Zotero.ItemTypes.getName(item.itemTypeID) + ", master is a "
            + Zotero.ItemTypes.getName(master.itemTypeID)
        );
    }
    others.push(item);
}
const collections = new Set(master.getCollections());
for (const item of others) {
    for (const id of item.getCollections()) collections.add(id);
}
if (collections.size !== master.getCollections().length) {
    master.setCollections([...collections]);
    await master.saveTx();
}
const attachmentsBefore = master.getAttachments().length;
const moved = [];
await Zotero.DB.executeTransaction(async () => {
    for (const item of others) {
        const childIDs = [...item.getAttachments(), ...item.getNotes()];
        for (const id of childIDs) {
            const child = Zotero.Items.get(id);
            child.parentItemID = master.id;
            await child.save();
            moved.push(child.key);
        }
    }
});
await Zotero.Items.merge(master, others);
const refreshed = Zotero.Items.getByLibraryAndKey(lib, masterKey);
const orphaned = [];
for (const key of otherKeys) {
    const loser = Zotero.Items.getByLibraryAndKey(lib, key);
    if (loser) orphaned.push(...loser.getAttachments().map(id => Zotero.Items.get(id).key));
}
if (orphaned.length) {
    throw new Error(
        "Merge left " + orphaned.length + " attachment(s) on a trashed duplicate: "
        + orphaned.join(", ")
    );
}
if (shouldSync) await Zotero.Sync.Runner.sync({background: true});
return {
    masterKey: masterKey,
    mergedKeys: otherKeys,
    collections: refreshed.getCollections().length,
    attachmentsBefore: attachmentsBefore,
    attachmentsAfter: refreshed.getAttachments().length,
    movedChildren: moved,
};
"""

_TRASH_ITEMS_JS = r"""
const lib = Zotero.Libraries.userLibraryID;
const trashed = [];
await Zotero.DB.executeTransaction(async () => {
    for (const key of itemKeys) {
        const item = Zotero.Items.getByLibraryAndKey(lib, key);
        if (!item) throw new Error("Item not found: " + key);
        if (!item.deleted) {
            item.deleted = true;
            await item.save();
        }
        trashed.push(item.key);
    }
});
if (shouldSync) await Zotero.Sync.Runner.sync({background: true});
return trashed;
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


# Asking the plugin about itself, rather than inferring it from "the endpoint
# answered". A stale bridge answers exactly like a current one right up to the
# call that needs the behavior it does not have.
_BRIDGE_INFO_JS = r"""
let addon = null;
let addonQueryError = null;
try {
    const { AddonManager } = ChromeUtils.importESModule(
        "resource://gre/modules/AddonManager.sys.mjs"
    );
    const found = await AddonManager.getAddonByID(addonID);
    if (found) {
        addon = {
            id: found.id,
            name: found.name || "",
            version: found.version || "",
            active: !!found.isActive,
            updateURL: found.updateURL || null,
        };
    }
} catch (e) {
    // "The add-on manager could not be reached" and "no such add-on" are
    // different answers. Reporting them as one would turn an unverifiable
    // environment into a confident accusation that the bridge is missing.
    addon = null;
    addonQueryError = (e && (e.message || String(e))) || "unknown error";
}
// Zotero.platform does not exist in Zotero 9; it read as undefined and this
// field was always empty. Services.appinfo.OS is what actually answers.
let platform = "";
try {
    if (typeof Services !== "undefined" && Services.appinfo) {
        platform = Services.appinfo.OS || "";
    }
} catch (e) {
    platform = "";
}
if (!platform) {
    platform = Zotero.isWin ? "WINNT" : Zotero.isMac ? "Darwin" : Zotero.isLinux ? "Linux" : "";
}
return {
    zoteroVersion: Zotero.version,
    platform: platform,
    libraryID: Zotero.Libraries.userLibraryID,
    endpointRegistered: Object.prototype.hasOwnProperty.call(
        Zotero.Server.Endpoints, endpointPath
    ),
    addon: addon,
    addonQueryError: addonQueryError,
};
"""


def _version_tuple(value: str) -> tuple[int, ...]:
    """Leading numeric components only. '1.2.0-beta.3' sorts as (1, 2, 0)."""
    parts: list[int] = []
    for chunk in str(value).split("."):
        digits = ""
        for character in chunk:
            if not character.isdigit():
                break
            digits += character
        if digits:
            parts.append(int(digits))
        # A chunk that is not purely numeric ends the version. Anything after
        # it is pre-release noise, and reading '1.2.0-beta.3' as (1, 2, 0, 3)
        # would rank a beta *above* the release it precedes.
        if digits != chunk:
            break
    return tuple(parts)


def describe_bridge(payload: dict) -> dict:
    """Turn a raw bridge report into a verdict, with the reasons spelled out.

    Kept separate from the call that fetches it so the judgement is testable
    without a running Zotero -- which is the whole difficulty with this
    component.
    """
    addon = payload.get("addon") or None
    problems: list[str] = []

    zotero_version = str(payload.get("zoteroVersion") or "")
    zotero_major = _version_tuple(zotero_version)[:1]
    low, high = SUPPORTED_ZOTERO_VERSIONS
    if zotero_major and not (low <= zotero_major[0] <= high):
        problems.append(
            f"Zotero {zotero_version} is outside the {low}.x-{high}.x range the "
            "bridge plugin declares support for"
        )

    if not payload.get("endpointRegistered"):
        problems.append(
            f"{BRIDGE_PATH} is not registered; the bridge plugin is absent or disabled"
        )

    bridge_version = ""
    query_error = payload.get("addonQueryError") or ""
    if addon is None and query_error:
        # Not the same as "the plugin is missing". We could not ask, so the
        # version is unknown and this says exactly that.
        problems.append(
            f"could not read the plugin's version from Zotero's add-on manager "
            f"({query_error}); the bridge may still be fine, but it is unverified"
        )
    elif addon is None:
        problems.append(
            "the bridge endpoint answered but no plugin reported itself under "
            f"{BRIDGE_ADDON_ID}; something else is serving {BRIDGE_PATH}"
        )
    else:
        bridge_version = str(addon.get("version") or "")
        if not addon.get("active"):
            problems.append(f"the {BRIDGE_ADDON_ID} plugin is installed but not active")
        if bridge_version and _version_tuple(bridge_version) < MIN_BRIDGE_VERSION:
            expected = ".".join(str(part) for part in MIN_BRIDGE_VERSION)
            problems.append(
                f"bridge plugin {bridge_version} is older than the tested minimum "
                f"{expected}; upgrade with `pip install -U {BRIDGE_PACKAGE}` then "
                "`zotero-cli app install-plugin`"
            )

    return {
        "ok": not problems,
        "zoteroVersion": zotero_version,
        "platform": payload.get("platform", ""),
        "endpoint": BRIDGE_PATH,
        "endpointRegistered": bool(payload.get("endpointRegistered")),
        "addonID": BRIDGE_ADDON_ID,
        "bridgeVersion": bridge_version,
        "bridgeActive": bool(addon.get("active")) if addon else False,
        "versionKnown": addon is not None,
        "package": BRIDGE_PACKAGE,
        "homepage": BRIDGE_HOMEPAGE,
        "problems": problems,
    }


def bridge_info() -> dict:
    """What the bridge is, and whether this package trusts this copy of it."""
    payload = evaluate(
        _const(addonID=BRIDGE_ADDON_ID, endpointPath=BRIDGE_PATH) + _BRIDGE_INFO_JS,
        timeout=20,
    )
    return describe_bridge(payload)


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

    def merge_items(self, master_key: str, other_keys: list[str]) -> dict:
        script = (
            _const(
                masterKey=master_key,
                otherKeys=list(other_keys),
                shouldSync=bool(self.sync_after_write),
            )
            + _MERGE_ITEMS_JS
        )
        return evaluate(script, timeout=self.timeout)

    def trash_items(self, item_keys: list[str]) -> list[str]:
        script = (
            _const(itemKeys=list(item_keys), shouldSync=bool(self.sync_after_write))
            + _TRASH_ITEMS_JS
        )
        return evaluate(script, timeout=self.timeout)

    def add_to_collection(self, item_key: str, collection_key: str) -> None:
        script = (
            _const(itemKey=item_key, collectionKey=collection_key) + _ADD_TO_COLLECTION_JS
        )
        evaluate(script, timeout=self.timeout)
