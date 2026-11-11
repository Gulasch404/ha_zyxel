"""Test parsing of real (anonymised) NR7101 data."""

from __future__ import annotations

from custom_components.zyxel_router.const import (
    FEATURE_BAND,
    FEATURE_CELL_LOCK,
    FEATURE_CELLULAR,
    FEATURE_GNSS,
    FEATURE_NR,
    FEATURE_NR_LOCK,
    FEATURE_SMS,
    FEATURE_TEMPERATURE,
    FEATURE_WLAN,
)
from custom_components.zyxel_router.models import (
    ZyxelData,
    band_label,
    counter_delta,
    parse_operator,
)

from .conftest import load_oid

OIDS = (
    "status",
    "cellwan_status",
    "Traffic_Status",
    "cellwan_band",
    "cellwan_lock",
    "cellwan_nr_lock",
    "cellwan_sim",
    "cellwan_gnss",
    "cellwan_sms",
    "wlan",
    "lanhosts",
    "cellwan",
)


def _data() -> ZyxelData:
    return ZyxelData(raw={oid: load_oid(oid) for oid in OIDS})


def test_helpers() -> None:
    assert band_label("LTE_BC3") == "B3"
    assert band_label("NR_N78") == "n78"
    assert parse_operator("Current_Magenta-T-_NR-NSA EN-DC_23203") == ("Magenta-T", "23203")
    assert counter_delta(100, 150) == 50
    assert counter_delta(2**32 - 10, 5) == 15  # 32 bit wrap
    assert counter_delta(2**33, 5) is None  # reset of 64 bit counter
    assert counter_delta(None, 5) is None


def test_nr7101_parsing() -> None:
    data = _data()
    assert data.detect_features() == {
        FEATURE_CELLULAR,
        FEATURE_NR,
        FEATURE_GNSS,
        FEATURE_WLAN,
        FEATURE_CELL_LOCK,
        FEATURE_NR_LOCK,
        FEATURE_BAND,
        FEATURE_TEMPERATURE,
    }
    assert FEATURE_SMS not in data.detect_features()
    assert data.operator == "Magenta-T"
    assert data.plmn == "23203"
    assert data.wan_connected is True
    assert data.wan_ipv4 == "203.0.113.10"
    assert data.ca_bands == "B3+B1+B8+n78"
    assert len(data.carriers) == 4
    # 20 (B3) + 15 (B1) + 10 (B8) + 100 (n78)
    assert data.total_dl_bandwidth == 145
    assert data.enb_id == 48225
    assert data.sector_id == 13
    assert data.nr_active
    assert data.gnss_position == (48.208176, 16.373819)
    assert data.wan_stats["BytesReceived"] == 2470214399
    assert data.temperature("CPU0") == 28
    assert data.apn == "staticIP"
    assert data.network_modes == ["Auto", "NR5G-NSA", "NR5G", "LTE", "UMTS"]
    assert "NR_N78" in data.supported_bands
    assert len(data.active_hosts) == 1
