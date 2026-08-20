"""Error taxonomy shared by every front-end.

The distinction that matters most is between "Zotero is not running" and
"Zotero is running but the CLI Bridge is not installed". Those have different
remedies, and conflating them is the single most confusing failure this
tooling produces.
"""

from __future__ import annotations


class ZoteroCoreError(RuntimeError):
    """Base class for every error this package raises deliberately."""


class ZoteroUnavailable(ZoteroCoreError):
    """Zotero Desktop is not listening on the local port."""


class BridgeNotInstalled(ZoteroCoreError):
    """Zotero answers, but the CLI Bridge write endpoint is absent."""


class BridgeError(ZoteroCoreError):
    """The bridge ran the script and reported an error."""


class BackendUnavailable(ZoteroCoreError):
    """A backend was requested whose optional dependency is not installed."""


class AmbiguousMatch(ZoteroCoreError):
    """One staged work matched more than one library item."""


class UnsupportedEntryType(ZoteroCoreError):
    """A BibTeX entry type has no Zotero item type, and guessing is refused."""


class IncompleteEntry(ZoteroCoreError):
    """A BibTeX entry lacks a field its resolved item type requires."""
