"""Data update coordinator for Zyxel routers."""

from __future__ import annotations

import asyncio
import copy
import logging
import time
from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import ZyxelApiError, ZyxelAuthError, ZyxelClient, ZyxelError
from .const import (
    CONF_ALLOW_CELLULAR_CHANGES,
    CONF_REVERT_TIMEOUT,
    CONF_SLOW_INTERVAL,
    DEFAULT_REVERT_TIMEOUT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SLOW_INTERVAL,
    DOMAIN,
    EVENT_REVERTED,
    EVENT_SMS_RECEIVED,
    FAST_OIDS,
    FEATURE_SMS,
    SLOW_OIDS,
)
from .models import ZyxelData, counter_delta, first

_LOGGER = logging.getLogger(__name__)

type ZyxelConfigEntry = ConfigEntry[ZyxelCoordinator]

# Seconds to wait after a cellular change before evaluating the connection
WATCHDOG_SETTLE = 25
WATCHDOG_POLL = 10
WATCHDOG_STABLE_CHECKS = 2


class ZyxelCoordinator(DataUpdateCoordinator[ZyxelData]):
    """Polls the router and handles writes."""

    config_entry: ZyxelConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: ZyxelConfigEntry, client: ZyxelClient
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {client.host}",
            update_interval=timedelta(
                seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            ),
        )
        self.client = client
        self._raw: dict[str, list[dict[str, Any]]] = {}
        self._last_slow = 0.0
        self._force_slow = True
        self._prev_counters: tuple[float, int | None, int | None] | None = None
        self._features: set[str] = set()
        self._sms_seen: set[str] | None = None
        self._unsupported: set[str] = set()
        self._change_lock = asyncio.Lock()
        self.watchdog_active = False

    # ------------------------------------------------------------- options
    @property
    def allow_cellular_changes(self) -> bool:
        return bool(self.config_entry.options.get(CONF_ALLOW_CELLULAR_CHANGES, False))

    @property
    def revert_timeout(self) -> int:
        return int(self.config_entry.options.get(CONF_REVERT_TIMEOUT, DEFAULT_REVERT_TIMEOUT))

    @property
    def slow_interval(self) -> int:
        return int(self.config_entry.options.get(CONF_SLOW_INTERVAL, DEFAULT_SLOW_INTERVAL))

    # -------------------------------------------------------------- polling
    async def _fetch(self, oids: tuple[str, ...] | list[str]) -> None:
        for oid in oids:
            if oid in self._unsupported:
                continue
            try:
                self._raw[oid] = await self.client.dal_get(oid)
            except ZyxelApiError as err:
                _LOGGER.debug("OID %s not available: %s", oid, err)
                if oid not in self._raw:
                    self._unsupported.add(oid)

    async def _async_update_data(self) -> ZyxelData:
        now = time.monotonic()
        slow = self._force_slow or now - self._last_slow >= self.slow_interval
        try:
            await self._fetch(FAST_OIDS)
            if slow:
                await self._fetch(SLOW_OIDS)
                self._last_slow = now
                self._force_slow = False
        except ZyxelAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except ZyxelError as err:
            raise UpdateFailed(str(err)) from err

        data = ZyxelData(raw=dict(self._raw))
        if slow or not self._features:
            self._features = data.detect_features()
        data.features = self._features
        self._compute_rates(data, now)
        self._handle_sms(data)
        return data

    def _compute_rates(self, data: ZyxelData, now: float) -> None:
        stats = data.wan_stats
        rx, tx = stats.get("BytesReceived"), stats.get("BytesSent")
        prev = self._prev_counters
        self._prev_counters = (now, rx, tx)
        if prev is None:
            return
        elapsed = now - prev[0]
        if elapsed <= 0:
            return
        d_rx, d_tx = counter_delta(prev[1], rx), counter_delta(prev[2], tx)
        data.rx_rate = d_rx * 8 / elapsed if d_rx is not None else None
        data.tx_rate = d_tx * 8 / elapsed if d_tx is not None else None

    def _handle_sms(self, data: ZyxelData) -> None:
        if FEATURE_SMS not in data.features:
            return
        sms_obj = first(data.raw, "cellwan_sms")
        inbox = sms_obj.get("SMS_Inbox") or []
        data.sms_inbox = inbox
        keys = {self._sms_key(m) for m in inbox}
        if self._sms_seen is None:  # first run: do not fire for old messages
            self._sms_seen = keys
            return
        for msg in inbox:
            key = self._sms_key(msg)
            if key not in self._sms_seen:
                self.hass.bus.async_fire(
                    EVENT_SMS_RECEIVED, {"entry_id": self.config_entry.entry_id, **msg}
                )
        self._sms_seen = keys

    @staticmethod
    def _sms_key(msg: dict[str, Any]) -> str:
        return "|".join(str(msg.get(k)) for k in sorted(msg))

    async def async_request_full_refresh(self) -> None:
        """Refresh including the slow oids."""
        self._force_slow = True
        await self.async_request_refresh()

    # --------------------------------------------------------------- writes
    async def async_dal_put(self, oid: str, payload: dict[str, Any]) -> None:
        """Generic (non cellular) write followed by a refresh."""
        try:
            await self.client.dal_put(oid, payload)
        except ZyxelError as err:
            raise HomeAssistantError(f"Zyxel {oid}: {err}") from err
        await self.async_request_full_refresh()

    def _ensure_cellular_allowed(self) -> None:
        if not self.allow_cellular_changes:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="cellular_changes_disabled"
            )
        if self.watchdog_active:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="change_in_progress"
            )

    async def async_cellular_change(
        self,
        description: str,
        snapshot: Callable[[], Awaitable[Any]],
        apply: Callable[[], Awaitable[None]],
        restore: Callable[[Any], Awaitable[None]],
    ) -> None:
        """Apply a connectivity-relevant change guarded by an auto-revert watchdog."""
        self._ensure_cellular_allowed()
        async with self._change_lock:
            try:
                previous = copy.deepcopy(await snapshot())
                _LOGGER.warning("Applying cellular change: %s", description)
                await apply()
            except ZyxelError as err:
                raise HomeAssistantError(f"Zyxel: {err}") from err
            self.watchdog_active = True
            self.config_entry.async_create_background_task(
                self.hass,
                self._watchdog(description, previous, restore),
                f"{DOMAIN} watchdog {description}",
            )

    @property
    def _revert_issue_id(self) -> str:
        return f"cellular_change_reverted_{self.config_entry.entry_id}"

    async def _connection_ok(self) -> bool:
        try:
            cell = await self.client.dal_get_one("cellwan_status")
            status = await self.client.dal_get_one("status")
        except ZyxelError as err:
            _LOGGER.debug("Watchdog check failed: %s", err)
            return False
        data = ZyxelData(raw={"cellwan_status": [cell], "status": [status]})
        return bool(data.wan_connected and data.wan_ipv4)

    async def _watchdog(
        self, description: str, previous: Any, restore: Callable[[Any], Awaitable[None]]
    ) -> None:
        deadline = time.monotonic() + self.revert_timeout
        stable = 0
        try:
            await asyncio.sleep(WATCHDOG_SETTLE)
            while time.monotonic() < deadline:
                if await self._connection_ok():
                    stable += 1
                    if stable >= WATCHDOG_STABLE_CHECKS:
                        _LOGGER.info("Cellular change '%s' confirmed, connection up", description)
                        ir.async_delete_issue(self.hass, DOMAIN, self._revert_issue_id)
                        return
                else:
                    stable = 0
                await asyncio.sleep(WATCHDOG_POLL)

            _LOGGER.error(
                "No cellular connection %ss after '%s' - reverting", self.revert_timeout, description
            )
            reverted = False
            for attempt in range(3):
                try:
                    await restore(previous)
                    reverted = True
                    break
                except ZyxelError as err:
                    _LOGGER.error("Revert attempt %s failed: %s", attempt + 1, err)
                    await asyncio.sleep(10)
            self.hass.bus.async_fire(
                EVENT_REVERTED,
                {
                    "entry_id": self.config_entry.entry_id,
                    "change": description,
                    "reverted": reverted,
                },
            )
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                self._revert_issue_id,
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING if reverted else ir.IssueSeverity.ERROR,
                translation_key="cellular_change_reverted" if reverted else "cellular_revert_failed",
                translation_placeholders={
                    "change": description,
                    "timeout": str(self.revert_timeout),
                },
            )
        finally:
            self.watchdog_active = False
            await self.async_request_full_refresh()
