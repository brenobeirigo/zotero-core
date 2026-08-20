"""Planning must not touch the network. Enforced, not merely intended."""

import socket

from zotero_core.bib.loader import load_bib_streams
from zotero_core.plan.planner import plan_import

from conftest import CORPUS


def test_offline_planning_opens_no_socket(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("planning attempted a network connection")

    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)

    plan = plan_import(load_bib_streams(CORPUS), "Project")
    assert plan.parsed > 0 and plan.ok
