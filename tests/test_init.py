"""Test setup, entities, services and the auto-revert watchdog."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_capture_events

from custom_components.zyxel_router import coordinator as coord_mod
from custom_components.zyxel_router.const import DOMAIN, EVENT_REVERTED


async def _setup(hass: HomeAssistant, entry: MockConfigEntry, **options) -> None:
    entry.add_to_hass(hass)
    if options:
        hass.config_entries.async_update_entry(entry, options=options)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


def _state(hass: HomeAssistant, platform: str, key: str):
    entity_id = er.async_get(hass).async_get_entity_id(platform, DOMAIN, f"S000Z00000000_{key}")
    assert entity_id, key
    return hass.states.get(entity_id)


async def test_setup_and_entities(hass: HomeAssistant, mock_client: AsyncMock, config_entry) -> None:
    await _setup(hass, config_entry)
    assert config_entry.state is ConfigEntryState.LOADED

    assert _state(hass, "sensor", "operator").state == "Magenta-T"
    assert _state(hass, "sensor", "rsrp").state == "-83"
    assert _state(hass, "sensor", "nr_band").state == "n78"
    assert _state(hass, "sensor", "ca_bands").state == "B3+B1+B8+n78"
    assert _state(hass, "sensor", "wan_ipv4").state == "203.0.113.10"
    assert _state(hass, "sensor", "temperature_cpu").state == "28"
    assert _state(hass, "binary_sensor", "wan_connected").state == "on"
    assert _state(hass, "binary_sensor", "band_lock").state == "off"
    assert _state(hass, "switch", "wlan_1").state == "on"
    # cellular controls hidden unless enabled
    reg = er.async_get(hass)
    assert reg.async_get_entity_id("select", DOMAIN, "S000Z00000000_network_mode") is None
    # no SMS on this device
    assert reg.async_get_entity_id("sensor", DOMAIN, "S000Z00000000_sms_inbox") is None

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    mock_client.logout.assert_awaited()


async def test_wlan_switch(hass: HomeAssistant, mock_client: AsyncMock, router, config_entry) -> None:
    await _setup(hass, config_entry)
    state = _state(hass, "switch", "wlan_1")
    await hass.services.async_call("switch", "turn_off", {"entity_id": state.entity_id}, blocking=True)
    method, oid, payload = router.writes[-1]
    assert (method, oid) == ("PUT", "wlan")
    assert payload["Index"] == 1 and payload["wlEnable"] is False
    assert payload["SSID"] == "Zyxel_TEST"


async def test_cellular_change_blocked_by_default(
    hass: HomeAssistant, mock_client: AsyncMock, router, config_entry
) -> None:
    await _setup(hass, config_entry)
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN, "set_preferred_bands", {"bands": ["B3"]}, blocking=True
        )
    assert router.writes == []


async def test_band_lock_confirmed(
    hass: HomeAssistant, mock_client: AsyncMock, router, config_entry
) -> None:
    await _setup(hass, config_entry, allow_cellular_changes=True)
    with (
        patch.object(coord_mod, "WATCHDOG_SETTLE", 0),
        patch.object(coord_mod, "WATCHDOG_POLL", 0),
    ):
        await hass.services.async_call(
            DOMAIN, "set_preferred_bands", {"bands": ["B3", "b1", "n78"]}, blocking=True
        )
        await hass.async_block_till_done(wait_background_tasks=True)
    puts = [w for w in router.writes if w[1] == "cellwan_band"]
    assert len(puts) == 1
    assert puts[0][2]["INTF_Preferred_Bands"] == "LTE_BC1,LTE_BC3,NR_N78"


async def test_band_lock_reverted(
    hass: HomeAssistant, mock_client: AsyncMock, router, config_entry
) -> None:
    await _setup(hass, config_entry, allow_cellular_changes=True, revert_timeout=0)
    events = async_capture_events(hass, EVENT_REVERTED)
    router.connected = False
    with (
        patch.object(coord_mod, "WATCHDOG_SETTLE", 0),
        patch.object(coord_mod, "WATCHDOG_POLL", 0),
    ):
        await hass.services.async_call(
            DOMAIN, "set_preferred_bands", {"bands": ["B20"]}, blocking=True
        )
        await hass.async_block_till_done(wait_background_tasks=True)
    puts = [w[2]["INTF_Preferred_Bands"] for w in router.writes if w[1] == "cellwan_band"]
    assert puts == ["LTE_BC20", "Auto"]  # applied, then restored
    assert len(events) == 1
    assert events[0].data["reverted"] is True
    issue = ir.async_get(hass).async_get_issue(
        DOMAIN, f"cellular_change_reverted_{config_entry.entry_id}"
    )
    assert issue is not None
    assert issue.translation_key == "cellular_change_reverted"
    assert issue.translation_placeholders["change"] == "Bands → LTE_BC20"


async def test_invalid_band_and_anchor(
    hass: HomeAssistant, mock_client: AsyncMock, router, config_entry
) -> None:
    await _setup(hass, config_entry, allow_cellular_changes=True)
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(DOMAIN, "set_preferred_bands", {"bands": ["B99"]}, blocking=True)
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(DOMAIN, "set_preferred_bands", {"bands": ["n78"]}, blocking=True)
    assert router.writes == []


async def test_cell_lock_sequence(
    hass: HomeAssistant, mock_client: AsyncMock, router, config_entry
) -> None:
    await _setup(hass, config_entry, allow_cellular_changes=True)
    with (
        patch.object(coord_mod, "WATCHDOG_SETTLE", 0),
        patch.object(coord_mod, "WATCHDOG_POLL", 0),
    ):
        await hass.services.async_call(
            DOMAIN, "set_cell_lock", {"cells": [{"pci": 400, "earfcn": 1300}]}, blocking=True
        )
        await hass.async_block_till_done(wait_background_tasks=True)
    lock_writes = [w for w in router.writes if w[1] == "cellwan_lock"]
    assert [w[0] for w in lock_writes] == ["POST", "PUT"]
    assert lock_writes[-1][2]["LK_Enable"] is True
    assert lock_writes[-1][2]["LK_LockedList"] == [{"PhyCellID": 400, "RFCN": 1300}]


async def test_dal_get_service(hass: HomeAssistant, mock_client: AsyncMock, config_entry) -> None:
    await _setup(hass, config_entry)
    resp = await hass.services.async_call(
        DOMAIN, "dal_get", {"oid": "cellwan_sim"}, blocking=True, return_response=True
    )
    assert resp["objects"][0]["USIM_Status"] == "DEVST_SIM_RDY"
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN, "dal_set", {"oid": "wlan", "payload": {}}, blocking=True, return_response=True
        )
