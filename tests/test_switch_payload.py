"""Unit tests for the WLAN PUT payload builder."""

from __future__ import annotations

import pytest
from homeassistant.exceptions import HomeAssistantError

from custom_components.zyxel_router.switch import build_wlan_payload

WPA2 = {
    "Index": 1,
    "wlEnable": True,
    "SSID": "Home",
    "wlHide": False,
    "AutoGenPSK": False,
    "SecurityMode": "WPA2-Personal",
    "PskDisplay": "secret123",
    "RekeyingInterval": 3600,
    "encryp": "aes",
}


def test_wpa2_payload_keeps_settings() -> None:
    payload = build_wlan_payload(WPA2, 1, False)
    assert payload == {
        "Index": 1,
        "wlEnable": False,
        "SSID": "Home",
        "wlHide": False,
        "AutoGenPSK": False,
        "RekeyingInterval": 3600,
        "encryp": "aes",
        "psk_value": "secret123",
        "securityLevel": "MoreSecure",
        "wpaMode": "wpa2psk",
    }


def test_open_network_needs_no_psk() -> None:
    payload = build_wlan_payload({"Index": 2, "SSID": "Guest", "SecurityMode": "None"}, 2, True)
    assert payload["securityLevel"] == "NoSecurity"
    assert "psk_value" not in payload


def test_no_defaults_for_missing_fields() -> None:
    obj = {"SSID": "Home", "SecurityMode": "WPA2-Personal", "CurrentPSKValue": "s"}
    payload = build_wlan_payload(obj, 1, True)
    for key in ("wlHide", "AutoGenPSK", "RekeyingInterval", "encryp"):
        assert key not in payload


@pytest.mark.parametrize(
    "obj",
    [
        {},
        {"SSID": "", "SecurityMode": "None"},
        {"SSID": "Home"},  # security mode missing
        {"SSID": "Home", "SecurityMode": "WPA3-Personal", "PskDisplay": "x"},
        {"SSID": "Home", "SecurityMode": "WEP-64"},
        {"SSID": "Home", "SecurityMode": "WPA2-Personal"},
        {"SSID": "Home", "SecurityMode": "WPA2-Personal", "PskDisplay": "", "CurrentPSKValue": ""},
    ],
)
def test_incomplete_object_is_refused(obj: dict) -> None:
    with pytest.raises(HomeAssistantError):
        build_wlan_payload(obj, 1, False)
