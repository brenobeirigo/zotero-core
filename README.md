# zotero-core

One definition of what a work is, shared by every tool that touches a Zotero
library.

Four separate toolchains grew their own answers to the same questions — how a
BibTeX entry maps to a Zotero item, when two records are the same work, where
Zotero keeps its database. The answers drifted, and the drift produced
duplicates. This package holds the single answer; the tools become thin
front-ends over it.

## Requirements

- Python 3.10+
- `bibtexparser` (installed automatically) — that is the whole base dependency
- Optional, per route: `pyzotero` for the Web API; Zotero Desktop plus the
  Zotero CLI Bridge for desktop writes; a local Zotero installation for the
  read-only SQLite route

The core imports and runs on any platform with no optional dependency
installed. Nothing here needs Windows.

## Install

```powershell
python -m pip install -e c:\dev\repos\zotero\zotero-core          # core only
python -m pip install -e "c:\dev\repos\zotero\zotero-core[web]"   # + Web API
python -m pip install -e "c:\dev\repos\zotero\zotero-core[dev]"   # + pytest
```

## Usage

Plan an import without a credential, a network connection, or Zotero
installed — a complete, reviewable plan against an empty library:

```powershell
zotero-core plan-import --bib-dir docs\bib --parent-name "My Paper"
```

Plan against your real library, read-only, straight from Zotero's database —
no API key and no bridge:

```powershell
zotero-core plan-import --bib-dir docs\bib --parent-name "My Paper" `
    --snapshot-from local-sqlite
```

Apply it:

```powershell
$env:ZOTERO_API_KEY = "<write-enabled key>"
$env:ZOTERO_USER_ID = "<your numeric user id>"
zotero-core import --bib-dir docs\bib --parent-name "My Paper" --backend web
```

Check what this machine can reach:

```powershell
zotero-core doctor
```

As a library:

```python
from zotero_core.bib import load_bib_streams
from zotero_core.plan import plan_import
from zotero_core.backends.sqlite import read_snapshot

works = load_bib_streams("docs/bib")
items, collections, mode = read_snapshot()
plan = plan_import(works, "My Paper", snapshot=items, collections=collections)
print(plan.counts)
```

## What it does

- **BibTeX to Zotero** — one type table, one creator parser, one field
  mapping. `@misc` is dispatched on its contents rather than mapped to a fixed
  type, because an arXiv entry with an `eprint` and a company page with a
  `url` are not the same thing.
- **Work identity** — one DOI normalizer, one title normalizer (Unicode-safe,
  and kept in lockstep with its JavaScript twin), one citation-key pattern.
- **Matching** — a documented ladder: DOI, then citation key **library-wide**,
  then title/year/creator, then title/year. More than one match at the
  deciding rule is a reported conflict, never an automatic merge.
- **Planning** — decided in Python for every route, so the Web API and the
  desktop bridge cannot disagree about what an import would do.
- **Repair** — `zotero_core.dedup` walks that same ladder over a library that
  has already been imported into twice, groups the copies, and picks which one
  should survive. Only DOI and citation-key groups are proposed for merging; a
  title match is reported for a person to decide. Importing and repairing
  therefore cannot disagree about what "the same work" means.
- **Local access** — Zotero's data directory, a read-only connection that
  survives the app holding a lock, attachment path resolution.

## What it does not do

- No PDF retrieval, no browser automation, no window handling. That is
  [zotero-connector-cli](https://github.com/brenobeirigo/zotero-connector-cli).
- No bibliography *generation* from DOIs or PDFs. That is `paperbib` and
  `inkgest`.
- No writing to Zotero's SQLite database, ever. The local route is read-only
  by construction.
- No credential handling beyond reading `ZOTERO_API_KEY` from the environment.
  There is no `--api-key` flag and no default library id.

## Agents

Working on this repository: read [AGENTS.md](AGENTS.md).
Choosing a route, or debugging one that will not connect:
read [docs/backends.md](docs/backends.md).

## License

MIT.
