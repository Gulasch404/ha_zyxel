"""Select entities for Zyxel Router."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import cellular
from .const import FEATURE_BAND, NETWORK_MODE_OPTIONS
from .coordinator import ZyxelConfigEntry, ZyxelCoordinator
from .entity import ZyxelEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ZyxelConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up selects (only when cellular changes are allowed)."""
    coordinator = entry.runtime_data
    if FEATURE_BAND in coordinator.data.features and coordinator.allow_cellular_changes:
        async_add_entities([ZyxelNetworkModeSelect(coordinator)])


class ZyxelNetworkModeSelect(ZyxelEntity, SelectEntity):
    """Preferred access technology."""

    _attr_translation_key = "network_mode"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: ZyxelCoordinator) -> None:
        super().__init__(coordinator, "network_mode")
        self._modes = {
            m: NETWORK_MODE_OPTIONS.get(m, m.lower().replace("-", "_"))
            for m in coordinator.data.network_modes
        }
        self._reverse = {v: k for k, v in self._modes.items()}
        self._attr_options = list(self._modes.values())

    @property
    def current_option(self) -> str | None:
        mode = self.coordinator.data.band.get("INTF_Preferred_Access_Technology")
        return self._modes.get(mode) if mode else None

    async def async_select_option(self, option: str) -> None:
        await cellular.set_network_mode(self.coordinator, self._reverse[option])
