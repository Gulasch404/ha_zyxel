"""Privacy: SMS event payload, diagnostics redaction, client attributes."""

from __future__ import annotations

from unittest.mock import AsyncMock

from homeassistant.components.diagnostics import REDACTED
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_capture_events

from custom_components.zyxel_router.const import DOMAIN, EVENT_SMS_RECEIVED
from custom_components.zyxel_router.diagnostics import (
    async_get_config_entry_diagnostics,
    redact,
)

SMS = {"Index": 3, "From": "+431234", "Time": "2026-11-26 08:00", "Content": "code 1234"}


async def _setup(hass: HomeAssistant, entry: MockConfigEntry, **options) -> None:
    entry.add_to_hass(hass)
    if options:
        hass.config_entries.async_update_entry(entry, options=options)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def _receive_sms(hass: HomeAssistant, router, entry: MockConfigEntry) -> list:
    router.objects["cellwan_sms"] = [{"SMS_Inbox": []}]
    await _setup(hass, entry)
    events = async_capture_events(hass, EVENT_SMS_RECEIVED)
    router.objects["cellwan_sms"] = [{"SMS_Inbox": [SMS]}]
    await entry.runtime_data.async_request_full_refresh()
    await hass.async_block_till_done()
    return events


async def test_sms_event_without_content_by_default(
    hass: HomeAssistant, mock_client: AsyncMock, router, config_entry
) -> None:
    events = await _receive_sms(hass, router, config_entry)
    assert len(events) == 1
    data = events[0].data
    assert data == {
        "entry_id": config_entry.entry_id,
        "index": 3,
        "from": "+431234",
        "time": "2026-11-26 08:00",
    }
    assert "code 1234" not in str(data)


async def test_sms_event_with_content_when_enabled(
    hass: HomeAssistant, mock_client: AsyncMock, router, config_entry
) -> None:
    config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(config_entry, options={"sms_content_in_events": True})
    router.objects["cellwan_sms"] = [{"SMS_Inbox": []}]
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    events = async_capture_events(hass, EVENT_SMS_RECEIVED)
    router.objects["cellwan_sms"] = [{"SMS_Inbox": [SMS]}]
    await config_entry.runtime_data.async_request_full_refresh()
    await hass.async_block_till_done()
    assert len(events) == 1
    assert events[0].data["content"] == "code 1234"
    assert set(events[0].data) == {"entry_id", "index", "from", "time", "content"}


async def test_clients_sensor_has_no_host_list(
    hass: HomeAssistant, mock_client: AsyncMock, config_entry
) -> None:
    await _setup(hass, config_entry)
    entity_id = er.async_get(hass).async_get_entity_id("sensor", DOMAIN, "S000Z00000000_clients")
    state = hass.states.get(entity_id)
    assert state is not None
    assert "hosts" not in state.attributes
    assert "02:00:00" not in str(state.attributes)


def test_redact_patterns() -> None:
    raw = {
        "CellAccessPointInfo": [{"Password": "apnpw", "Username": "apnuser", "APN": "internet"}],
        "WWANBackupInfo": {"PIN": "1234", "PUK": "5678", "NewPIN": "", "RemainingPIN": 3},
        "GponInfo": {"EnhancedPSK": "secret", "Password": "gpon", "EquipmentId": "ZYX1"},
        "wifiSsid": [{"X_ZYXEL_MasterMainPassword": "wifi", "Enable": True}],
        "SMS_Inbox": [{"Content": "x"}],
        "Mapping": "keep",
        "PingTest": "keep",
        "UpTime": 42,
        "IPv6Enable": True,
        "USIM_PIN_Protection": False,
    }
    out = redact(raw)
    assert out["CellAccessPointInfo"][0]["Password"] == REDACTED
    assert out["CellAccessPointInfo"][0]["Username"] == REDACTED
    assert out["CellAccessPointInfo"][0]["APN"] == "internet"
    assert out["WWANBackupInfo"]["PIN"] == REDACTED
    assert out["WWANBackupInfo"]["PUK"] == REDACTED
    assert out["WWANBackupInfo"]["NewPIN"] == ""  # empty values stay (like HA core)
    assert out["WWANBackupInfo"]["RemainingPIN"] == REDACTED
    assert out["GponInfo"]["EnhancedPSK"] == REDACTED
    assert out["GponInfo"]["EquipmentId"] == REDACTED
    assert out["wifiSsid"][0]["X_ZYXEL_MasterMainPassword"] == REDACTED
    assert out["wifiSsid"][0]["Enable"] is True
    assert out["SMS_Inbox"] == REDACTED
    assert out["Mapping"] == "keep"
    assert out["PingTest"] == "keep"
    assert out["UpTime"] == 42
    assert out["IPv6Enable"] is True
    assert out["USIM_PIN_Protection"] is False
    assert raw["WWANBackupInfo"]["PIN"] == "1234"  # input untouched


async def test_diagnostics(
    hass: HomeAssistant, mock_client: AsyncMock, config_entry
) -> None:
    await _setup(hass, config_entry)
    diag = await async_get_config_entry_diagnostics(hass, config_entry)
    assert diag["entry"]["password"] == REDACTED
    assert diag["entry"]["host"] == "http://192.168.1.1"
    wlan = diag["raw"]["wlan"][0]
    assert wlan["PskDisplay"] == REDACTED
    assert wlan["CurrentPSKValue"] == REDACTED
    assert wlan["SSID"] == REDACTED
    assert wlan["wlEnable"] is True
    assert diag["raw"]["status"][0]["DeviceInfo"]["SerialNumber"] == REDACTED
    assert diag["menu"] == ["Network > WAN"]
    assert "cellular" in diag["features"]
    # diagnostics must not talk to the router
    mock_client.cgi_get.assert_awaited_once()
