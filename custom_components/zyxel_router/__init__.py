"""The Zyxel Router integration."""

from __future__ import annotations

import aiohttp
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.typing import ConfigType

from .api import ZyxelAuthError, ZyxelClient, ZyxelError
from .const import CONF_VERIFY_SSL, DOMAIN
from .coordinator import ZyxelConfigEntry, ZyxelCoordinator
from .services import async_setup_services

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.DEVICE_TRACKER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


def create_client(hass: HomeAssistant, data: dict) -> ZyxelClient:
    """Create an API client with its own cookie jar (IP hosts need unsafe jar)."""
    verify = bool(data.get(CONF_VERIFY_SSL, False))
    session = async_create_clientsession(
        hass, verify_ssl=verify, cookie_jar=aiohttp.CookieJar(unsafe=True)
    )
    return ZyxelClient(
        data[CONF_HOST], data[CONF_USERNAME], data[CONF_PASSWORD], session, verify_ssl=verify
    )


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register services."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ZyxelConfigEntry) -> bool:
    """Set up Zyxel Router from a config entry."""
    client = create_client(hass, dict(entry.data))
    try:
        await client.login()
    except ZyxelAuthError as err:
        raise ConfigEntryAuthFailed(str(err)) from err
    except ZyxelError as err:
        raise ConfigEntryNotReady(str(err)) from err

    coordinator = ZyxelCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ZyxelConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ZyxelConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.client.logout()
    return unloaded
