"""Connectivity relevant cellular operations (always watchdog protected)."""

from __future__ import annotations

from typing import Any

from homeassistant.exceptions import ServiceValidationError

from .api import ZyxelClient
from .const import DOMAIN
from .coordinator import ZyxelCoordinator


def normalize_band(band: str, supported: list[str]) -> str:
    """Accept 'B3', '3', 'LTE_BC3', 'n78', 'N78', 'NR_N78'."""
    raw = band.strip()
    candidates: list[str] = [raw]
    upper = raw.upper()
    if upper.startswith("B") and upper[1:].isdigit():
        candidates.append(f"LTE_BC{upper[1:]}")
    elif upper.isdigit():
        candidates.append(f"LTE_BC{upper}")
    elif upper.startswith("N") and upper[1:].isdigit():
        candidates.append(f"NR_N{upper[1:]}")
    elif upper.startswith("NR_N") or upper.startswith("LTE_BC"):
        candidates.append(upper)
    for cand in candidates:
        if cand in supported:
            return cand
    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="invalid_band",
        translation_placeholders={"band": band, "supported": ", ".join(supported)},
    )


async def set_network_mode(coordinator: ZyxelCoordinator, mode: str) -> None:
    """Set preferred access technology (Auto, LTE, NR5G-NSA, NR5G, UMTS)."""
    client: ZyxelClient = coordinator.client
    modes = coordinator.data.network_modes if coordinator.data else ["Auto"]
    if mode not in modes:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_mode",
            translation_placeholders={"mode": mode, "supported": ", ".join(modes)},
        )

    async def snapshot() -> dict[str, Any]:
        return await client.dal_get_one("cellwan_band")

    async def apply() -> None:
        obj = await client.dal_get_one("cellwan_band")
        obj["INTF_Preferred_Access_Technology"] = mode
        await client.dal_put("cellwan_band", obj)

    async def restore(prev: dict[str, Any]) -> None:
        await client.dal_put("cellwan_band", prev)

    await coordinator.async_cellular_change(f"Network mode → {mode}", snapshot, apply, restore)


async def set_preferred_bands(coordinator: ZyxelCoordinator, bands: list[str]) -> None:
    """Set preferred bands; empty list or ['auto'] => Auto."""
    client = coordinator.client
    supported = coordinator.data.supported_bands if coordinator.data else []
    if not bands or [b.lower() for b in bands] == ["auto"]:
        value = "Auto"
    else:
        value = ",".join(sorted({normalize_band(b, supported) for b in bands}))
        if not any(b.startswith("LTE_") for b in value.split(",")):
            # NSA needs an LTE anchor; SA-only lists are allowed but dangerous
            mode = (coordinator.data.band.get("INTF_Preferred_Access_Technology") if coordinator.data else None)
            if mode != "NR5G":
                raise ServiceValidationError(
                    translation_domain=DOMAIN, translation_key="no_lte_anchor"
                )

    async def snapshot() -> dict[str, Any]:
        return await client.dal_get_one("cellwan_band")

    async def apply() -> None:
        obj = await client.dal_get_one("cellwan_band")
        obj["INTF_Preferred_Bands"] = value
        await client.dal_put("cellwan_band", obj)

    async def restore(prev: dict[str, Any]) -> None:
        await client.dal_put("cellwan_band", prev)

    await coordinator.async_cellular_change(f"Bands → {value}", snapshot, apply, restore)


async def _write_cell_lock(client: ZyxelClient, enable: bool, cells: list[dict[str, int]]) -> None:
    """Replicate the web GUI: delete entries, POST new ones, PUT enable flag."""
    current = await client.dal_get_one("cellwan_lock")
    existing = current.get("LK_LockedList") or []
    if enable or existing:
        for index in range(len(existing), 0, -1):
            await client.dal_delete("cellwan_lock", Index=str(index))
        current = await client.dal_get_one("cellwan_lock")
        current["LK_LockedList"] = []
        for _ in cells:
            current["LK_LockedList"].append({"PhyCellID": -1, "RFCN": 0})
            await client.dal_post("cellwan_lock", current)
    current = await client.dal_get_one("cellwan_lock")
    current["LK_Enable"] = enable and bool(cells)
    current["LK_LockedList"] = [
        {"PhyCellID": int(c["PhyCellID"]), "RFCN": int(c["RFCN"])} for c in cells
    ]
    await client.dal_put("cellwan_lock", current)


async def set_cell_lock(coordinator: ZyxelCoordinator, cells: list[dict[str, Any]]) -> None:
    """Lock LTE to up to 5 cells [{pci, earfcn}]."""
    client = coordinator.client
    if not 1 <= len(cells) <= 5:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="cell_count")
    parsed = [{"PhyCellID": int(c["pci"]), "RFCN": int(c["earfcn"])} for c in cells]
    for cell in parsed:
        if not 0 <= cell["PhyCellID"] <= 503 or cell["RFCN"] <= 0:
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key="invalid_cell")

    async def snapshot() -> dict[str, Any]:
        return await client.dal_get_one("cellwan_lock")

    async def apply() -> None:
        await _write_cell_lock(client, True, parsed)

    async def restore(prev: dict[str, Any]) -> None:
        await _write_cell_lock(
            client, bool(prev.get("LK_Enable")), list(prev.get("LK_LockedList") or [])
        )

    desc = ", ".join(f"PCI {c['PhyCellID']}/EARFCN {c['RFCN']}" for c in parsed)
    await coordinator.async_cellular_change(f"LTE cell lock → {desc}", snapshot, apply, restore)


async def clear_cell_lock(coordinator: ZyxelCoordinator) -> None:
    """Disable LTE cell lock."""
    client = coordinator.client

    async def snapshot() -> dict[str, Any]:
        return await client.dal_get_one("cellwan_lock")

    async def apply() -> None:
        obj = await client.dal_get_one("cellwan_lock")
        obj["LK_Enable"] = False
        await client.dal_put("cellwan_lock", obj)

    async def restore(prev: dict[str, Any]) -> None:
        await _write_cell_lock(
            client, bool(prev.get("LK_Enable")), list(prev.get("LK_LockedList") or [])
        )

    await coordinator.async_cellular_change("LTE cell lock off", snapshot, apply, restore)


async def set_nr_cell_lock(
    coordinator: ZyxelCoordinator, pci: int, arfcn: int, band: int, scs: int
) -> None:
    """Lock NR5G-SA cell (only effective in SA mode)."""
    client = coordinator.client
    if scs not in (15, 30, 60, 120):
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="invalid_scs")

    async def snapshot() -> dict[str, Any]:
        return await client.dal_get_one("cellwan_nr_lock")

    async def apply() -> None:
        obj = await client.dal_get_one("cellwan_nr_lock")
        obj.update(PCI_Enable=True, PCI=int(pci), RFCN=int(arfcn), BAND=int(band), SCS=int(scs))
        obj.pop("Status", None)
        await client.dal_put("cellwan_nr_lock", obj)

    async def restore(prev: dict[str, Any]) -> None:
        prev = dict(prev)
        prev.pop("Status", None)
        await client.dal_put("cellwan_nr_lock", prev)

    await coordinator.async_cellular_change(
        f"NR cell lock → PCI {pci}/ARFCN {arfcn}/n{band}", snapshot, apply, restore
    )


async def clear_nr_cell_lock(coordinator: ZyxelCoordinator) -> None:
    """Disable NR cell lock."""
    client = coordinator.client

    async def snapshot() -> dict[str, Any]:
        return await client.dal_get_one("cellwan_nr_lock")

    async def apply() -> None:
        obj = await client.dal_get_one("cellwan_nr_lock")
        obj["PCI_Enable"] = False
        obj.pop("Status", None)
        await client.dal_put("cellwan_nr_lock", obj)

    async def restore(prev: dict[str, Any]) -> None:
        prev = dict(prev)
        prev.pop("Status", None)
        await client.dal_put("cellwan_nr_lock", prev)

    await coordinator.async_cellular_change("NR cell lock off", snapshot, apply, restore)


async def set_roaming(coordinator: ZyxelCoordinator, enable: bool) -> None:
    """Enable/disable data roaming."""
    client = coordinator.client

    async def snapshot() -> dict[str, Any]:
        return await client.dal_get_one("cellwan")

    async def apply() -> None:
        obj = await client.dal_get_one("cellwan")
        obj["CELL_Roaming_Enable"] = enable
        await client.dal_put("cellwan", obj)

    async def restore(prev: dict[str, Any]) -> None:
        await client.dal_put("cellwan", prev)

    await coordinator.async_cellular_change(
        f"Roaming → {'on' if enable else 'off'}", snapshot, apply, restore
    )
