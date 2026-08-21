# Backends: what each route needs, and how it fails

Four routes reach the same Zotero library. This package speaks all four so
that the tools built on it do not each grow their own client.

| Route | Module | Reads | Writes | Prerequisite |
|---|---|---|---|---|
| Web API | `backends/web.py` | yes | yes | `pip install "zotero-core[web]"`, `ZOTERO_API_KEY`, `ZOTERO_USER_ID`, Zotero sync enabled |
| Desktop bridge | `backends/desktop.py` | yes | yes | Zotero Desktop running **and** the Zotero CLI Bridge installed — see below |
| Local SQLite | `backends/sqlite.py` | yes | **never** | a Zotero installation on this machine |
| Nothing | `backends/null.py` | empty | never | none — this is the offline plan |

Only the first two are backends in the protocol sense. `sqlite.py` is a
*snapshot source*: it can tell you what is in the library, and it cannot
write. That is a feature — planning an import against the real library needs
no key, no bridge, and no full-library dump over HTTP.

## Credentials

The Web API key is read from `ZOTERO_API_KEY` **only**. There is no
`--api-key` flag, and there never will be: a key on a command line lands in
shell history, in process listings, and in any log that captures a command.

There is **no default library id**. `--library-id`, then `ZOTERO_USER_ID`,
then a hard error naming where to find yours. A built-in default means
somebody else's install silently writes at the author's library.

## The Zotero CLI Bridge is a third-party plugin

The desktop backend writes through `POST http://127.0.0.1:23119/cli-bridge/eval`,
an endpoint that **stock Zotero does not provide**. It comes from the
`cli-bridge@cli-anything.dev` plugin, distributed inside the PyPI package
`cli-anything-zotero` and deliberately not vendored here.
[`cli-bridge.md`](cli-bridge.md) covers installation, the manual upgrade path,
the tested version range, and what the endpoint permits — read it before
installing, because the endpoint evaluates arbitrary privileged JavaScript for
any local caller.

The consequence for this package is that on a machine without the bridge,
every desktop *write* is unavailable. Reads via `backends/sqlite.py` still
work, and planning still works.

`backends.desktop.bridge_info()` reports which plugin is answering and whether
its version is one this package has been tested against.

So the two failures are told apart deliberately:

| What happened | What you get |
|---|---|
| Nothing listening on `127.0.0.1:23119` | `ZoteroUnavailable: Zotero Desktop is not running...` |
| Zotero answers, `/cli-bridge/eval` returns 404 | `BridgeNotInstalled: Zotero is running, but the Zotero CLI Bridge endpoint is not installed...` |
| The bridge ran the script and it threw | `BridgeError` carrying the script's own message |

One message covering the first two cases is what made this blocker feel like
a mystery instead of a missing component.

## Why planning is Python, not JavaScript

The desktop route used to compute the whole import plan inside a ~150-line
script running in Zotero, while the Web API route computed its own in Python.
Two implementations of one decision, already disagreeing about item types and
about what counts as a duplicate.

Now a backend answers five questions — `snapshot_library`, `list_collections`,
`ensure_collection`, `create_items`, `add_to_collection` — and
`zotero_core.plan.planner` decides. The JS that survives is the part that only
Zotero can do: reading the live object model, and applying writes in one
`Zotero.DB.executeTransaction`.

Two expressions in that surviving JS are copied verbatim and must stay that
way:

```js
const doiOf = item => cleanDOI(item.getField("DOI") || item.getExtraField("DOI"));
const yearOf = item => { /* Zotero.Date.strToDate, then a \b(19|20)\d{2}\b fallback */ };
```

DOIs stashed in the Extra field are routine for reports and preprints.
Dropping `getExtraField("DOI")` degrades matching silently — the run reports
success and writes duplicates. `tests/test_backends_offline.py` asserts both
expressions are still present.

## The Python and JS normalizers must agree

`identity.normalize_title` and `identity.JS_NORMALIZE_TITLE` are the same
definition in two languages, because entries normalized in Python are compared
against items normalized in JS. `tests/test_js_parity.py` runs the actual JS
under `node` and asserts character-for-character agreement; without it,
`Zürich` and `Zurich` quietly become different works.
