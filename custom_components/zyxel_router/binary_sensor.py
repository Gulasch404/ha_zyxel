"""Binary sensors for Zyxel Router."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import FEATURE_BAND, FEATURE_CELL_LOCK, FEATURE_CELLULAR, FEATURE_NR, FEATURE_NR_LOCK
from .coordinator import ZyxelConfigEntry, ZyxelCoordinator
from .entity import ZyxelEntity
from .models import ZyxelData

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class ZyxelBinaryDescription(BinarySensorEntityDescription):
    """Binary sensor description."""

    value_fn: Callable[[ZyxelData], bool | None]
    feature: str | None = None


BINARY_SENSORS: tuple[ZyxelBinaryDescription, ...] = (
    ZyxelBinaryDescription(
        key="wan_connected",
        translation_key="wan_connected",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=lambda d: d.wan_connected,
    ),
    ZyxelBinaryDescription(
        key="nr_connected",
        translation_key="nr_connected",
        feature=FEATURE_NR,
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=lambda d: d.nr_active,
    ),
    ZyxelBinaryDescription(
        key="roaming",
        translation_key="roaming",
        feature=FEATURE_CELLULAR,
        value_fn=lambda d: d.cell.get("CELL_Roaming_Enable")
        if "CELL_Roaming_Enable" in d.cell
        else None,
    ),
    ZyxelBinaryDescription(
        key="sim_ready",
        translation_key="sim_ready",
        feature=FEATURE_CELLULAR,
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        # PROBLEM => on when SIM not ready
        value_fn=lambda d: (d.cell.get("USIM_Status") or d.sim.get("USIM_Status"))
        != "DEVST_SIM_RDY",
    ),
    ZyxelBinaryDescription(
        key="band_lock",
        translation_key="band_lock",
        feature=FEATURE_BAND,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: (d.preferred_bands or "Auto") != "Auto"
        if d.band
        else None,
    ),
    ZyxelBinaryDescription(
        key="cell_lock",
        translation_key="cell_lock",
        feature=FEATURE_CELL_LOCK,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: bool(d.lock.get("LK_Enable")) if d.lock else None,
    ),
    ZyxelBinaryDescription(
        key="nr_cell_lock",
        translation_key="nr_cell_lock",
        feature=FEATURE_NR_LOCK,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: bool(d.nr_lock.get("PCI_Enable")) if d.nr_lock else None,
    ),
    ZyxelBinaryDescription(
        key="ip_passthrough",
        translation_key="ip_passthrough",
        feature=FEATURE_CELLULAR,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.cell.get("Passthru_Enable") if "Passthru_Enable" in d.cell else None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ZyxelConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up binary sensors."""
    coordinator = entry.runtime_data
    features = coordinator.data.features
    async_add_entities(
        ZyxelBinarySensor(coordinator, desc)
        for desc in BINARY_SENSORS
        if desc.feature is None or desc.feature in features
    )


class ZyxelBinarySensor(ZyxelEntity, BinarySensorEntity):
    """Zyxel binary sensor."""

    entity_description: ZyxelBinaryDescription

    def __init__(self, coordinator: ZyxelCoordinator, description: ZyxelBinaryDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        return self.entity_description.value_fn(self.coordinator.data)
