# Changelog

Notable changes to `zotero-core`. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Because the desktop backend drives someone's real library, entries here name
the behavior that changed, not only the code that moved.

## [Unreleased]

### Added

- `zotero_core.dedup`: grouping a library's existing duplicates and deciding
  which copy survives, walking the same match ladder the importer walks. Only
  DOI and citation-key groups are proposed for merging; a title match is
  reported for a person to decide.
- `Backend.merge_items` and `Backend.trash_items`. The Web API backend raises
  `MergeUnsupported` rather than approximating a merge by deleting the loser.
- `backends.desktop.bridge_info()`: reports which plugin is serving
  `/cli-bridge/eval`, its version, and whether it is one this package has been
  tested against.
- `docs/cli-bridge.md`: what the bridge is, where it comes from, how to
  install and upgrade it, and what its endpoint permits.

### Fixed

- Merging no longer relies on `Zotero.Items.merge` to reparent child items. On
  Zotero 9.0.6 it does not, and attachments followed the losing items into the
  trash — routinely the only copy of a PDF. The merge script moves children
  across itself and refuses to finish if any are left behind.
- `bridge_info()` reported an empty platform on every call: `Zotero.platform`
  does not exist in Zotero 9. It reads `Services.appinfo.OS` now.

### Changed

- `docs/backends.md` no longer describes the CLI Bridge as undistributed. It
  is a third-party plugin with a known source, licence and install path.

## [0.1.0] - 2026-08-20

### Added

- First release. Four Zotero toolchains consolidated into one library so that
  BibTeX identity, item typing, duplicate matching and import planning have a
  single definition rather than four drifting ones.
- BibTeX loading with `@misc` dispatched on its contents, one creator parser,
  one field mapping.
- Work identity: one DOI normalizer, one Unicode-safe title normalizer kept in
  lockstep with its JavaScript twin, one citation-key pattern.
- The match ladder: DOI, citation key library-wide, title/year/creator,
  title/year. More than one match at the deciding rule is a reported conflict,
  never an automatic merge.
- Import planning in Python for every route, so the Web API and the desktop
  bridge cannot disagree about what an import would do.
- Backends: Web API, Zotero Desktop via the CLI Bridge, read-only local
  SQLite, and a null backend for planning with no credential at all.

[Unreleased]: https://github.com/brenobeirigo/zotero-core/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/brenobeirigo/zotero-core/releases/tag/v0.1.0
