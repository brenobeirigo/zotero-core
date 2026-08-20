"""The Python and JS title normalizers must agree, character for character.

The desktop route compares Python-normalized BibTeX entries against
JS-normalized library items running inside Zotero. Any disagreement is a
silent dedup miss, and a silent dedup miss writes a real duplicate into a real
library. This test runs the actual JS from the desktop backend when node is
available, so the two definitions cannot drift apart unnoticed.
"""

from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from zotero_core.identity import JS_NORMALIZE_TITLE, normalize_title

CASES = [
    "Zürich",
    "Zurich",
    "Dynamic Routing: Under Uncertainty!",
    "Coordinating   Heterogeneous  Fleets",
    "Å ngström and the naïve café",
    "a_b",
    "Multi-Agent (Deep) RL — 2021",
    "ÉCOLE POLYTECHNIQUE",
    "",
    "   ",
]

pytestmark = pytest.mark.skipif(
    shutil.which("node") is None, reason="node is not installed"
)


def test_python_and_js_normalizers_agree(tmp_path):
    script = tmp_path / "normalize.mjs"
    script.write_text(
        JS_NORMALIZE_TITLE
        + "\nconst cases = "
        + json.dumps(CASES, ensure_ascii=False)
        + ";\nconsole.log(JSON.stringify(cases.map(normalizeTitle)));\n",
        encoding="utf-8",
    )
    completed = subprocess.run(
        ["node", str(script)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    from_js = json.loads(completed.stdout)
    from_python = [normalize_title(case) for case in CASES]
    assert from_js == from_python
