"""Sensors for Zyxel Router."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    SIGNAL_STRENGTH_DECIBELS,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfDataRate,
    UnitOfFrequency,
    UnitOfInformation,
    UnitOfLength,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import (
    FEATURE_CELLULAR,
    FEATURE_GNSS,
    FEATURE_NR,
    FEATURE_SMS,
    FEATURE_TEMPERATURE,
    FEATURE_WLAN,
)
from .coordinator import ZyxelConfigEntry, ZyxelCoordinator
from .entity import ZyxelEntity
from .models import ZyxelData, band_label, lte_bw, valid

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class ZyxelSensorDescription(SensorEntityDescription):
    """Sensor description."""

    value_fn: Callable[[ZyxelData], Any]
    attr_fn: Callable[[ZyxelData], dict[str, Any] | None] | None = None
    feature: str | None = None


def _uptime(seconds: Any) -> datetime | None:
    if not isinstance(seconds, (int, float)) or seconds <= 0:
        return None
    # round to the minute to avoid state changes every poll
    ts = dt_util.utcnow() - timedelta(seconds=seconds)
    return ts.replace(second=0, microsecond=0)


_SIM_STATES = {
    "RDY": "ready",
    "NOT_INSERTED": "not_inserted",
    "PIN": "pin_required",
    "PUK": "puk_required",
    "ERROR": "error",
}


def _sim_status(raw: str | None) -> str | None:
    if not raw:
        return None
    code = raw.removeprefix("DEVST_SIM_").upper()
    return _SIM_STATES.get(code, code.lower())


def _mbit(value: float | None) -> float | None:
    return round(value / 1_000_000, 2) if value is not None else None


def _c(key: str) -> Callable[[ZyxelData], Any]:
    return lambda d: valid(d.cell.get(key))


SIGNAL = {
    "state_class": SensorStateClass.MEASUREMENT,
}

SENSORS: tuple[ZyxelSensorDescription, ...] = (
    # ------------------------------------------------------------ cellular
    ZyxelSensorDescription(
        key="access_technology",
        translation_key="access_technology",
        feature=FEATURE_CELLULAR,
        value_fn=_c("INTF_Current_Access_Technology"),
    ),
    ZyxelSensorDescription(
        key="operator",
        translation_key="operator",
        feature=FEATURE_CELLULAR,
        value_fn=lambda d: d.operator,
        attr_fn=lambda d: {"plmn": d.plmn},
    ),
    ZyxelSensorDescription(
        key="band",
        translation_key="band",
        feature=FEATURE_CELLULAR,
        value_fn=lambda d: band_label(d.cell.get("INTF_Current_Band")),
    ),
    ZyxelSensorDescription(
        key="ca_bands",
        translation_key="ca_bands",
        feature=FEATURE_CELLULAR,
        value_fn=lambda d: d.ca_bands,
        attr_fn=lambda d: {
            "carriers": d.carriers,
            "carrier_count": len(d.carriers),
            "ca_combination": d.cell.get("INTF_CA_COMBINATION"),
        },
    ),
    ZyxelSensorDescription(
        key="carrier_count",
        translation_key="carrier_count",
        feature=FEATURE_CELLULAR,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: len(d.carriers),
    ),
    ZyxelSensorDescription(
        key="total_bandwidth",
        translation_key="total_bandwidth",
        feature=FEATURE_CELLULAR,
        native_unit_of_measurement=UnitOfFrequency.MEGAHERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.total_dl_bandwidth,
    ),
    ZyxelSensorDescription(
        key="rssi",
        translation_key="rssi",
        feature=FEATURE_CELLULAR,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        value_fn=_c("INTF_RSSI"),
        **SIGNAL,
    ),
    ZyxelSensorDescription(
        key="rsrp",
        translation_key="rsrp",
        feature=FEATURE_CELLULAR,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        value_fn=_c("INTF_RSRP"),
        **SIGNAL,
    ),
    ZyxelSensorDescription(
        key="rsrq",
        translation_key="rsrq",
        feature=FEATURE_CELLULAR,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
        value_fn=_c("INTF_RSRQ"),
        **SIGNAL,
    ),
    ZyxelSensorDescription(
        key="sinr",
        translation_key="sinr",
        feature=FEATURE_CELLULAR,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
        value_fn=lambda d: valid(d.cell.get("INTF_SINR"), (-32768,)),
        **SIGNAL,
    ),
    ZyxelSensorDescription(
        key="cqi",
        translation_key="cqi",
        feature=FEATURE_CELLULAR,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_c("INTF_CQI"),
        **SIGNAL,
    ),
    ZyxelSensorDescription(
        key="mcs",
        translation_key="mcs",
        feature=FEATURE_CELLULAR,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda d: valid(d.cell.get("INTF_MCS"), ()),
        **SIGNAL,
    ),
    ZyxelSensorDescription(
        key="ri",
        translation_key="ri",
        feature=FEATURE_CELLULAR,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_c("INTF_RI"),
        **SIGNAL,
    ),
    ZyxelSensorDescription(
        key="cell_id",
        translation_key="cell_id",
        feature=FEATURE_CELLULAR,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_c("INTF_Cell_ID"),
        attr_fn=lambda d: {
            "enb_id": d.enb_id,
            "sector_id": d.sector_id,
            "tac": valid(d.cell.get("INTF_TAC")),
            "pci": valid(d.cell.get("INTF_PhyCell_ID")),
            "earfcn": valid(d.cell.get("INTF_RFCN")),
        },
    ),
    ZyxelSensorDescription(
        key="enb_id",
        translation_key="enb_id",
        feature=FEATURE_CELLULAR,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.enb_id,
    ),
    ZyxelSensorDescription(
        key="pci",
        translation_key="pci",
        feature=FEATURE_CELLULAR,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_c("INTF_PhyCell_ID"),
    ),
    ZyxelSensorDescription(
        key="earfcn",
        translation_key="earfcn",
        feature=FEATURE_CELLULAR,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_c("INTF_RFCN"),
    ),
    ZyxelSensorDescription(
        key="tac",
        translation_key="tac",
        feature=FEATURE_CELLULAR,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_c("INTF_TAC"),
    ),
    ZyxelSensorDescription(
        key="dl_bandwidth",
        translation_key="dl_bandwidth",
        feature=FEATURE_CELLULAR,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfFrequency.MEGAHERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
        value_fn=lambda d: lte_bw(d.cell.get("INTF_Downlink_Bandwidth")),
    ),
    ZyxelSensorDescription(
        key="ul_bandwidth",
        translation_key="ul_bandwidth",
        feature=FEATURE_CELLULAR,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfFrequency.MEGAHERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
        value_fn=lambda d: lte_bw(d.cell.get("INTF_Uplink_Bandwidth")),
    ),
    # ------------------------------------------------------------- 5G NR
    ZyxelSensorDescription(
        key="nr_band",
        translation_key="nr_band",
        feature=FEATURE_NR,
        value_fn=lambda d: band_label(d.cell.get("NSA_Band")) if d.cell.get("NSA_Enable") else None,
    ),
    ZyxelSensorDescription(
        key="nr_rsrp",
        translation_key="nr_rsrp",
        feature=FEATURE_NR,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        value_fn=lambda d: valid(d.cell.get("NSA_RSRP")) if d.cell.get("NSA_Enable") else None,
        **SIGNAL,
    ),
    ZyxelSensorDescription(
        key="nr_rsrq",
        translation_key="nr_rsrq",
        feature=FEATURE_NR,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
        value_fn=lambda d: valid(d.cell.get("NSA_RSRQ")) if d.cell.get("NSA_Enable") else None,
        **SIGNAL,
    ),
    ZyxelSensorDescription(
        key="nr_sinr",
        translation_key="nr_sinr",
        feature=FEATURE_NR,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
        value_fn=lambda d: valid(d.cell.get("NSA_SINR"), (-32768,))
        if d.cell.get("NSA_Enable")
        else None,
        **SIGNAL,
    ),
    ZyxelSensorDescription(
        key="nr_pci",
        translation_key="nr_pci",
        feature=FEATURE_NR,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: valid(d.cell.get("NSA_PCI")) if d.cell.get("NSA_Enable") else None,
    ),
    ZyxelSensorDescription(
        key="nr_arfcn",
        translation_key="nr_arfcn",
        feature=FEATURE_NR,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: valid(d.cell.get("NSA_RFCN")) if d.cell.get("NSA_Enable") else None,
    ),
    # ------------------------------------------------------------- SIM
    ZyxelSensorDescription(
        key="sim_status",
        translation_key="sim_status",
        feature=FEATURE_CELLULAR,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: _sim_status(d.cell.get("USIM_Status") or d.sim.get("USIM_Status")),
    ),
    ZyxelSensorDescription(
        key="imei",
        translation_key="imei",
        feature=FEATURE_CELLULAR,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_c("INTF_IMEI"),
    ),
    ZyxelSensorDescription(
        key="imsi",
        translation_key="imsi",
        feature=FEATURE_CELLULAR,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_c("USIM_IMSI"),
    ),
    ZyxelSensorDescription(
        key="iccid",
        translation_key="iccid",
        feature=FEATURE_CELLULAR,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_c("USIM_ICCID"),
    ),
    ZyxelSensorDescription(
        key="preferred_bands",
        translation_key="preferred_bands",
        feature=FEATURE_CELLULAR,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.preferred_bands,
        attr_fn=lambda d: {"supported_bands": [band_label(b) for b in d.supported_bands]},
    ),
    ZyxelSensorDescription(
        key="modem_firmware",
        translation_key="modem_firmware",
        feature=FEATURE_CELLULAR,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_c("INTF_Module_Software_Version"),
    ),
    # ------------------------------------------------------------- WAN
    ZyxelSensorDescription(
        key="wan_ipv4",
        translation_key="wan_ipv4",
        value_fn=lambda d: d.wan_ipv4,
        attr_fn=lambda d: {"dns": d.wan_dns, "interface": d.wan.get("X_ZYXEL_SrvName")},
    ),
    ZyxelSensorDescription(
        key="wan_ipv6",
        translation_key="wan_ipv6",
        entity_registry_enabled_default=False,
        value_fn=lambda d: d.wan_ipv6,
    ),
    ZyxelSensorDescription(
        key="download_rate",
        translation_key="download_rate",
        native_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND,
        device_class=SensorDeviceClass.DATA_RATE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda d: _mbit(d.rx_rate),
    ),
    ZyxelSensorDescription(
        key="upload_rate",
        translation_key="upload_rate",
        native_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND,
        device_class=SensorDeviceClass.DATA_RATE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda d: _mbit(d.tx_rate),
    ),
    ZyxelSensorDescription(
        key="wan_received",
        translation_key="wan_received",
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIGABYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda d: d.wan_stats.get("BytesReceived"),
    ),
    ZyxelSensorDescription(
        key="wan_sent",
        translation_key="wan_sent",
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIGABYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda d: d.wan_stats.get("BytesSent"),
    ),
    ZyxelSensorDescription(
        key="wan_connected_since",
        translation_key="wan_connected_since",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: _uptime(d.wan_iface.get("X_ZYXEL_UpTime")),
    ),
    # ------------------------------------------------------------ system
    ZyxelSensorDescription(
        key="last_boot",
        translation_key="last_boot",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: _uptime(d.device_info.get("UpTime")),
    ),
    ZyxelSensorDescription(
        key="clients",
        translation_key="clients",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: len(d.active_hosts),
        attr_fn=lambda d: {
            "hosts": [
                {
                    "name": h.get("HostName") or h.get("DeviceName"),
                    "ip": h.get("IPAddress"),
                    "mac": h.get("PhysAddress"),
                    "connection": h.get("X_ZYXEL_ConnectionType"),
                }
                for h in d.active_hosts
            ]
        },
    ),
    ZyxelSensorDescription(
        key="wifi_clients",
        translation_key="wifi_clients",
        feature=FEATURE_WLAN,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.wifi_clients,
    ),
    ZyxelSensorDescription(
        key="lan_speed",
        translation_key="lan_speed",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND,
        device_class=SensorDeviceClass.DATA_RATE,
        value_fn=lambda d: next(
            (
                p.get("MaxBitRate")
                for p in d.status.get("LanPortInfo") or []
                if p.get("Status") == "Up"
            ),
            None,
        ),
    ),
    ZyxelSensorDescription(
        key="apn",
        translation_key="apn",
        feature=FEATURE_CELLULAR,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.apn,
    ),
    # ------------------------------------------------------ temperatures
    ZyxelSensorDescription(
        key="temperature_cpu",
        translation_key="temperature_cpu",
        feature=FEATURE_TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.temperature("CPU0"),
    ),
    ZyxelSensorDescription(
        key="temperature_modem",
        translation_key="temperature_modem",
        feature=FEATURE_TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.temperature("SDX"),
    ),
    ZyxelSensorDescription(
        key="temperature_ambient",
        translation_key="temperature_ambient",
        feature=FEATURE_TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.temperature("AMBIENT"),
    ),
    # ------------------------------------------------------------- GNSS
    ZyxelSensorDescription(
        key="gnss_satellites",
        translation_key="gnss_satellites",
        feature=FEATURE_GNSS,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.gnss.get("GNSS_NumberOfSatellites"),
    ),
    ZyxelSensorDescription(
        key="gnss_altitude",
        translation_key="gnss_altitude",
        feature=FEATURE_GNSS,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfLength.METERS,
        device_class=SensorDeviceClass.DISTANCE,
        value_fn=lambda d: d.gnss.get("GNSS_Elevation") / 10
        if isinstance(d.gnss.get("GNSS_Elevation"), (int, float))
        else None,
    ),
    ZyxelSensorDescription(
        key="gnss_last_fix",
        translation_key="gnss_last_fix",
        feature=FEATURE_GNSS,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda d: dt_util.parse_datetime(d.gnss.get("GNSS_LastFixTime") or ""),
    ),
    # -------------------------------------------------------------- SMS
    ZyxelSensorDescription(
        key="sms_inbox",
        translation_key="sms_inbox",
        feature=FEATURE_SMS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: len(d.sms_inbox),
        attr_fn=lambda d: {"messages": d.sms_inbox[-10:]},
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ZyxelConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensors."""
    coordinator = entry.runtime_data
    features = coordinator.data.features
    async_add_entities(
        ZyxelSensor(coordinator, desc)
        for desc in SENSORS
        if desc.feature is None or desc.feature in features
    )


class ZyxelSensor(ZyxelEntity, SensorEntity):
    """Zyxel sensor."""

    entity_description: ZyxelSensorDescription

    def __init__(self, coordinator: ZyxelCoordinator, description: ZyxelSensorDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.attr_fn is None:
            return None
        return self.entity_description.attr_fn(self.coordinator.data)
