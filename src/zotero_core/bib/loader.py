"""Load a directory of per-stream .bib files into staged works.

Both importers globbed `*.bib` sorted, both configured bibtexparser the same
way, and both keyed the stream by the file stem. Only one had an intra-batch
duplicate guard, and only the other had the `uncited-backup` convention. This
has both.
"""

from __future__ import annotations

from pathlib import Path

import bibtexparser
from bibtexparser.bparser import BibTexParser

from ..identity import identity_slug, normalize_doi
from .entry import entry_to_work
from .models import Work

#: Stems skipped unless explicitly included. `uncited-backup.bib` is the
#: holding pen for keys no longer cited; importing it by default would file
#: retired references alongside live ones.
DEFAULT_SKIP_STEMS = ("uncited-backup",)


def _parser() -> BibTexParser:
    parser = BibTexParser(common_strings=True)
    parser.ignore_nonstandard_types = False
    return parser


def _identity(work: Work) -> tuple:
    doi = normalize_doi(work.doi)
    if doi:
        return ("doi", doi)
    return (
        "title-year-creator",
        identity_slug(work.title),
        work.year,
        identity_slug(work.match_creator),
    )


def load_bib_streams(
    bib_dir: str | Path,
    *,
    include_uncited: bool = False,
    strict_types: bool = False,
    skip_stems: tuple[str, ...] = DEFAULT_SKIP_STEMS,
    stream_order: list[str] | None = None,
) -> list[Work]:
    """Load every stream file in the directory.

    ``stream_order`` names stems to read first, in that order -- the order a
    paper's argument runs in, which is not alphabetical. Stems it does not
    name follow, sorted. Naming a stem that does not exist is not an error;
    the paper's outline can run ahead of its bibliography.
    """
    directory = Path(bib_dir).expanduser().resolve()
    if not directory.is_dir():
        raise ValueError(f"Not a directory: {directory}")
    files = sorted(directory.glob("*.bib"))
    if not include_uncited:
        files = [path for path in files if path.stem not in skip_stems]
    if stream_order:
        by_stem = {path.stem: path for path in files}
        ordered = [by_stem[stem] for stem in stream_order if stem in by_stem]
        ordered += [path for path in files if path not in ordered]
        files = ordered
    if not files:
        raise ValueError(f"No .bib files found in {directory}")

    works: list[Work] = []
    seen: dict[tuple, str] = {}
    for path in files:
        database = bibtexparser.loads(path.read_text(encoding="utf-8"), parser=_parser())
        for entry in database.entries:
            work = entry_to_work(entry, path.stem, strict_types=strict_types)
            identity = _identity(work)
            if identity in seen:
                raise ValueError(
                    f"duplicate staged work in {path.name}: {work.title} "
                    f"(already staged from {seen[identity]})"
                )
            seen[identity] = path.name
            works.append(work)
    return works


def load_bib_directory(bib_dir: str | Path, **kwargs) -> list[dict]:
    """:func:`load_bib_streams` in the desktop bridge's wire shape."""
    return [work.to_payload() for work in load_bib_streams(bib_dir, **kwargs)]
