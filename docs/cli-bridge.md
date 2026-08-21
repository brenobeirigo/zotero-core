# The Zotero CLI Bridge

Every desktop **write** in this package goes through
`POST http://127.0.0.1:23119/cli-bridge/eval`. Stock Zotero does not serve
that endpoint. It comes from a Zotero plugin that this project does not own,
does not vendor, and does not ship.

This file records what that plugin is, how to install and upgrade it, which
versions are tested, and — the part that matters most — what it lets a local
process do.

## What it is

| | |
|---|---|
| Plugin id | `cli-bridge@cli-anything.dev` |
| Plugin name | CLI Bridge for Zotero |
| Distributed in | the PyPI package [`cli-anything-zotero`](https://pypi.org/project/cli-anything-zotero/) |
| Source | <https://github.com/PiaoyangGuohai1/cli-anything-zotero> (`cli_anything/zotero/plugin/zotero-cli-bridge/`) |
| Licence | Apache-2.0 |
| Zotero range | 7.0 – 9.0.x (`strict_min_version` 6.999, `strict_max_version` 9.0.*) |
| Tested minimum here | 1.2.0 — `MIN_BRIDGE_VERSION` in `backends/desktop.py` |

The plugin is roughly seventy lines. It registers one endpoint whose `init`
runs `eval("(async () => {" + options.data + "})()")` and returns the result
as JSON. That is the entire mechanism: this package sends JavaScript, Zotero
runs it with full privileges, and the value comes back.

## Installing it

```powershell
python -m pip install cli-anything-zotero
zotero-cli app install-plugin          # builds the .xpi and prints its path
```

Then, once, by hand in Zotero: **Tools → Plugins → gear icon → Install Plugin
From File…**, choose the printed `.xpi`, and restart Zotero.

## Upgrading it

```powershell
python -m pip install -U cli-anything-zotero
zotero-cli app install-plugin
```

**Zotero's own auto-update does not work for this plugin.** Its manifest
points `update_url` at
`https://raw.githubusercontent.com/PiaoyangGuohai1/cli-anything-zotero/main/update.json`,
which returns 404. Treat upgrades as manual and driven by pip; do not expect
Zotero to notice a new version on its own.

## Checking what is installed

```python
from zotero_core.backends.desktop import bridge_info

report = bridge_info()      # asks the plugin about itself
print(report["ok"], report["bridgeVersion"], report["problems"])
```

`bridge_info()` reports the Zotero version, whether the endpoint is
registered, and the plugin's own id, version and active state. It does not
infer "the bridge is fine" from the endpoint answering: a stale bridge answers
exactly like a current one, right up to the first call that needs behavior it
does not have.

`zotero-connector doctor` prints the same report.

## What this endpoint actually permits

Read this before deciding the bridge is a harmless convenience.

- **It executes arbitrary privileged JavaScript.** There is no command
  vocabulary and no allow-list. Anything Zotero's own code can do — read every
  item, rewrite them, delete them, reach the filesystem through Zotero's
  APIs — the endpoint can be asked to do.
- **It has no authentication.** There is no token, no shared secret, and no
  per-caller identity. The only thing standing between a local process and
  your library is that it has to know the URL.
- **Its access control is "local only", and that is all.** Zotero's HTTP
  server listens on `127.0.0.1`, so the endpoint is not reachable from another
  machine. Every process running as you on this machine can reach it.
- **It accepts `text/plain`.** The plugin declares
  `supportedDataTypes: ["text/plain"]`, which is a CORS-simple content type,
  so a cross-origin `POST` from a web page does not trigger a preflight. The
  plugin does set `permitBookmarklet: false`. Whether Zotero's server rejects
  such a request on other grounds is a property of Zotero's server, not of
  this plugin, and this project has not verified it. Do not assume a browser
  tab cannot reach this endpoint.

The practical consequence: install the bridge on a machine you control, and
treat "the bridge is running" as equivalent to "any local program may rewrite
my Zotero library". Quit Zotero when you are not using the write commands.

## Why this package does not vendor it

The licence would permit it. Two things argue against it: a copy here would
silently drift from the upstream the plugin's own installer keeps current, and
this project would then be shipping a privileged-eval endpoint under its own
name. Pinning an id, checking a version, and documenting the risk is the
honest arrangement — `zotero-connector-cli`'s `TODO.md` no longer carries this
as a blocker because the component is now identified and verifiable, not
because it became ours.
