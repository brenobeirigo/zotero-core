"""BibTeX parsing and mapping into Zotero's vocabulary."""

from .creators import clean, first_creator_match, parse_creators
from .entry import entry_to_work
from .loader import load_bib_directory, load_bib_streams
from .models import Work
from .types import TYPE_MAP, YEAR_REQUIRED, check_required, resolve_item_type

__all__ = [
    "TYPE_MAP",
    "YEAR_REQUIRED",
    "Work",
    "check_required",
    "clean",
    "entry_to_work",
    "first_creator_match",
    "load_bib_directory",
    "load_bib_streams",
    "parse_creators",
    "resolve_item_type",
]
