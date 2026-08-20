"""Open Zotero's SQLite database without ever writing to it."""

from __future__ import annotations

import sqlite3
from pathlib import Path

READ_ONLY = "read-only"
IMMUTABLE = "immutable-fallback"


def open_read_only(database: str | Path, *, timeout: float = 0.2) -> tuple[sqlite3.Connection, str]:
    """Return ``(connection, mode)``, falling back when the live app holds a lock.

    Immutable mode takes no locks and can therefore miss changes Zotero has
    not yet checkpointed into the main database file. The returned mode keeps
    that limitation visible to whatever is auditing, instead of quietly
    reporting stale data as current.
    """
    path = Path(database)
    uri = f"file:{path.as_posix()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True, timeout=timeout)
    try:
        connection.execute("SELECT 1 FROM items LIMIT 1").fetchone()
        return connection, READ_ONLY
    except sqlite3.OperationalError as exc:
        connection.close()
        if "locked" not in str(exc).casefold():
            raise
    immutable = sqlite3.connect(f"{uri}&immutable=1", uri=True)
    immutable.execute("SELECT 1 FROM items LIMIT 1").fetchone()
    return immutable, IMMUTABLE
