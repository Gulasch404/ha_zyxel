"""Config flow for Zyxel Router."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_SCAN_INTERVAL, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers import selector

from .api import ZyxelAuthError, ZyxelConnectionError, ZyxelError
from .const import (
    CONF_ALLOW_CELLULAR_CHANGES,
    CONF_ALLOW_RAW_WRITES,
    CONF_REVERT_TIMEOUT,
    CONF_SLOW_INTERVAL,
    CONF_VERIFY_SSL,
    DEFAULT_HOST,
    DEFAULT_REVERT_TIMEOUT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SLOW_INTERVAL,
    DEFAULT_USERNAME,
    DOMAIN,
    MIN_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


async def _validate(hass, data: dict[str, Any]) -> dict[str, Any]:
    """Log in and return the device info."""
    from . import create_client

    client = create_client(hass, data)
    try:
        await client.login()
        status = await client.dal_get_one("status")
    finally:
        await client.logout()
        await client.close()
    return status.get("DeviceInfo") or {}


def _user_schema(defaults: Mapping[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=defaults.get(CONF_HOST, DEFAULT_HOST)): str,
            vol.Required(
                CONF_USERNAME, default=defaults.get(CONF_USERNAME, DEFAULT_USERNAME)
            ): str,
            vol.Required(CONF_PASSWORD): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
            ),
            vol.Optional(
                CONF_VERIFY_SSL, default=defaults.get(CONF_VERIFY_SSL, False)
            ): bool,
        }
    )


class ZyxelConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    async def _try(self, data: dict[str, Any], errors: dict[str, str]) -> dict[str, Any] | None:
        try:
            return await _validate(self.hass, data)
        except ZyxelAuthError:
            errors["base"] = "invalid_auth"
        except ZyxelConnectionError:
            errors["base"] = "cannot_connect"
        except ZyxelError:
            _LOGGER.exception("Unexpected Zyxel error")
            errors["base"] = "unknown"
        return None

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            info = await self._try(user_input, errors)
            if info is not None:
                serial = info.get("SerialNumber") or user_input[CONF_HOST]
                await self.async_set_unique_id(serial)
                self._abort_if_unique_id_configured(updates={CONF_HOST: user_input[CONF_HOST]})
                title = f"{info.get('ModelName', 'Zyxel')} ({user_input[CONF_HOST]})"
                return self.async_create_entry(title=title, data=user_input)
        return self.async_show_form(
            step_id="user", data_schema=_user_schema(user_input or {}), errors=errors
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            data = {**entry.data, **user_input}
            if await self._try(data, errors) is not None:
                return self.async_update_reload_and_abort(entry, data=data)
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME, default=entry.data[CONF_USERNAME]): str,
                    vol.Required(CONF_PASSWORD): selector.TextSelector(
                        selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        entry = self._get_reconfigure_entry()
        if user_input is not None:
            info = await self._try(user_input, errors)
            if info is not None:
                await self.async_set_unique_id(info.get("SerialNumber") or entry.unique_id)
                self._abort_if_unique_id_mismatch()
                return self.async_update_reload_and_abort(entry, data=user_input)
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_user_schema(user_input or entry.data),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> ZyxelOptionsFlow:
        return ZyxelOptionsFlow()


class ZyxelOptionsFlow(OptionsFlow):
    """Options."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        opts = self.config_entry.options
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=opts.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                    ): vol.All(vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL, max=3600)),
                    vol.Required(
                        CONF_SLOW_INTERVAL,
                        default=opts.get(CONF_SLOW_INTERVAL, DEFAULT_SLOW_INTERVAL),
                    ): vol.All(vol.Coerce(int), vol.Range(min=30, max=86400)),
                    vol.Required(
                        CONF_ALLOW_CELLULAR_CHANGES,
                        default=opts.get(CONF_ALLOW_CELLULAR_CHANGES, False),
                    ): bool,
                    vol.Required(
                        CONF_REVERT_TIMEOUT,
                        default=opts.get(CONF_REVERT_TIMEOUT, DEFAULT_REVERT_TIMEOUT),
                    ): vol.All(vol.Coerce(int), vol.Range(min=90, max=1800)),
                    vol.Required(
                        CONF_ALLOW_RAW_WRITES,
                        default=opts.get(CONF_ALLOW_RAW_WRITES, False),
                    ): bool,
                }
            ),
        )
