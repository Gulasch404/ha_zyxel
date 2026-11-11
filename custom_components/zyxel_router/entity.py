"""Base entity for Zyxel Router."""

from __future__ import annotations

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import ZyxelCoordinator


class ZyxelEntity(CoordinatorEntity[ZyxelCoordinator]):
    """Common base."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: ZyxelCoordinator, key: str) -> None:
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._attr_unique_id = f"{entry.unique_id or entry.entry_id}_{key}"
        info = coordinator.data.device_info if coordinator.data else {}
        mac = None
        if coordinator.data:
            ports = coordinator.data.status.get("LanPortInfo") or []
            mac = ports[0].get("MACAddress") if ports else None
        cfg_url = coordinator.client.base_url
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.unique_id or entry.entry_id)},
            connections={(CONNECTION_NETWORK_MAC, mac.lower())} if mac else set(),
            manufacturer=MANUFACTURER,
            model=info.get("ModelName"),
            model_id=info.get("ProductClass"),
            name=info.get("ModelName") or "Zyxel",
            serial_number=info.get("SerialNumber"),
            sw_version=info.get("SoftwareVersion"),
            hw_version=info.get("HardwareVersion"),
            configuration_url=cfg_url,
        )
