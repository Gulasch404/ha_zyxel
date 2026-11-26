"""Client factory shared by setup and the config flow."""

from __future__ import annotations

from typing import Any

import aiohttp
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .api import ZyxelClient
from .const import CONF_VERIFY_SSL


def create_client(hass: HomeAssistant, data: dict[str, Any]) -> ZyxelClient:
    """Create an API client with its own cookie jar (IP hosts need unsafe jar)."""
    verify = bool(data.get(CONF_VERIFY_SSL, False))
    session = async_create_clientsession(
        hass, verify_ssl=verify, cookie_jar=aiohttp.CookieJar(unsafe=True)
    )
    return ZyxelClient(
        data[CONF_HOST], data[CONF_USERNAME], data[CONF_PASSWORD], session, verify_ssl=verify
    )
