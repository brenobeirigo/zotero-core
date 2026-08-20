"""Work identity: normalization, citation keys, and the dedup match ladder.

Four tools used to spell "the same work" four different ways. This module is
the single spelling. The JS constants below are exported so the desktop
backend and the parity test read the *same* definition the Python functions
use -- a Python normalizer that disagrees with the JS one is a silent dedup
miss, which writes real duplicates into a real library.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

# Letters and digits only, Unicode-aware, underscore excluded so that this
# agrees exactly with the JS \p{L}\p{N} class below.
_WORD = re.compile(r"[^\W_]+", re.UNICODE)

_DOI_PREFIX = re.compile(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)")

_YEAR = re.compile(r"\b(?:19|20)\d{2}\b")

# Anchored at both ends: an unanchored pattern happily reads a note saying
# "no Citation Key: unknown" and returns "unknown".
CITATION_KEY_RE = re.compile(r"(?im)^citation key:\s*(\S+)\s*$")

#: The JS twin of :func:`normalize_title`. Keep the two in lockstep.
JS_NORMALIZE_TITLE = """
const normalizeTitle = value => (value || "")
    .normalize("NFKD")
    .replace(/\p{M}+/gu, "")
    .toLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, " ")
    .trim();
"""

#: The JS twin of :func:`normalize_doi`.
JS_CLEAN_DOI = """
const cleanDOI = value => (Zotero.Utilities.cleanDOI(value || "") || "").toLowerCase();
"""


def normalize_doi(value: str | None) -> str:
    """Strip resolver prefixes and case from a DOI."""
    return _DOI_PREFIX.sub("", (value or "").strip().casefold())


def normalize_title(value: str | None) -> str:
    """Fold a title to space-separated lowercase alphanumeric words.

    NFKD plus combining-mark removal is not cosmetic: the desktop route
    compares these Python-normalized entries against JS-normalized library
    items, and without it "Zurich" and "Zürich" are different works.
    """
    if not value:
        return ""
    decomposed = unicodedata.normalize("NFKD", value)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return " ".join(_WORD.findall(stripped.casefold()))


def identity_slug(value: str | None) -> str:
    """:func:`normalize_title` with the spaces removed, for compact keys."""
    return normalize_title(value).replace(" ", "")


def parse_year(value: str | None) -> str:
    match = _YEAR.search(value or "")
    return match.group(0) if match else ""


def citation_key_from_extra(extra: str | None) -> str:
    match = CITATION_KEY_RE.search(extra or "")
    return match.group(1) if match else ""


def format_citation_key(key: str) -> str:
    """Render the Extra line. Byte-identical to what both tools already write."""
    return f"Citation Key: {key}"


DOI = "doi"
CITEKEY = "citekey"
TITLE_YEAR_CREATOR = "title-year-creator"
TITLE_YEAR = "title-year"

#: Every rule, in precedence order. See :func:`rules_for`.
MATCH_RULES = (DOI, CITEKEY, TITLE_YEAR_CREATOR, TITLE_YEAR)


@dataclass(frozen=True)
class LibraryItem:
    """One regular item, however it was obtained: bridge, Web API, or SQLite."""

    key: str
    title: str = ""
    year: str = ""
    doi: str = ""
    first_creator: str = ""
    citation_key: str = ""
    collection_keys: tuple[str, ...] = ()


@dataclass
class MatchResult:
    rule: str | None
    items: list[LibraryItem] = field(default_factory=list)
    low_confidence: bool = False

    @property
    def item(self) -> LibraryItem | None:
        return self.items[0] if len(self.items) == 1 else None

    @property
    def ambiguous(self) -> bool:
        return len(self.items) > 1


def _keys_for(rule: str, doi: str, citekey: str, title: str, year: str, creator: str) -> str:
    if rule == DOI:
        return normalize_doi(doi)
    if rule == CITEKEY:
        return citekey
    base = f"{identity_slug(title)}|{year}"
    if rule == TITLE_YEAR_CREATOR:
        return f"{base}|{identity_slug(creator)}"
    return base


def rules_for(doi: str, citekey: str, creator: str) -> list[str]:
    """Which rules apply to one staged work, in order.

    A DOI is a global identifier, so it is tried first -- and when a work
    *has* a DOI, the title heuristics are never tried. Matching a DOI-bearing
    entry to a differently-identified item by title is a guess, and the
    connector has always refused it. The citation key sits between the two:
    it is user-assigned rather than inferred, and it is what makes re-running
    the same project idempotent.
    """
    rules: list[str] = []
    if normalize_doi(doi):
        rules.append(DOI)
    if citekey:
        rules.append(CITEKEY)
    if not normalize_doi(doi):
        rules.append(TITLE_YEAR_CREATOR if identity_slug(creator) else TITLE_YEAR)
    return rules


class LibraryIndex:
    """Every library item, indexed once per rule."""

    def __init__(self, items: list[LibraryItem] | None = None) -> None:
        self._index: dict[str, dict[str, list[LibraryItem]]] = {r: {} for r in MATCH_RULES}
        for item in items or []:
            self.add(item)

    def add(self, item: LibraryItem) -> None:
        for rule in MATCH_RULES:
            key = _keys_for(
                rule,
                item.doi,
                item.citation_key,
                item.title,
                item.year,
                item.first_creator,
            )
            if not key or key.strip("|") == "":
                continue
            self._index[rule].setdefault(key, []).append(item)

    def lookup(self, rule: str, key: str) -> list[LibraryItem]:
        return list(self._index[rule].get(key, ()))

    def __len__(self) -> int:
        return len({item.key for bucket in self._index[DOI].values() for item in bucket})


def match_work(
    *,
    doi: str = "",
    citekey: str = "",
    title: str = "",
    year: str = "",
    creator: str = "",
    index: LibraryIndex,
) -> MatchResult:
    """Walk the ladder; the first rule with at least one hit decides."""
    for rule in rules_for(doi, citekey, creator):
        key = _keys_for(rule, doi, citekey, title, year, creator)
        if not key or key.strip("|") == "":
            continue
        hits = index.lookup(rule, key)
        if hits:
            low = rule in (TITLE_YEAR_CREATOR, TITLE_YEAR) and not year
            return MatchResult(rule=rule, items=hits, low_confidence=low)
    return MatchResult(rule=None)
