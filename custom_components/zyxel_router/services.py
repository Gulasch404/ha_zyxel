"""Services for Zyxel Router."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr

from . import cellular
from .api import ZyxelError
from .const import (
    CONF_ALLOW_RAW_WRITES,
    DOMAIN,
    FEATURE_SMS,
    SERVICE_CLEAR_CELL_LOCK,
    SERVICE_CLEAR_NR_CELL_LOCK,
    SERVICE_DAL_GET,
    SERVICE_DAL_SET,
    SERVICE_DELETE_SMS,
    SERVICE_SET_CELL_LOCK,
    SERVICE_SET_NETWORK_MODE,
    SERVICE_SET_NR_CELL_LOCK,
    SERVICE_SET_PREFERRED_BANDS,
)
from .coordinator import ZyxelCoordinator

ATTR_DEVICE_ID = "device_id"

BASE = vol.Schema({vol.Optional(ATTR_DEVICE_ID): cv.string}, extra=vol.PREVENT_EXTRA)

SCHEMAS: dict[str, vol.Schema] = {
    SERVICE_SET_PREFERRED_BANDS: BASE.extend(
        {vol.Required("bands"): vol.All(cv.ensure_list, [cv.string])}
    ),
    SERVICE_SET_NETWORK_MODE: BASE.extend({vol.Required("mode"): cv.string}),
    SERVICE_SET_CELL_LOCK: BASE.extend(
        {
            vol.Required("cells"): vol.All(
                cv.ensure_list,
                [
                    vol.Schema(
                        {
                            vol.Required("pci"): vol.Coerce(int),
                            vol.Required("earfcn"): vol.Coerce(int),
                        }
                    )
                ],
            )
        }
    ),
    SERVICE_CLEAR_CELL_LOCK: BASE,
    SERVICE_SET_NR_CELL_LOCK: BASE.extend(
        {
            vol.Required("pci"): vol.Coerce(int),
            vol.Required("arfcn"): vol.Coerce(int),
            vol.Required("band"): vol.Coerce(int),
            vol.Optional("scs", default=30): vol.Coerce(int),
        }
    ),
    SERVICE_CLEAR_NR_CELL_LOCK: BASE,
    SERVICE_DELETE_SMS: BASE.extend({vol.Required("index"): vol.Coerce(int)}),
    SERVICE_DAL_GET: BASE.extend({vol.Required("oid"): cv.string}),
    SERVICE_DAL_SET: BASE.extend(
        {
            vol.Required("oid"): cv.string,
            vol.Optional("method", default="PUT"): vol.In(["PUT", "POST", "DELETE"]),
            vol.Optional("payload", default={}): dict,
            vol.Optional("params", default={}): {cv.string: cv.string},
        }
    ),
}


def _coordinator(hass: HomeAssistant, call: ServiceCall) -> ZyxelCoordinator:
    entries = [
        e
        for e in hass.config_entries.async_entries(DOMAIN)
        if e.state is ConfigEntryState.LOADED
    ]
    device_id = call.data.get(ATTR_DEVICE_ID)
    if device_id:
        device = dr.async_get(hass).async_get(device_id)
        if device is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="unknown_device"
            )
        entries = [e for e in entries if e.entry_id in device.config_entries]
    if len(entries) != 1:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="device_required"
        )
    return entries[0].runtime_data


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register integration services."""

    async def set_preferred_bands(call: ServiceCall) -> None:
        await cellular.set_preferred_bands(_coordinator(hass, call), call.data["bands"])

    async def set_network_mode(call: ServiceCall) -> None:
        await cellular.set_network_mode(_coordinator(hass, call), call.data["mode"])

    async def set_cell_lock(call: ServiceCall) -> None:
        await cellular.set_cell_lock(_coordinator(hass, call), call.data["cells"])

    async def clear_cell_lock(call: ServiceCall) -> None:
        await cellular.clear_cell_lock(_coordinator(hass, call))

    async def set_nr_cell_lock(call: ServiceCall) -> None:
        await cellular.set_nr_cell_lock(
            _coordinator(hass, call),
            call.data["pci"],
            call.data["arfcn"],
            call.data["band"],
            call.data["scs"],
        )

    async def clear_nr_cell_lock(call: ServiceCall) -> None:
        await cellular.clear_nr_cell_lock(_coordinator(hass, call))

    async def delete_sms(call: ServiceCall) -> None:
        coordinator = _coordinator(hass, call)
        if FEATURE_SMS not in coordinator.data.features:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="sms_not_supported"
            )
        try:
            await coordinator.client.dal_delete("cellwan_sms", objIndex=str(call.data["index"]))
        except ZyxelError as err:
            raise HomeAssistantError(str(err)) from err
        await coordinator.async_request_full_refresh()

    async def dal_get(call: ServiceCall) -> ServiceResponse:
        coordinator = _coordinator(hass, call)
        try:
            objects = await coordinator.client.dal_get(call.data["oid"])
        except ZyxelError as err:
            raise HomeAssistantError(str(err)) from err
        return {"objects": objects}

    async def dal_set(call: ServiceCall) -> ServiceResponse:
        coordinator = _coordinator(hass, call)
        if not coordinator.config_entry.options.get(CONF_ALLOW_RAW_WRITES, False):
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="raw_writes_disabled"
            )
        oid, method = call.data["oid"], call.data["method"]
        params: dict[str, Any] = call.data["params"]
        try:
            if method == "PUT":
                result = await coordinator.client.dal_put(oid, call.data["payload"], **params)
            elif method == "POST":
                result = await coordinator.client.dal_post(oid, call.data["payload"], **params)
            else:
                result = await coordinator.client.dal_delete(oid, **params)
        except ZyxelError as err:
            raise HomeAssistantError(str(err)) from err
        await coordinator.async_request_full_refresh()
        return {"result": result if isinstance(result, dict) else {"raw": result}}

    handlers = {
        SERVICE_SET_PREFERRED_BANDS: (set_preferred_bands, SupportsResponse.NONE),
        SERVICE_SET_NETWORK_MODE: (set_network_mode, SupportsResponse.NONE),
        SERVICE_SET_CELL_LOCK: (set_cell_lock, SupportsResponse.NONE),
        SERVICE_CLEAR_CELL_LOCK: (clear_cell_lock, SupportsResponse.NONE),
        SERVICE_SET_NR_CELL_LOCK: (set_nr_cell_lock, SupportsResponse.NONE),
        SERVICE_CLEAR_NR_CELL_LOCK: (clear_nr_cell_lock, SupportsResponse.NONE),
        SERVICE_DELETE_SMS: (delete_sms, SupportsResponse.NONE),
        SERVICE_DAL_GET: (dal_get, SupportsResponse.ONLY),
        SERVICE_DAL_SET: (dal_set, SupportsResponse.OPTIONAL),
    }
    for name, (handler, supports) in handlers.items():
        hass.services.async_register(
            DOMAIN, name, handler, schema=SCHEMAS[name], supports_response=supports
        )
