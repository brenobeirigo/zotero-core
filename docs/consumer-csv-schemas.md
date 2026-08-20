# Consumer CSV and report schemas, as they exist today

Recorded so that unifying them later starts from a table instead of an
archaeology session. **Nothing in this package reads or writes these files.**
Unifying them is a data migration across a live paper repository and an
assessed student project, with no shared-code prerequisite — it is a separate
piece of work, deliberately not bundled with the consolidation.

Every header below was read from the file on disk, not reconstructed.

## `pdf-status.csv` — input to `zotero-connector batch-csv`

Four run directories under
`paper-cmarp/reference/search/<topic>-<date>/`, three distinct headers:

| Run | Header |
|---|---|
| `task-interaction-skill-taxonomies-2026-08-07` | `zotero_key,doi,title,access_url,status,local_pdf,sha256,retrieval_policy` |
| `truck-trailer-robotic-ontology-2026-08-07` | `zotero_key,doi,title,access_url,status,local_pdf,sha256,retrieval_policy` |
| `multi-entity-configurations-2026-08-08` | `citekey,zotero_key,title,doi,access_url,status,local_pdf,sha256` |
| `coalition-capability-composition-2026-08-15` | `zotero_key,bibtex_key,title,access_url,status,local_pdf,sha256` |

The drift that matters: the citation-key column is absent, then `citekey`,
then `bibtex_key`; `doi` disappears in the newest run; `retrieval_policy` is
present only in the two oldest.

**The `sha256` column holds UPPERCASE digests** and is compared byte-wise when
a batch resumes. `zotero_core.hashing.file_sha256` therefore defaults to
lowercase and takes `uppercase=True`; the connector passes it. Changing that
default silently invalidates every recorded run.

## Student-project schemas

`iem-m1-project/companies/asml-suppliers/2026/`:

| File | Header |
|---|---|
| `zotero-pdf-status.csv` | `company,citation_key,zotero_key,title,source_url,status,sha256,retrieval_policy,attachment_key,linked_filename` |
| `case-studies/benchmark/sources/zotero_import_manifest.csv` | `bib_key,title,item_type,access_url,status,zotero_collection,zotero_key,notes` (quoted) |
| `case-studies/benchmark/sources/zotero_pdf_queue.csv` | `bib_key,pdf_url,pdf_status,attachment_action,notes` |

`case-studies/benchmark/tests/test_case_data.py:208` asserts that the `.bib`
keys equal the `bib_key` column of the manifest. Any migration has to keep
that test passing.

## `zotero-seeds.csv` — output of the PRISMA library search

Frozen 15-column contract, unchanged across runs:

```
item_id,zotero_key,item_type,title,authors,date,year,venue,doi,url,
abstract,tags,matched_queries,matched_in,attachment_paths
```

This one is a genuine interface, not drift. It is preserved byte-for-byte.

## Two unrelated JSON report shapes, side by side

Both live in the same run directory:

- `pdf-status.zotero-connector-report.json` —
  `ok, finished, runId, startedAt, updatedAt, executionMode, csv, reportFile,
  logFile, selected, policyValue, processed, withPDF, withoutPDF,
  interactiveRequired, operationalErrors, results`
- `zotero-import-report.json` —
  `date, parent{name,key}, import{parsed,created,duplicates_created},
  collections[], items[{citekey,key,collection,pdf}], attachment_audit,
  connector_report, final_pdf_count`

Plus `pdf-status.zotero-connector-runs.jsonl`, an append-only event log of
`run-start` / `item` / finish records.

## If this is unified later

A single versioned `pdf_status` schema with a `schema_version` column, an
explicit `citation_key` name (retiring `citekey` / `bibtex_key` / `bib_key`),
and a reader that accepts every historical header. Deliberately **not** in
v0.1: a report writer would be a fifth route into this package, and the four
it has are the ones the duplication justified.
