"""Constants for the Zyxel Router integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN: Final = "zyxel_router"
MANUFACTURER: Final = "Zyxel"

CONF_VERIFY_SSL: Final = "verify_ssl"
CONF_ALLOW_CELLULAR_CHANGES: Final = "allow_cellular_changes"
CONF_ALLOW_RAW_WRITES: Final = "allow_raw_writes"
CONF_REVERT_TIMEOUT: Final = "revert_timeout"
CONF_SLOW_INTERVAL: Final = "slow_interval"

DEFAULT_HOST: Final = "http://192.168.1.1"
DEFAULT_USERNAME: Final = "admin"
DEFAULT_SCAN_INTERVAL: Final = 30
MIN_SCAN_INTERVAL: Final = 10
DEFAULT_SLOW_INTERVAL: Final = 300
DEFAULT_REVERT_TIMEOUT: Final = 240

# OIDs polled every update (status holds WAN/DSL/GPON link state)
FAST_OIDS: Final = ("status", "cellwan_status", "Traffic_Status")
# OIDs polled every slow interval (and after writes)
SLOW_OIDS: Final = (
    "cellwan",
    "cellwan_band",
    "cellwan_lock",
    "cellwan_nr_lock",
    "cellwan_sim",
    "cellwan_gnss",
    "cellwan_sms",
    "wlan",
    "lanhosts",
)

# Features (detected at runtime)
FEATURE_CELLULAR: Final = "cellular"
FEATURE_NR: Final = "nr"
FEATURE_GNSS: Final = "gnss"
FEATURE_WLAN: Final = "wlan"
FEATURE_SMS: Final = "sms"
FEATURE_CELL_LOCK: Final = "cell_lock"
FEATURE_NR_LOCK: Final = "nr_lock"
FEATURE_BAND: Final = "band"
FEATURE_TEMPERATURE: Final = "temperature"
FEATURE_DSL: Final = "dsl"
FEATURE_GPON: Final = "gpon"

# Services
SERVICE_SET_PREFERRED_BANDS: Final = "set_preferred_bands"
SERVICE_SET_NETWORK_MODE: Final = "set_network_mode"
SERVICE_SET_CELL_LOCK: Final = "set_cell_lock"
SERVICE_CLEAR_CELL_LOCK: Final = "clear_cell_lock"
SERVICE_SET_NR_CELL_LOCK: Final = "set_nr_cell_lock"
SERVICE_CLEAR_NR_CELL_LOCK: Final = "clear_nr_cell_lock"
SERVICE_DELETE_SMS: Final = "delete_sms"
SERVICE_DAL_GET: Final = "dal_get"
SERVICE_DAL_SET: Final = "dal_set"

EVENT_SMS_RECEIVED: Final = f"{DOMAIN}_sms_received"
EVENT_REVERTED: Final = f"{DOMAIN}_cellular_change_reverted"

# LTE bandwidth index (3GPP / Quectel) -> MHz
LTE_BANDWIDTH_MHZ: Final = {0: 1.4, 1: 3, 2: 5, 3: 10, 4: 15, 5: 20}
# NR bandwidth index (Quectel) -> MHz
NR_BANDWIDTH_MHZ: Final = {
    0: 5, 1: 10, 2: 15, 3: 20, 4: 25, 5: 30, 6: 40, 7: 50, 8: 60,
    9: 70, 10: 80, 11: 90, 12: 100, 13: 200, 14: 400,
}

NETWORK_MODE_OPTIONS: Final = {
    "Auto": "auto",
    "NR5G-NSA": "nr5g_nsa",
    "NR5G": "nr5g_sa",
    "LTE": "lte",
    "UMTS": "umts",
}

FAST_INTERVAL_DEFAULT: Final = timedelta(seconds=DEFAULT_SCAN_INTERVAL)
