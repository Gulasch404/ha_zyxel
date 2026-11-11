"""Tests for non-cellular device types.

The data below is SYNTHETIC: field names are taken from the Zyxel web GUI code
(which is shared across models), values are made up. Replace with anonymised
real dumps once users report these models.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.zyxel_router.const import (
    DOMAIN,
    FEATURE_CELLULAR,
    FEATURE_DSL,
    FEATURE_GPON,
)
from custom_components.zyxel_router.models import ZyxelData


def _wan(link_type: str, encapsulation: str = "PPPoE", ppp: str = "Connected") -> dict:
    return {
        "X_ZYXEL_Type": "WAN",
        "X_ZYXEL_DefaultGatewayIface": True,
        "LinkType": link_type,
        "Encapsulation": encapsulation,
        "pppConnectionStatus": ppp,
        "Status": "Up",
        "IPv4Address": [{"IPAddress": "203.0.113.20"}],
    }


def _ports(count: int) -> list[dict]:
    return [
        {
            "X_ZYXEL_LanPort": f"LAN{i + 1}",
            "Status": "Up" if i == 0 else "Down",
            "MaxBitRate": 1000,
            "DuplexMode": "Full",
        }
        for i in range(count)
    ]


DSL_STATUS = {
    "DeviceInfo": {"ModelName": "VMG8825-T50", "SoftwareVersion": "V5.50", "UpTime": 1000},
    "WanLanInfo": [_wan("DSL")],
    "DslChannelInfo": [
        {
            "Status": "Up",
            "DownstreamCurrRate": 109998,
            "UpstreamCurrRate": 39998,
            "LinkEncapsulationUsed": "G.993.2_Annex_K_PTM",
        },
        {"Status": "Down", "DownstreamCurrRate": 0, "UpstreamCurrRate": 0},
    ],
    "GponStatsInfo": {"RxPowerSignal": "0", "TxPowerSignal": "0", "Temperature": "0"},
    "LanPortInfo": _ports(4),
}

GPON_STATUS = {
    "DeviceInfo": {"ModelName": "PX3321-T1", "SoftwareVersion": "V5.50", "UpTime": 1000},
    "WanLanInfo": [_wan("PON")],
    "DslChannelInfo": [],
    "GponStatsInfo": {
        "RxPowerSignal": "-18.52",
        "TxPowerSignal": "2.31",
        "Temperature": "45.1",
        "SFP_Presence": "1",
        "SFP_Vendor": "ZYXEL",
        "SFP_Model": "PMG3000",
    },
    "LanPortInfo": _ports(4),
}

PPP_TRAFFIC = {
    "ipIface": [
        {"Name": "LAN", "X_ZYXEL_DefaultGatewayIface": False, "LowerLayers": "Ethernet.Link.1"},
        {"Name": "WAN", "X_ZYXEL_DefaultGatewayIface": True, "LowerLayers": "PPP.Interface.1"},
    ],
    "ipIfaceSt": [{"BytesReceived": 1, "BytesSent": 1}, {"BytesReceived": 0, "BytesSent": 0}],
    "pppIfaceSt": [{"BytesReceived": 5_000_000, "BytesSent": 1_000_000}],
}


def test_dsl_parsing() -> None:
    data = ZyxelData(raw={"status": [DSL_STATUS], "Traffic_Status": [PPP_TRAFFIC]})
    feats = data.detect_features()
    assert FEATURE_DSL in feats
    assert FEATURE_GPON not in feats
    assert FEATURE_CELLULAR not in feats
    assert data.wan_link_type == "dsl"
    assert data.wan_connected is True
    assert data.dsl_rate("DownstreamCurrRate") == 109.998
    assert data.dsl_rate("UpstreamCurrRate") == 39.998
    # PPPoE: counters come from the PPP interface, not the (empty) IP interface
    assert data.wan_stats["BytesReceived"] == 5_000_000


def test_ppp_disconnected() -> None:
    status = {**DSL_STATUS, "WanLanInfo": [_wan("DSL", ppp="Disconnected")]}
    assert ZyxelData(raw={"status": [status]}).wan_connected is False


def test_gpon_parsing() -> None:
    data = ZyxelData(raw={"status": [GPON_STATUS]})
    feats = data.detect_features()
    assert FEATURE_GPON in feats
    assert FEATURE_DSL not in feats
    assert data.gpon_value("RxPowerSignal") == -18.52
    assert data.gpon_value("TxPowerSignal") == 2.31
    assert data.gpon_value("Temperature") == 45.1
    assert data.wan_link_type == "pon"


async def test_dsl_device_setup(
    hass: HomeAssistant, mock_client: AsyncMock, router, config_entry
) -> None:
    """A DSL router without any cellular OIDs sets up with DSL + per-port sensors."""
    router.objects = {
        "status": [DSL_STATUS],
        "Traffic_Status": [PPP_TRAFFIC],
        "wlan": [
            {"Index": 1, "band": "2.4GHz", "MainSSID": True, "wlEnable": True, "SSID": "a"},
            {"Index": 5, "band": "5GHz", "MainSSID": True, "wlEnable": True, "SSID": "a"},
            {"Index": 2, "band": "2.4GHz", "MainSSID": False, "wlEnable": False, "SSID": "Guest"},
        ],
    }
    for oid in (
        "cellwan_status", "cellwan", "cellwan_band", "cellwan_lock", "cellwan_nr_lock",
        "cellwan_sim", "cellwan_gnss", "cellwan_sms", "lanhosts",
    ):
        router.objects[oid] = []
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    reg = er.async_get(hass)

    def state(platform: str, key: str):
        entity_id = reg.async_get_entity_id(platform, DOMAIN, f"S000Z00000000_{key}")
        return hass.states.get(entity_id) if entity_id else None

    assert state("sensor", "dsl_downstream").state == "109.998"
    assert state("sensor", "wan_type").state == "dsl"
    assert state("binary_sensor", "wan_connected").state == "on"
    assert state("sensor", "lan_speed_lan1").state == "1000"
    assert state("sensor", "lan_speed_lan2").state == "0"
    assert state("sensor", "lan_speed") is None  # replaced by per-port sensors
    assert state("sensor", "rsrp") is None  # no cellular entities
    assert state("switch", "wlan_5") is not None
    assert state("switch", "wlan_2").attributes["friendly_name"].endswith("2.4GHz Guest")


def test_gpon_nested_ax7501() -> None:
    status = {
        "GponStatsInfo": {
            "gponStatusObj": {"RxPowerSignal": "-21.3", "TxPowerSignal": "2.0", "Temperature": "40"},
            "bosa_presence": "1",
        }
    }
    data = ZyxelData(raw={"status": [status]})
    assert FEATURE_GPON in data.detect_features()
    assert data.gpon_value("RxPowerSignal") == -21.3
