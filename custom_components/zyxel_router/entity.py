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
        self._device_id = entry.unique_id or entry.entry_id
        self._attr_unique_id = f"{self._device_id}_{key}"

    @property
    def device_info(self) -> DeviceInfo:
        """Device info, read live so a firmware update shows up without a reload."""
        data = self.coordinator.data
        info = data.device_info if data else {}
        mac = None
        if data:
            ports = data.status.get("LanPortInfo") or []
            mac = ports[0].get("MACAddress") if ports else None
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            connections={(CONNECTION_NETWORK_MAC, mac.lower())} if mac else set(),
            manufacturer=MANUFACTURER,
            model=info.get("ModelName"),
            model_id=info.get("ProductClass"),
            name=info.get("ModelName") or "Zyxel",
            serial_number=info.get("SerialNumber"),
            sw_version=info.get("SoftwareVersion"),
            hw_version=info.get("HardwareVersion"),
            configuration_url=self.coordinator.client.base_url,
        )
