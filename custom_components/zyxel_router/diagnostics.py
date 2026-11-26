"""Diagnostics for Zyxel Router."""

from __future__ import annotations

import re
from typing import Any

from homeassistant.components.diagnostics import REDACTED
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .coordinator import ZyxelConfigEntry

# Exact keys that are always redacted, whatever their value type.
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

# The router API has hundreds of keys and new models add more. Scalar values
# whose key matches one of these patterns (case-insensitive) are redacted too.
_REDACT_PATTERN = re.compile(
    r"password|passwd|psk|secret|^pin$|pin$|_pin|pin_|pincode|puk|imei|imsi|iccid|serial|"
    r"macaddr|physaddr|bssid|ssid|hostname|devicename|latitude|longitude|"
    r"ipaddr|ipv6|gateway|dns|provisioning|equipmentid|username|account|"
    r"^sms|phonenumber|msisdn",
    re.IGNORECASE,
)


def _sensitive_key(key: str) -> bool:
    return key in TO_REDACT or bool(_REDACT_PATTERN.search(key))


def redact(data: Any) -> Any:
    """Redact sensitive values recursively (exact keys and key patterns)."""
    if isinstance(data, list):
        return [redact(item) for item in data]
    if not isinstance(data, dict):
        return data
    out: dict[str, Any] = {}
    for key, value in data.items():
        if value is None or value == "":
            out[key] = value
        elif key in TO_REDACT:
            out[key] = REDACTED
        elif isinstance(value, (dict, list)):
            out[key] = redact(value)
        elif not isinstance(value, bool) and _sensitive_key(key):
            # flags like IPv6Enable or AutoGenPSK are harmless and useful
            out[key] = REDACTED
        else:
            out[key] = value
    return out


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ZyxelConfigEntry
) -> dict[str, Any]:
    """Return diagnostics (in-memory state only, no requests to the router)."""
    coordinator = entry.runtime_data
    data = coordinator.data
    return {
        "entry": redact(dict(entry.data)),
        "options": dict(entry.options),
        "features": sorted(data.features) if data else [],
        "unsupported_oids": sorted(coordinator.unsupported_oids),
        "menu": coordinator.menu,
        "raw": redact(data.raw) if data else None,
    }
