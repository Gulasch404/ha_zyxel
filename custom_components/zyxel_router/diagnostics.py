"""Diagnostics for Zyxel Router."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .api import ZyxelError
from .coordinator import ZyxelConfigEntry

TO_REDACT = {
    CONF_PASSWORD,
    CONF_USERNAME,
    "INTF_IMEI",
    "USIM_IMSI",
    "USIM_ICCID",
    "SerialNumber",
    "IPAddress",
    "IPAddress6",
    "PhysAddress",
    "MACAddress",
    "BSSID",
    "SSID",
    "PskDisplay",
    "AutoGenPSKValue",
    "CurrentPSKValue",
    "wifiPassword",
    "psk_value",
    "RadiusSecret",
    "GNSS_Latitude",
    "GNSS_Longitude",
    "X_ZYXEL_ProvisioningKey",
    "AP_Password",
    "AP_Username",
    "DNSServer",
    "v4dns",
    "HostName",
    "DeviceName",
    "Content",
    "SMS_Inbox",
    "Passthru_MacAddr",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ZyxelConfigEntry
) -> dict[str, Any]:
    """Return diagnostics."""
    coordinator = entry.runtime_data
    data = coordinator.data
    return {
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "options": dict(entry.options),
        "features": sorted(data.features) if data else [],
        "unsupported_oids": sorted(coordinator._unsupported),
        "menu": await _menu(coordinator),
        "raw": async_redact_data(data.raw, TO_REDACT) if data else None,
    }


async def _menu(coordinator) -> list[str] | str:
    """Page titles of the web GUI menu (shows which functions a model offers)."""
    try:
        menu = await coordinator.client.cgi_get("MenuList")
    except ZyxelError as err:
        return f"unavailable: {err}"
    titles: list[str] = []
    for section in (menu or {}).get("MenuList") or []:
        for page in section.get("submenu") or []:
            if page.get("title"):
                titles.append(f"{section.get('title')} > {page['title']}")
    return titles
