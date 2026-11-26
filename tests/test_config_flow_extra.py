"""Config flow: error branches, duplicates, reauth and reconfigure."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_RECONFIGURE
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.zyxel_router.api import ZyxelApiError, ZyxelSessionBusyError
from custom_components.zyxel_router.const import DOMAIN

USER_INPUT = {
    CONF_HOST: "http://192.168.1.1",
    CONF_USERNAME: "admin",
    CONF_PASSWORD: "secret",
}
VALIDATE = "custom_components.zyxel_router.config_flow._validate"
OTHER_DEVICE = {"SerialNumber": "S999Z99999999", "ModelName": "NR7101"}


@pytest.mark.parametrize(
    ("exc", "err"),
    [
        (ZyxelSessionBusyError("busy"), "session_busy"),
        (ZyxelApiError("api"), "unknown"),
        (ValueError("decrypt"), "unknown"),
    ],
)
async def test_user_flow_more_errors(
    hass: HomeAssistant, mock_client: AsyncMock, exc: Exception, err: str
) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(VALIDATE, side_effect=exc):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": err}
    # the form recovers
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_duplicate_updates_host(
    hass: HomeAssistant, mock_client: AsyncMock, config_entry: MockConfigEntry
) -> None:
    config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**USER_INPUT, CONF_HOST: "http://10.0.0.1"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert config_entry.data[CONF_HOST] == "http://10.0.0.1"


async def test_reauth(
    hass: HomeAssistant, mock_client: AsyncMock, config_entry: MockConfigEntry
) -> None:
    config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_REAUTH, "entry_id": config_entry.entry_id},
        data=config_entry.data,
    )
    assert result["step_id"] == "reauth_confirm"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USERNAME: "admin", CONF_PASSWORD: "new"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert config_entry.data[CONF_PASSWORD] == "new"
    assert config_entry.data[CONF_HOST] == USER_INPUT[CONF_HOST]


async def test_reauth_other_device(
    hass: HomeAssistant, mock_client: AsyncMock, config_entry: MockConfigEntry
) -> None:
    """Credentials of a different router must not be stored on this entry."""
    config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_REAUTH, "entry_id": config_entry.entry_id},
        data=config_entry.data,
    )
    with patch(VALIDATE, return_value=OTHER_DEVICE):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_USERNAME: "admin", CONF_PASSWORD: "new"}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"
    assert config_entry.data[CONF_PASSWORD] == "secret"


async def test_reconfigure_keeps_password(
    hass: HomeAssistant, mock_client: AsyncMock, config_entry: MockConfigEntry
) -> None:
    config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_RECONFIGURE, "entry_id": config_entry.entry_id}
    )
    assert result["step_id"] == "reconfigure"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "https://192.168.1.1", CONF_USERNAME: "admin"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert config_entry.data[CONF_HOST] == "https://192.168.1.1"
    assert config_entry.data[CONF_PASSWORD] == "secret"


async def test_reconfigure_other_device(
    hass: HomeAssistant, mock_client: AsyncMock, config_entry: MockConfigEntry
) -> None:
    config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_RECONFIGURE, "entry_id": config_entry.entry_id}
    )
    with patch(VALIDATE, return_value=OTHER_DEVICE):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {**USER_INPUT, CONF_HOST: "http://10.0.0.2"}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"
    assert config_entry.data[CONF_HOST] == USER_INPUT[CONF_HOST]
