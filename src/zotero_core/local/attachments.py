"""Resolve Zotero's `storage:` and `attachments:` attachment paths."""

from __future__ import annotations

from pathlib import Path


def resolve_attachment(
    raw: str,
    attachment_key: str,
    data_dir: Path | None,
    attachment_root: Path | None = None,
) -> Path | None:
    """Turn a stored attachment path into a filesystem path, or None.

    None means "this record does not name a resolvable file here" -- either a
    linked attachment with no configured root, or a relative path with no
    anchor. Callers that need the raw string back keep it themselves.
    """
    if raw.startswith("storage:") and data_dir:
        return (data_dir / "storage" / attachment_key / raw.removeprefix("storage:")).resolve()
    if raw.startswith("attachments:") and attachment_root:
        return (attachment_root / raw.removeprefix("attachments:")).resolve()
    candidate = Path(raw)
    return candidate.resolve() if candidate.is_absolute() else None
