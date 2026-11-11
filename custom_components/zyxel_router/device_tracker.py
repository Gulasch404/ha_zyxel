"""GNSS position of the router."""

from __future__ import annotations

from typing import Any

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import FEATURE_GNSS
from .coordinator import ZyxelConfigEntry, ZyxelCoordinator
from .entity import ZyxelEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ZyxelConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up GNSS tracker."""
    coordinator = entry.runtime_data
    if FEATURE_GNSS in coordinator.data.features:
        async_add_entities([ZyxelGnssTracker(coordinator)])


class ZyxelGnssTracker(ZyxelEntity, TrackerEntity):
    """Router GNSS position."""

    _attr_translation_key = "gnss"
    _attr_entity_registry_enabled_default = False  # location is privacy relevant

    def __init__(self, coordinator: ZyxelCoordinator) -> None:
        super().__init__(coordinator, "gnss")

    @property
    def source_type(self) -> SourceType:
        return SourceType.GPS

    @property
    def latitude(self) -> float | None:
        pos = self.coordinator.data.gnss_position
        return pos[0] if pos else None

    @property
    def longitude(self) -> float | None:
        pos = self.coordinator.data.gnss_position
        return pos[1] if pos else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        gnss = self.coordinator.data.gnss
        return {
            "satellites": gnss.get("GNSS_NumberOfSatellites"),
            "hdop": gnss.get("GNSS_HDOP"),
            "last_fix": gnss.get("GNSS_LastFixTime"),
        }
