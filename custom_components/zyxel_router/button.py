"""Buttons for Zyxel Router."""

from __future__ import annotations

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import ZyxelConnectionError, ZyxelError
from .coordinator import ZyxelConfigEntry, ZyxelCoordinator
from .entity import ZyxelEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ZyxelConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up buttons."""
    coordinator = entry.runtime_data
    async_add_entities([ZyxelRebootButton(coordinator), ZyxelRefreshButton(coordinator)])


class ZyxelRebootButton(ZyxelEntity, ButtonEntity):
    """Reboot the router."""

    _attr_device_class = ButtonDeviceClass.RESTART
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: ZyxelCoordinator) -> None:
        super().__init__(coordinator, "reboot")

    async def async_press(self) -> None:
        try:
            await self.coordinator.client.reboot()
        except ZyxelConnectionError:
            pass  # device often drops the connection while rebooting
        except ZyxelError as err:
            raise HomeAssistantError(f"Reboot failed: {err}") from err
        self.coordinator.client.logged_in = False


class ZyxelRefreshButton(ZyxelEntity, ButtonEntity):
    """Force a full refresh."""

    _attr_translation_key = "refresh"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: ZyxelCoordinator) -> None:
        super().__init__(coordinator, "refresh")

    async def async_press(self) -> None:
        await self.coordinator.async_request_full_refresh()
