"""zotero-core: plan and apply BibTeX imports, and diagnose the environment.

Deliberately three commands. Item lookup and library search stay in the
front-ends that own their output contracts (exit codes, frozen CSV columns) --
reimplementing them here would put back the duplication this package exists to
remove.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .backends import get_backend
from .bib.loader import load_bib_streams
from .errors import ZoteroCoreError
from .plan.applier import apply_plan
from .plan.planner import plan_import

SNAPSHOT_SOURCES = ("none", "local-sqlite", "web", "desktop")


def _add_planning_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--bib-dir", required=True, type=Path)
    parser.add_argument("--parent-name", required=True)
    parser.add_argument("--flat", action="store_true",
                        help="one flat project collection instead of per-stream children")
    parser.add_argument("--include-uncited", action="store_true",
                        help="also import uncited-backup.bib")
    parser.add_argument("--strict-types", action="store_true",
                        help="fail instead of guessing an item type for a bare @misc entry")
    parser.add_argument("--library-id", default=None,
                        help="Zotero library id for the web backend (else ZOTERO_USER_ID)")
    parser.add_argument("--json", action="store_true")


def _load(args):
    return load_bib_streams(
        args.bib_dir,
        include_uncited=args.include_uncited,
        strict_types=args.strict_types,
    )


def _plan(args, source: str):
    works = _load(args)
    if source == "none":
        return plan_import(works, args.parent_name, flat=args.flat)
    if source == "local-sqlite":
        from .backends.sqlite import read_snapshot

        items, collections, mode = read_snapshot()
        print(f"snapshot: local sqlite ({mode}), {len(items)} items", file=sys.stderr)
        return plan_import(
            works, args.parent_name, snapshot=items, collections=collections, flat=args.flat
        )
    backend = get_backend(source, **({"library_id": args.library_id} if source == "web" else {}))
    return plan_import(works, args.parent_name, backend=backend, flat=args.flat)


def _render(plan, as_json: bool) -> None:
    if as_json:
        print(json.dumps(plan.to_dict(), indent=2, ensure_ascii=False))
        return
    counts = plan.counts
    scope = "offline (empty library assumed)" if plan.offline else "against the library"
    print(f"Parsed {plan.parsed} entries for project {plan.parent_name!r}, planned {scope}.")
    for collection in plan.collections:
        state = "reuse" if collection.exists else "CREATE"
        print(f"  {state:6} {collection.name}")
    for action, count in counts.items():
        if count:
            print(f"  {action}: {count}")
    for conflict in plan.conflicts:
        print(f"  CONFLICT {conflict.citation_key}: {conflict.reason} "
              f"({', '.join(conflict.item_keys)})")
    for row in plan.rows:
        if row.action == "needs-review":
            print(f"  REVIEW {row.citation_key}: {row.note}")


def command_doctor(args) -> int:
    report = {
        "version": __version__,
        "python": sys.version.split()[0],
        "executable": sys.executable,
    }
    try:
        import pyzotero  # noqa: F401

        report["pyzotero"] = "installed"
    except ModuleNotFoundError:
        report["pyzotero"] = "missing (pip install zotero-core[web])"

    from .local.datadir import find_data_dir, machine_attachment_root

    data_dir = find_data_dir()
    report["data_dir"] = str(data_dir) if data_dir else "not found"
    root = machine_attachment_root()
    report["attachment_root"] = str(root) if root else "not configured"

    from .backends.desktop import bridge_ping

    try:
        report["bridge"] = bridge_ping()
    except ZoteroCoreError as exc:
        report["bridge"] = f"{type(exc).__name__}: {exc}"

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        for key, value in report.items():
            print(f"{key}: {value}")
    return 0


def command_plan_import(args) -> int:
    plan = _plan(args, args.snapshot_from)
    _render(plan, args.json)
    return 0 if plan.ok else 1


def command_import(args) -> int:
    plan = _plan(args, args.backend)
    if not plan.ok:
        _render(plan, args.json)
        print("Refusing to write while conflicts are unresolved.", file=sys.stderr)
        return 1
    backend = get_backend(
        args.backend, **({"library_id": args.library_id} if args.backend == "web" else {})
    )
    apply_plan(plan, backend)
    _render(plan, args.json)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="zotero-core", description=__doc__)
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    doctor = sub.add_parser("doctor", help="report what this environment can reach")
    doctor.add_argument("--json", action="store_true")
    doctor.set_defaults(func=command_doctor)

    planner = sub.add_parser("plan-import", help="decide what an import would do, writing nothing")
    _add_planning_flags(planner)
    planner.add_argument("--snapshot-from", choices=SNAPSHOT_SOURCES, default="none")
    planner.set_defaults(func=command_plan_import)

    importer = sub.add_parser("import", help="apply an import")
    _add_planning_flags(importer)
    importer.add_argument("--backend", choices=("web", "desktop"), required=True)
    importer.set_defaults(func=command_import)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except ZoteroCoreError as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
