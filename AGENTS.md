# Repository instructions

This package exists to be the *only* place certain decisions are made. Most of
the rules below are about not quietly reintroducing a second copy.

## The point of this repository

Four toolchains independently answered the same questions and drifted apart:
two BibTeX importers with conflicting type tables, three creator parsers, two
byte-identical data-directory finders, three sha256 helpers, three title
normalizers. That drift wrote duplicate items into a real library. If you find
yourself writing a second spelling of something here, stop — that is the bug
this repository was created to remove.

## Rules

- **Base dependencies stay at `bibtexparser` alone.** Anything heavier goes
  behind an optional extra. `import zotero_core` — including
  `zotero_core.local` and `zotero_core.backends.desktop` — must succeed on
  Linux with no extras installed. CI enforces this on `ubuntu-latest`.
- **Nothing Windows-specific belongs here.** No `pywinauto`, no `ctypes`
  window handling, no keystroke automation, no hardcoded program paths. Those
  live in `zotero-connector-cli`.
- **No institution-specific anything.** No proxy hosts, no database lists, no
  personal library ids, no default user id. A default library id means someone
  else's install silently writes at the author's library.
- **The API key is read from `ZOTERO_API_KEY` and nowhere else.** Do not add a
  flag, a config file, or a prompt. Do not print it, log it, or write it.
- **The local SQLite route never writes.** Read-only URIs only.
- **Planning stays pure Python.** A backend answers questions
  (`snapshot_library`, `list_collections`, `ensure_collection`,
  `create_items`, `add_to_collection`); it does not decide. Moving a decision
  back into a JS blob recreates the split that made sharing impossible.
- **Keep `normalize_title` and `JS_NORMALIZE_TITLE` in lockstep.** They are
  compared against each other across a process boundary at runtime.
  `tests/test_js_parity.py` runs the real JS under `node`.
- **Do not change `file_sha256`'s lowercase default.** The connector writes
  uppercase digests into `pdf-status.csv` and compares them byte-wise on
  resume; it passes `uppercase=True`. See `docs/consumer-csv-schemas.md`.
- **Do not drop `getExtraField("DOI")` or the `strToDate` year fallback** from
  the desktop snapshot script. DOIs in the Extra field are routine for reports
  and preprints; losing that read degrades matching silently, which is the
  failure mode that writes duplicates while reporting success.

## Conventions

- setuptools, `src/` layout, dashed distribution name, underscored package,
  `[project.scripts]` entry point, MIT, `requires-python = ">=3.10"`.
- pytest, flat `tests/`, no conftest hierarchy beyond the single root one.
- Every test must pass with no Zotero installed, no network, and no
  credential. Use the `zotero_db` fixture (a synthetic `zotero.sqlite`) and
  `FakeBackend`. If a test needs a real library, it does not belong here.
- Ports of behaviour from a front-end come with the test that pins the
  behaviour, and the front-end's copy is deleted in the same change — not
  left behind "for now".

## Related repositories

- `zotero-connector-cli` — Windows PDF retrieval, browser Connector
  automation, batch CSV runs. Depends on this package.
- `skill-zotero-bib` — the Claude skill for importing a paper's per-stream
  `.bib` files. Depends on this package.
- `skill-sanitize-citations`, `prisma-literature-review` — read-only auditing
  and search over the local database. Depend on this package.
- `paperbib`, `inkgest` — bibliography *generation* from DOIs and PDFs. No
  Zotero route; not consumers of this package today.
