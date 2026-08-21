# Releasing

The rule this process exists to enforce: **a tag is a claim that the version
in the tag, the version in `pyproject.toml`, and the version in
`__init__.py` are the same string.** A test asserts the last two agree, and
the release workflow refuses a tag that disagrees with either. Two of those
three drifting apart is the failure that makes a published package impossible
to reason about later.

Nothing here is published to PyPI. `zotero-connector-cli` is installed from a
git URL in CI and editable everywhere else, and there is no reason to occupy a
name on an index for a package with one user. The workflow builds a wheel and
an sdist anyway and attaches them to the GitHub Release, so an install by URL
resolves to a specific, downloadable artifact.

## Cutting a release

1. Update `CHANGELOG.md`: retitle `[Unreleased]` as the new version with
   today's date, and open a fresh `[Unreleased]`. Update the link definitions
   at the bottom.
2. Set the version in **both** places:
   - `pyproject.toml` → `[project] version`
   - `src/zotero_core/__init__.py` → `__version__`
3. Run the checks locally:
   ```powershell
   python -m pytest -q
   python -m build
   python -m pip_audit --strict
   ```
4. Commit, then tag and push:
   ```powershell
   git commit -am "Release 0.2.0"
   git tag v0.2.0
   git push && git push --tags
   ```

Pushing the tag runs `.github/workflows/release.yml`, which re-runs the tests,
verifies the tag against both version strings, builds the artifacts, and
creates the GitHub Release with the changelog section as its body.

## Version policy

Pre-1.0, so the middle number carries breaking changes.

- **Patch** — a fix that does not change what a caller may rely on.
- **Minor** — new capability, or a change to what a backend or a plan
  contains. Adding a required method to the `Backend` protocol is minor
  pre-1.0 and would be major after.
- **Major** — reserved for 1.0, which this package should not reach until the
  bridge situation is settled enough that the desktop route is not the odd one
  out.

Changing what a write does to a library is never a patch, however small the
diff. `merge_items` learning to reparent child items was a fix in the sense
that the old behavior was wrong, and a minor release in the sense that anyone
depending on the old behavior would notice.

## Dependency audit

CI runs `pip-audit` on every push and on a weekly schedule, against the
resolved dependency set including the `web` extra. It is advisory on the
schedule and blocking on a release tag: a known vulnerability should not first
be discovered by the person installing the wheel.

The runtime dependency surface is deliberately small — `bibtexparser` for the
core, `pyzotero` only under the `web` extra. Anything that grows it should be
argued for in the pull request that adds it.
