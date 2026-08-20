"""Find Zotero's data directory and the linked-attachment root.

Two front-ends carried byte-for-byte copies of this discovery logic. This is
the copy that survives.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

_DATA_DIR_PREF = re.compile(
    r'user_pref\("extensions\.zotero\.dataDir",\s*"(.+?)"\);'
)


def find_data_dir() -> Path | None:
    """The directory containing `zotero.sqlite`, or None.

    Tries the default location first, then the `dataDir` preference recorded
    in each Firefox-style profile's `prefs.js`.
    """
    candidate = Path.home() / "Zotero"
    if (candidate / "zotero.sqlite").exists():
        return candidate

    appdata = os.environ.get("APPDATA")
    if not appdata:
        return None
    profiles = Path(appdata) / "Zotero" / "Zotero" / "Profiles"
    if not profiles.exists():
        return None
    for prefs in sorted(profiles.glob("*/prefs.js")):
        text = prefs.read_text(encoding="utf-8", errors="ignore")
        match = _DATA_DIR_PREF.search(text)
        if not match:
            continue
        path = Path(bytes(match.group(1), "utf-8").decode("unicode_escape"))
        if (path / "zotero.sqlite").exists():
            return path
    return None


def machine_attachment_root() -> Path | None:
    """The linked-attachment base directory declared in `~/.openclaw/machine-paths.json`."""
    profile = Path.home() / ".openclaw" / "machine-paths.json"
    if not profile.exists():
        return None
    try:
        value = json.loads(profile.read_text(encoding="utf-8"))["roots"]["zotero"]
    except (KeyError, TypeError, json.JSONDecodeError):
        return None
    path = Path(value)
    return path if path.exists() else None
