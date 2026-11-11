"""Parsed data model for Zyxel routers (pure python, no HA imports)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .const import (
    FEATURE_BAND,
    FEATURE_CELL_LOCK,
    FEATURE_CELLULAR,
    FEATURE_DSL,
    FEATURE_GNSS,
    FEATURE_GPON,
    FEATURE_NR,
    FEATURE_NR_LOCK,
    FEATURE_SMS,
    FEATURE_TEMPERATURE,
    FEATURE_WLAN,
    LTE_BANDWIDTH_MHZ,
    NR_BANDWIDTH_MHZ,
)

COUNTER_WRAP = 2**32


def first(raw: dict[str, Any], oid: str) -> dict[str, Any]:
    """Return first object of an oid result list."""
    objs = raw.get(oid) or []
    return objs[0] if objs and isinstance(objs[0], dict) else {}


def band_label(band: str | None) -> str | None:
    """LTE_BC3 -> B3, NR_N78 -> n78."""
    if not band:
        return None
    if band.startswith("LTE_BC"):
        return f"B{band[6:]}"
    if band.startswith("NR_N"):
        return f"n{band[4:]}"
    if band.startswith("BC"):
        return f"B{band[2:]}"
    if band.startswith("N") and band[1:].isdigit():
        return f"n{band[1:]}"
    return band


def lte_bw(index: Any) -> float | None:
    """Convert LTE bandwidth index to MHz."""
    return LTE_BANDWIDTH_MHZ.get(index) if isinstance(index, int) else None


def nr_bw(index: Any) -> float | None:
    """Convert NR bandwidth index to MHz."""
    return NR_BANDWIDTH_MHZ.get(index) if isinstance(index, int) else None


def valid(
    value: Any, invalid: tuple[Any, ...] = (-1, -120, -140, -240, -32768, 0x7FFFFFFF)
) -> Any:
    """Return None for sentinel values."""
    if value is None or value in invalid or value == "":
        return None
    return value


def parse_operator(network_in_use: str | None) -> tuple[str | None, str | None]:
    """Parse 'Current_Magenta-T-_NR-NSA EN-DC_23203' -> (name, plmn)."""
    if not network_in_use:
        return None, None
    text = network_in_use
    if text.startswith("Current_"):
        text = text[8:]
    parts = text.rsplit("_", 2)
    if len(parts) == 3:
        name, _tech, plmn = parts
        return name.strip("-_ ") or None, plmn or None
    return text, None


def counter_delta(prev: int | None, cur: int | None) -> int | None:
    """Delta of a (possibly 32 bit wrapping) counter, None on reset."""
    if prev is None or cur is None:
        return None
    if cur >= prev:
        return cur - prev
    if prev < COUNTER_WRAP:
        return cur + COUNTER_WRAP - prev
    return None


@dataclass
class ZyxelData:
    """Container for all polled data."""

    raw: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    features: set[str] = field(default_factory=set)
    rx_rate: float | None = None  # bit/s
    tx_rate: float | None = None  # bit/s
    sms_inbox: list[dict[str, Any]] = field(default_factory=list)

    # --------------------------------------------------------------- objects
    @property
    def cell(self) -> dict[str, Any]:
        return first(self.raw, "cellwan_status")

    @property
    def status(self) -> dict[str, Any]:
        return first(self.raw, "status")

    @property
    def device_info(self) -> dict[str, Any]:
        return self.status.get("DeviceInfo") or {}

    @property
    def cell_intf(self) -> dict[str, Any]:
        """status.CellIntfInfo (contains temperatures)."""
        return self.status.get("CellIntfInfo") or {}

    @property
    def apn(self) -> str | None:
        for ap in self.status.get("CellAccessPointInfo") or []:
            if ap.get("Enable") and ap.get("APN"):
                return ap["APN"]
        return None

    def temperature(self, key: str) -> float | None:
        value = self.cell_intf.get(f"X_ZYXEL_TEMPERATURE_{key}")
        if not isinstance(value, (int, float)) or value <= -100 or value == 0:
            return None
        return value

    @property
    def band(self) -> dict[str, Any]:
        return first(self.raw, "cellwan_band")

    @property
    def lock(self) -> dict[str, Any]:
        return first(self.raw, "cellwan_lock")

    @property
    def nr_lock(self) -> dict[str, Any]:
        return first(self.raw, "cellwan_nr_lock")

    @property
    def sim(self) -> dict[str, Any]:
        return first(self.raw, "cellwan_sim")

    @property
    def gnss(self) -> dict[str, Any]:
        return first(self.raw, "cellwan_gnss")

    @property
    def cellwan(self) -> dict[str, Any]:
        return first(self.raw, "cellwan")

    @property
    def wlan(self) -> list[dict[str, Any]]:
        return self.raw.get("wlan") or []

    @property
    def traffic(self) -> dict[str, Any]:
        return first(self.raw, "Traffic_Status")

    @property
    def lanhosts(self) -> list[dict[str, Any]]:
        return first(self.raw, "lanhosts").get("lanhosts") or []

    # ------------------------------------------------------------- derived
    @property
    def wan(self) -> dict[str, Any]:
        """Default gateway WAN entry from status.WanLanInfo."""
        entries = self.status.get("WanLanInfo") or []
        wans = [e for e in entries if e.get("X_ZYXEL_Type") == "WAN"]
        for entry in wans:
            if entry.get("X_ZYXEL_DefaultGatewayIface"):
                return entry
        return wans[0] if wans else {}

    @property
    def wan_ipv4(self) -> str | None:
        for addr in self.wan.get("IPv4Address") or []:
            if addr.get("IPAddress"):
                return addr["IPAddress"]
        return None

    @property
    def wan_ipv6(self) -> str | None:
        for addr in self.wan.get("IPv6Address") or []:
            ip = addr.get("IPAddress")
            if ip and not ip.lower().startswith("fe80"):
                return ip
        return None

    @property
    def wan_dns(self) -> str | None:
        servers = [
            s.get("DNSServer") for s in self.wan.get("dnsv4Server") or [] if s.get("DNSServer")
        ]
        return ",".join(servers) or None

    def _wan_iface_index(self) -> int | None:
        ifaces = self.traffic.get("ipIface") or []
        for idx, iface in enumerate(ifaces):
            if iface.get("X_ZYXEL_DefaultGatewayIface"):
                return idx
        for idx, iface in enumerate(ifaces):
            if iface.get("Name") == "WAN" and iface.get("Status") == "Up":
                return idx
        return None

    @property
    def wan_iface(self) -> dict[str, Any]:
        idx = self._wan_iface_index()
        return (self.traffic.get("ipIface") or [])[idx] if idx is not None else {}

    @property
    def wan_stats(self) -> dict[str, Any]:
        """Byte counters of the WAN interface (IP or underlying PPP interface)."""
        idx = self._wan_iface_index()
        if idx is None:
            return {}
        iface = (self.traffic.get("ipIface") or [])[idx]
        lower = str(iface.get("LowerLayers") or "")
        ppp_stats = self.traffic.get("pppIfaceSt") or []
        if lower.startswith("PPP.Interface.") and ppp_stats:
            try:
                ppp_idx = int(lower.split(".")[2].rstrip(",")) - 1
            except (IndexError, ValueError):
                ppp_idx = 0
            if 0 <= ppp_idx < len(ppp_stats):
                return ppp_stats[ppp_idx]
        stats = self.traffic.get("ipIfaceSt") or []
        return stats[idx] if idx < len(stats) else {}

    @property
    def wan_link_type(self) -> str | None:
        """CELL, DSL, ETH, PON, ... of the default WAN."""
        link = self.wan.get("LinkType")
        return str(link).lower() if link else None

    @property
    def wan_connected(self) -> bool | None:
        wan = self.wan
        cell_status = self.cell.get("INTF_Status")
        if not wan and cell_status is None:
            return None
        wan_up = wan.get("Status", "Up") == "Up" if wan else True
        ppp = wan.get("pppConnectionStatus")
        if ppp:
            wan_up = wan_up and ppp == "Connected"
        if cell_status is not None and (wan.get("LinkType") or "CELL") == "CELL":
            return cell_status == "Up" and wan_up
        return wan_up

    # ----------------------------------------------------------------- DSL
    @property
    def dsl_channels(self) -> list[dict[str, Any]]:
        return [c for c in self.status.get("DslChannelInfo") or [] if isinstance(c, dict)]

    @property
    def dsl(self) -> dict[str, Any]:
        """Active (or first) DSL channel."""
        channels = self.dsl_channels
        for channel in channels:
            if channel.get("Status") == "Up":
                return channel
        return channels[0] if channels else {}

    def dsl_rate(self, key: str) -> float | None:
        """DSL sync rate in Mbit/s (DAL reports kbit/s)."""
        value = self.dsl.get(key)
        if not isinstance(value, (int, float)) or value <= 0:
            return None
        return round(value / 1000, 3)

    # ---------------------------------------------------------------- GPON
    @property
    def gpon(self) -> dict[str, Any]:
        info = self.status.get("GponStatsInfo") or {}
        # AX7501 nests the values one level deeper
        nested = info.get("gponStatusObj")
        return {**info, **nested} if isinstance(nested, dict) else info

    def gpon_value(self, key: str) -> float | None:
        """Parse a GPON value like '-18.5' or '-18.5 dBm'; '0'/'' means not available."""
        raw = self.gpon.get(key)
        if raw in (None, "", "0", 0):
            return None
        match = re.search(r"-?\d+(?:\.\d+)?", str(raw))
        return float(match.group()) if match else None

    # ----------------------------------------------------------------- LAN
    @property
    def lan_ports(self) -> list[dict[str, Any]]:
        return [p for p in self.status.get("LanPortInfo") or [] if isinstance(p, dict)]

    @property
    def operator(self) -> str | None:
        return parse_operator(self.cell.get("INTF_Network_In_Use"))[0]

    @property
    def plmn(self) -> str | None:
        plmn = parse_operator(self.cell.get("INTF_Network_In_Use"))[1]
        if plmn:
            return plmn
        mcc, mnc = self.cell.get("NSA_MCC"), self.cell.get("NSA_MNC")
        return f"{mcc}{mnc}" if mcc and mnc else None

    @property
    def scc(self) -> list[dict[str, Any]]:
        return [s for s in self.cell.get("SCC_Info") or [] if s.get("Enable")]

    @property
    def nr_active(self) -> bool:
        cell = self.cell
        tech = cell.get("INTF_Current_Access_Technology") or ""
        return bool(cell.get("NSA_Enable")) or tech.startswith("NR")

    @property
    def carriers(self) -> list[dict[str, Any]]:
        """All aggregated carriers (PCC, SCCs, NR leg)."""
        cell = self.cell
        out: list[dict[str, Any]] = []
        if cell.get("INTF_Current_Band"):
            out.append(
                {
                    "role": "PCC",
                    "band": band_label(cell.get("INTF_Current_Band")),
                    "pci": valid(cell.get("INTF_PhyCell_ID")),
                    "earfcn": valid(cell.get("INTF_RFCN")),
                    "dl_bandwidth_mhz": lte_bw(cell.get("INTF_Downlink_Bandwidth"))
                    if not (cell.get("INTF_Current_Access_Technology") or "").startswith("NR5G-SA")
                    else nr_bw(cell.get("INTF_Downlink_Bandwidth")),
                    "rsrp": valid(cell.get("INTF_RSRP")),
                    "rsrq": valid(cell.get("INTF_RSRQ")),
                    "sinr": valid(cell.get("INTF_SINR")),
                }
            )
        for scc in self.scc:
            bw = scc.get("DownlinkBandwidth")
            try:
                bw_mhz: float | None = float(bw) if bw not in (None, "", "-1") else None
            except ValueError:
                bw_mhz = None
            out.append(
                {
                    "role": "SCC",
                    "band": band_label(scc.get("Band")),
                    "pci": valid(scc.get("PhysicalCellID")),
                    "earfcn": valid(scc.get("RFCN")),
                    "dl_bandwidth_mhz": bw_mhz or lte_bw(scc.get("DL_BW")),
                    "rsrp": valid(scc.get("RSRP")),
                    "rsrq": valid(scc.get("RSRQ")),
                    "sinr": valid(scc.get("SINR")),
                }
            )
        if cell.get("NSA_Enable") and cell.get("NSA_Band"):
            out.append(
                {
                    "role": "NR",
                    "band": band_label(cell.get("NSA_Band")),
                    "pci": valid(cell.get("NSA_PCI")),
                    "earfcn": valid(cell.get("NSA_RFCN")),
                    "dl_bandwidth_mhz": nr_bw(cell.get("NSA_DL_BW")),
                    "rsrp": valid(cell.get("NSA_RSRP")),
                    "rsrq": valid(cell.get("NSA_RSRQ")),
                    "sinr": valid(cell.get("NSA_SINR")),
                }
            )
        return out

    @property
    def total_dl_bandwidth(self) -> float | None:
        values = [c["dl_bandwidth_mhz"] for c in self.carriers if c.get("dl_bandwidth_mhz")]
        return sum(values) if values else None

    @property
    def ca_bands(self) -> str | None:
        bands = [c["band"] for c in self.carriers if c.get("band")]
        return "+".join(bands) if bands else None

    @property
    def enb_id(self) -> int | None:
        cell_id = valid(self.cell.get("INTF_Cell_ID"))
        if cell_id is None:
            return None
        return self.cell.get("INTF_SiteID") or (int(cell_id) >> 8)

    @property
    def sector_id(self) -> int | None:
        cell_id = valid(self.cell.get("INTF_Cell_ID"))
        return int(cell_id) & 0xFF if cell_id is not None else None

    @property
    def gnss_position(self) -> tuple[float, float] | None:
        gnss = self.gnss
        lat, lon = gnss.get("GNSS_Latitude"), gnss.get("GNSS_Longitude")
        if not gnss.get("GNSS_Enable") or not lat or not lon:
            return None
        return lat / 1_000_000, lon / 1_000_000

    @property
    def active_hosts(self) -> list[dict[str, Any]]:
        return [h for h in self.lanhosts if h.get("Active")]

    @property
    def wifi_clients(self) -> int:
        return sum(
            1
            for h in self.active_hosts
            if h.get("X_ZYXEL_ConnectionType", "").lower().startswith(("802.11", "wi"))
            or h.get("AssociatedDevice")
        )

    @property
    def preferred_bands(self) -> str | None:
        return self.band.get("INTF_Preferred_Bands")

    @property
    def supported_bands(self) -> list[str]:
        bands = self.band.get("INTF_Supported_Bands") or self.cell.get("INTF_Supported_Bands")
        return [b for b in (bands or "").split(",") if b]

    @property
    def network_modes(self) -> list[str]:
        supported = self.band.get("INTF_Supported_Access_Technologies") or ""
        return ["Auto", *[m for m in supported.split(",") if m]]

    def detect_features(self) -> set[str]:
        """Detect features from the polled raw data."""
        feats: set[str] = set()
        if self.cell:
            feats.add(FEATURE_CELLULAR)
        if "NSA_Enable" in self.cell or any(
            b.startswith("NR_") for b in self.supported_bands
        ):
            feats.add(FEATURE_NR)
        if "GNSS_Enable" in self.gnss:
            feats.add(FEATURE_GNSS)
        if self.wlan:
            feats.add(FEATURE_WLAN)
        if first(self.raw, "cellwan_sms"):
            feats.add(FEATURE_SMS)
        if "LK_Enable" in self.lock:
            feats.add(FEATURE_CELL_LOCK)
        if "PCI_Enable" in self.nr_lock:
            feats.add(FEATURE_NR_LOCK)
        if "INTF_Preferred_Bands" in self.band:
            feats.add(FEATURE_BAND)
        if any(k.startswith("X_ZYXEL_TEMPERATURE_") for k in self.cell_intf):
            feats.add(FEATURE_TEMPERATURE)
        if self.dsl_channels:
            feats.add(FEATURE_DSL)
        gpon = self.gpon
        if gpon.get("SFP_Presence") not in (None, "", "0", 0, False) or self.gpon_value(
            "RxPowerSignal"
        ) is not None:
            feats.add(FEATURE_GPON)
        return feats
