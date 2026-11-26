"""Watchdog cancellation, stale entities, stale data and small helpers."""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.zyxel_router import coordinator as coord_mod
from custom_components.zyxel_router.api import ZyxelApiError, _summary
from custom_components.zyxel_router.const import DOMAIN
from custom_components.zyxel_router.sensor import _sim_status


async def _setup(hass: HomeAssistant, entry: MockConfigEntry, **options) -> None:
    entry.add_to_hass(hass)
    if options:
        hass.config_entries.async_update_entry(entry, options=options)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


def _entity(hass: HomeAssistant, platform: str, key: str) -> str | None:
    return er.async_get(hass).async_get_entity_id(platform, DOMAIN, f"S000Z00000000_{key}")


async def test_watchdog_cancelled_on_unload_warns(
    hass: HomeAssistant, mock_client: AsyncMock, router, config_entry, caplog
) -> None:
    """Unloading while a change is pending must not pass silently."""
    await _setup(hass, config_entry, allow_cellular_changes=True)
    # settle time far in the future: the watchdog is still sleeping on unload
    with patch.object(coord_mod, "WATCHDOG_SETTLE", 3600):
        await hass.services.async_call(
            DOMAIN, "set_preferred_bands", {"bands": ["B3"]}, blocking=True
        )
        assert config_entry.runtime_data.watchdog_active is True
        with caplog.at_level(logging.WARNING):
            assert await hass.config_entries.async_unload(config_entry.entry_id)
            await hass.async_block_till_done()
    assert "NOT verified" in caplog.text
    assert [w for w in router.writes if w[1] == "cellwan_band"][-1][2]["INTF_Preferred_Bands"] == "LTE_BC3"


async def test_option_gated_entities_removed_when_disabled(
    hass: HomeAssistant, mock_client: AsyncMock, config_entry
) -> None:
    await _setup(hass, config_entry, allow_cellular_changes=True)
    assert _entity(hass, "select", "network_mode")
    assert _entity(hass, "switch", "roaming_switch")

    hass.config_entries.async_update_entry(config_entry, options={"allow_cellular_changes": False})
    await hass.async_block_till_done()  # options listener reloads the entry
    assert config_entry.runtime_data.allow_cellular_changes is False
    assert _entity(hass, "select", "network_mode") is None
    assert _entity(hass, "switch", "roaming_switch") is None


async def test_stale_object_cleared_on_error(
    hass: HomeAssistant, mock_client: AsyncMock, router, config_entry
) -> None:
    await _setup(hass, config_entry)
    sim = hass.states.get(_entity(hass, "sensor", "sim_status"))
    assert sim.state == "ready"

    orig = router.dal_get

    async def failing(oid: str):
        if oid == "cellwan_sim":
            raise ZyxelApiError("boom")
        return await orig(oid)

    mock_client.dal_get.side_effect = failing
    await config_entry.runtime_data.async_request_full_refresh()
    await hass.async_block_till_done()
    # cellwan (fast) still carries USIM_Status on the NR7101, so test via raw data
    assert "cellwan_sim" not in config_entry.runtime_data.data.raw
    assert "cellwan_sim" not in config_entry.runtime_data.unsupported_oids


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("DEVST_SIM_RDY", "ready"),
        ("DEVST_SIM_PIN", "pin_required"),
        ("DEVST_SIM_SOMETHING_NEW", "error"),
        ("", None),
        (None, None),
    ],
)
def test_sim_status_enum(raw, expected) -> None:
    assert _sim_status(raw) == expected


def test_response_summary_hides_bodies() -> None:
    assert _summary({"result": "ZCFG_FAIL", "ReplyMsg": "bad", "secret": "x"}) == (
        "result=ZCFG_FAIL, ReplyMsg=bad"
    )
    assert _summary("<html><body>login page with token abc</body></html>") == "non-JSON response"
    assert _summary({"other": 1}) == "unexpected JSON response"
    assert "x" * 121 not in _summary("x" * 500)
