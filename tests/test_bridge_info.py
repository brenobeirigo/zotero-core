import pytest

from zotero_core.backends.desktop import (
    BRIDGE_ADDON_ID,
    BRIDGE_PATH,
    MIN_BRIDGE_VERSION,
    _version_tuple,
    describe_bridge,
)


def report(**overrides):
    payload = {
        "zoteroVersion": "9.0.6",
        "platform": "win",
        "libraryID": 1,
        "endpointRegistered": True,
        "addon": {
            "id": BRIDGE_ADDON_ID,
            "name": "CLI Bridge for Zotero",
            "version": "1.2.0",
            "active": True,
            "updateURL": None,
        },
    }
    payload.update(overrides)
    return payload


@pytest.mark.parametrize(
    "value, expected",
    [
        ("1.2.0", (1, 2, 0)),
        ("9.0.6", (9, 0, 6)),
        ("1.2", (1, 2)),
        ("", ()),
        ("abc", ()),
        # Pre-release noise ends the version. Reading this as (1, 2, 0, 3)
        # would rank a beta above the release it precedes.
        ("1.2.0-beta.3", (1, 2, 0)),
        ("1.2.0rc1", (1, 2, 0)),
    ],
)
def test_version_parsing_stops_at_the_first_non_numeric_part(value, expected):
    assert _version_tuple(value) == expected


def test_a_current_bridge_on_a_supported_zotero_is_ok():
    verdict = describe_bridge(report())

    assert verdict["ok"] is True
    assert verdict["problems"] == []
    assert verdict["bridgeVersion"] == "1.2.0"
    assert verdict["bridgeActive"] is True
    assert verdict["endpoint"] == BRIDGE_PATH


def test_an_unregistered_endpoint_is_reported():
    verdict = describe_bridge(report(endpointRegistered=False))

    assert verdict["ok"] is False
    assert any("not registered" in problem for problem in verdict["problems"])


def test_a_missing_plugin_is_not_mistaken_for_a_working_bridge():
    # The endpoint answered -- that is how we got a payload at all -- but no
    # plugin claims it. Something else is serving the path.
    verdict = describe_bridge(report(addon=None))

    assert verdict["ok"] is False
    assert verdict["bridgeVersion"] == ""
    assert verdict["versionKnown"] is False
    assert any(BRIDGE_ADDON_ID in problem for problem in verdict["problems"])


def test_an_unaskable_addon_manager_is_not_reported_as_a_missing_plugin():
    # "Could not ask" and "not installed" are different facts. Reporting the
    # first as the second sends someone reinstalling a plugin that is fine.
    verdict = describe_bridge(
        report(addon=None, addonQueryError="ChromeUtils is not defined")
    )

    assert verdict["ok"] is False
    assert verdict["versionKnown"] is False
    problem = "\n".join(verdict["problems"])
    assert "could not read the plugin's version" in problem
    assert "unverified" in problem
    assert BRIDGE_ADDON_ID not in problem


def test_a_known_version_is_marked_as_known():
    assert describe_bridge(report())["versionKnown"] is True


def test_an_installed_but_disabled_plugin_is_reported():
    verdict = describe_bridge(report(addon={**report()["addon"], "active": False}))

    assert verdict["ok"] is False
    assert any("not active" in problem for problem in verdict["problems"])


def test_a_bridge_older_than_the_tested_minimum_says_how_to_upgrade():
    verdict = describe_bridge(report(addon={**report()["addon"], "version": "1.1.0"}))

    assert verdict["ok"] is False
    problem = "\n".join(verdict["problems"])
    assert "older than the tested minimum" in problem
    assert "cli-anything-zotero" in problem
    assert "install-plugin" in problem


def test_a_bridge_newer_than_the_tested_minimum_is_accepted():
    verdict = describe_bridge(report(addon={**report()["addon"], "version": "1.9.0"}))

    assert verdict["ok"] is True


def test_the_tested_minimum_is_not_quietly_below_what_is_documented():
    # Guards the pin itself: lowering it is a decision, not a side effect.
    assert MIN_BRIDGE_VERSION >= (1, 2, 0)


@pytest.mark.parametrize("version", ["6.0.27", "10.0"])
def test_a_zotero_outside_the_plugins_declared_range_is_reported(version):
    verdict = describe_bridge(report(zoteroVersion=version))

    assert verdict["ok"] is False
    assert any("outside the" in problem for problem in verdict["problems"])


@pytest.mark.parametrize("version", ["7.0.9", "8.0.1", "9.0.6"])
def test_every_zotero_the_plugin_declares_is_accepted(version):
    assert describe_bridge(report(zoteroVersion=version))["ok"] is True


def test_an_unreadable_zotero_version_does_not_invent_a_range_problem():
    verdict = describe_bridge(report(zoteroVersion=""))

    assert not any("outside the" in problem for problem in verdict["problems"])
