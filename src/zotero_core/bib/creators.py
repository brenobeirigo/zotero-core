"""One creator parser, replacing three.

The braced-corporate-author branch is the one behaviour worth calling out:
`{International Maritime Organization}` is a single institutional name, not a
person, and Zotero represents that as a single-field creator
(``fieldMode: 1``). Splitting it into a first and last name is the bug the
skill documented as a known limitation for months.
"""

from __future__ import annotations

import re

_AND = re.compile(r"\s+and\s+", re.IGNORECASE)


def clean(value: str | None) -> str:
    """Strip BibTeX braces and collapse whitespace."""
    return re.sub(r"\s+", " ", (value or "").replace("{", "").replace("}", "")).strip()


def _is_corporate(name: str) -> bool:
    return name.startswith("{") and name.endswith("}")


def parse_creators(author_field: str | None, *, creator_type: str = "author") -> list[dict]:
    creators: list[dict] = []
    for raw in _AND.split(author_field or ""):
        name = raw.strip()
        if not name:
            continue
        if _is_corporate(name):
            creators.append(
                {
                    "creatorType": creator_type,
                    "firstName": "",
                    "lastName": clean(name),
                    "fieldMode": 1,
                }
            )
            continue
        name = clean(name)
        if not name:
            continue
        if "," in name:
            last, first = (part.strip() for part in name.split(",", 1))
        elif " " in name:
            parts = name.split()
            first, last = " ".join(parts[:-1]), parts[-1]
        else:
            first, last = "", name
        creators.append(
            {"creatorType": creator_type, "firstName": first, "lastName": last}
        )
    return creators


def first_creator_match(author_field: str | None) -> str:
    """The surname (or institution) used to disambiguate a title/year match."""
    first = _AND.split(author_field or "", maxsplit=1)[0].strip()
    if not first:
        return ""
    if _is_corporate(first):
        return clean(first)
    first = clean(first)
    if "," in first:
        return first.split(",", 1)[0].strip()
    parts = first.split()
    return parts[-1] if parts else ""
