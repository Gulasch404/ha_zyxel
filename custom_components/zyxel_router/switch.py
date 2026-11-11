"""Switches for Zyxel Router."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import cellular
from .const import FEATURE_CELLULAR, FEATURE_WLAN
from .coordinator import ZyxelConfigEntry, ZyxelCoordinator
from .entity import ZyxelEntity

PARALLEL_UPDATES = 1


def _wlan_label(wlan: dict[str, Any], position: int) -> str:
    """'2.4GHz' for main SSIDs, '2.4GHz Guest-SSID' for additional ones."""
    band = wlan.get("band") or str(position + 1)
    if wlan.get("MainSSID", True):
        return band
    return f"{band} {wlan.get('SSID') or wlan.get('Index')}"


def build_wlan_payload(obj: dict[str, Any], index: int, enable: bool) -> dict[str, Any]:
    """Build the wlan PUT payload like the web GUI does (keeps SSID/PSK/security)."""
    sec = obj.get("SecurityMode")
    payload: dict[str, Any] = {
        "Index": index,
        "wlEnable": enable,
        "SSID": obj.get("SSID"),
        "wlHide": obj.get("wlHide", False),
        "AutoGenPSK": obj.get("AutoGenPSK", False),
        "psk_value": obj.get("PskDisplay") or obj.get("CurrentPSKValue", ""),
        "RekeyingInterval": obj.get("RekeyingInterval", 3600),
        "encryp": obj.get("encryp", "aes"),
    }
    if sec == "WPA2-Personal":
        payload |= {"securityLevel": "MoreSecure", "wpaMode": "wpa2psk"}
    elif sec in ("None", None):
        payload |= {"securityLevel": "NoSecurity"}
    return payload


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ZyxelConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up switches."""
    coordinator = entry.runtime_data
    entities: list[SwitchEntity] = []
    if FEATURE_WLAN in coordinator.data.features:
        entities.extend(
            ZyxelWlanSwitch(coordinator, int(w.get("Index", i + 1)), _wlan_label(w, i))
            for i, w in enumerate(coordinator.data.wlan)
        )
    if FEATURE_CELLULAR in coordinator.data.features and coordinator.allow_cellular_changes:
        entities.append(ZyxelRoamingSwitch(coordinator))
    async_add_entities(entities)


class ZyxelWlanSwitch(ZyxelEntity, SwitchEntity):
    """Enable/disable a WLAN (SSID)."""

    _attr_translation_key = "wlan"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: ZyxelCoordinator, index: int, band: str | None) -> None:
        super().__init__(coordinator, f"wlan_{index}")
        self._index = index
        self._attr_translation_placeholders = {"band": band or str(index)}

    def _obj(self) -> dict[str, Any]:
        for w in self.coordinator.data.wlan:
            if int(w.get("Index", 0)) == self._index:
                return w
        return {}

    @property
    def is_on(self) -> bool | None:
        obj = self._obj()
        return obj.get("wlEnable") if obj else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        obj = self._obj()
        return {
            "ssid": obj.get("SSID"),
            "channel": obj.get("channel"),
            "bandwidth": obj.get("bandwidth"),
            "security": obj.get("SecurityMode"),
        }

    async def _set(self, enable: bool) -> None:
        payload = build_wlan_payload(self._obj(), self._index, enable)
        await self.coordinator.async_dal_put("wlan", payload)

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._set(False)


class ZyxelRoamingSwitch(ZyxelEntity, SwitchEntity):
    """Data roaming (watchdog protected)."""

    _attr_translation_key = "roaming"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: ZyxelCoordinator) -> None:
        super().__init__(coordinator, "roaming_switch")

    @property
    def is_on(self) -> bool | None:
        value = self.coordinator.data.cellwan.get("CELL_Roaming_Enable")
        return value if isinstance(value, bool) else None

    async def async_turn_on(self, **kwargs: Any) -> None:
        await cellular.set_roaming(self.coordinator, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await cellular.set_roaming(self.coordinator, False)
