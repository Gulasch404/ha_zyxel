"""Test the config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.zyxel_router.api import ZyxelAuthError, ZyxelConnectionError
from custom_components.zyxel_router.const import DOMAIN

USER_INPUT = {
    CONF_HOST: "http://192.168.1.1",
    CONF_USERNAME: "admin",
    CONF_PASSWORD: "secret",
}


async def test_user_flow(hass: HomeAssistant, mock_client: AsyncMock) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "NR7101 (http://192.168.1.1)"
    assert result["result"].unique_id == "S000Z00000000"


async def test_user_flow_errors(hass: HomeAssistant, mock_client: AsyncMock) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    for exc, err in ((ZyxelAuthError("x"), "invalid_auth"), (ZyxelConnectionError("x"), "cannot_connect")):
        with patch("custom_components.zyxel_router.config_flow._validate", side_effect=exc):
            result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
        assert result["errors"] == {"base": err}


async def test_options_flow(hass: HomeAssistant, mock_client: AsyncMock, config_entry) -> None:
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "scan_interval": 15,
            "slow_interval": 120,
            "allow_cellular_changes": True,
            "revert_timeout": 300,
            "allow_raw_writes": False,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options["allow_cellular_changes"] is True
