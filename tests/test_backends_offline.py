"""Backends must fail legibly when their prerequisite is missing."""

import urllib.error

import pytest

from zotero_core.backends import get_backend
from zotero_core.backends import desktop
from zotero_core.backends.web import resolve_api_key, resolve_library_id
from zotero_core.errors import BackendUnavailable, BridgeNotInstalled, ZoteroUnavailable


def test_unknown_backend_names_the_valid_ones():
    with pytest.raises(BackendUnavailable, match="null, web, desktop"):
        get_backend("carrier-pigeon")


def test_null_backend_reports_an_empty_library():
    backend = get_backend("null")
    assert backend.snapshot_library() == [] and backend.list_collections() == []


def test_null_backend_refuses_to_write():
    with pytest.raises(NotImplementedError):
        get_backend("null").ensure_collection("X", None)


def test_library_id_has_no_default(monkeypatch):
    # A built-in default means someone else's install silently writes at the
    # author's library.
    monkeypatch.delenv("ZOTERO_USER_ID", raising=False)
    with pytest.raises(BackendUnavailable, match="No Zotero library id"):
        resolve_library_id()


def test_library_id_comes_from_the_environment(monkeypatch):
    monkeypatch.setenv("ZOTERO_USER_ID", "123")
    assert resolve_library_id() == "123"
    assert resolve_library_id("456") == "456"


def test_api_key_is_environment_only(monkeypatch):
    monkeypatch.delenv("ZOTERO_API_KEY", raising=False)
    with pytest.raises(BackendUnavailable, match="ZOTERO_API_KEY"):
        resolve_api_key()


def test_missing_bridge_is_not_reported_as_a_connection_problem(monkeypatch):
    def fake_urlopen(*_args, **_kwargs):
        raise urllib.error.HTTPError(
            "http://127.0.0.1:23119/cli-bridge/eval", 404, "Not Found", {}, None
        )

    monkeypatch.setattr(desktop.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(BridgeNotInstalled, match="not installed"):
        desktop.bridge_ping()


def test_zotero_not_running_is_reported_as_such(monkeypatch):
    def fake_urlopen(*_args, **_kwargs):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(desktop.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(ZoteroUnavailable, match="not running"):
        desktop.bridge_ping()


def test_the_snapshot_script_still_reads_the_doi_out_of_extra():
    # Dropping getExtraField("DOI") degrades matching silently for reports and
    # preprints, which is how duplicates get written into a real library.
    assert 'item.getExtraField("DOI")' in desktop.JS_HELPERS
    assert "Zotero.Date.strToDate" in desktop.JS_HELPERS
