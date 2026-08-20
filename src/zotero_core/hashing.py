"""One file-hash helper, replacing three.

The default is lowercase, which is what every other tool in the world emits.
The connector CLI writes uppercase digests into `pdf-status.csv` and compares
them byte-wise when resuming a batch, so it passes ``uppercase=True``. Changing
that default would silently invalidate every recorded run.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

_BLOCK = 1024 * 1024


def file_sha256(path: str | Path, *, uppercase: bool = False) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(_BLOCK), b""):
            digest.update(block)
    value = digest.hexdigest()
    return value.upper() if uppercase else value
