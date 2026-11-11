# Zyxel Router for Home Assistant

[![Open your Home Assistant instance and open this repository in the Marketplace.](https://my.home-assistant.io/badges/marketplace_repository.svg)](https://my.home-assistant.io/redirect/marketplace_repository/?owner=Gulasch404&repository=ha_zyxel&category=integration)

Monitor and control Zyxel routers locally from Home Assistant: 5G/LTE signal, cells and bands,
DSL sync rates, fiber optical power, throughput, temperatures, GPS position and more. No cloud
involved.

## Supported devices

The integration works with Zyxel routers that use the current web interface (the one with the
"Connection Status" dashboard). It detects automatically what a device offers, so only matching
entities are created.

**Legend:** ✅ tested with this integration · 🟢 same interface confirmed by other open-source
projects, expected to work · ⚪ same product family, not confirmed yet · ❌ not compatible

### 5G / LTE

| Model | Status | Notes |
| --- | --- | --- |
| NR7101 | ✅ | Firmware `1.00(ABUV.11)C0` |
| NR7102, NR7302 | 🟢 | |
| NR5103E, NR5103 v2, NR5307 | 🟢 | |
| FWA505, FWA510, FWA515, FWA710 | 🟢 | |
| LTE3202-M437, LTE5398-M904, LTE7490-M904 | 🟢 | |
| NR7301, NR7303, NR5101, NR5111, NR5309, NR2301, NR2101, LTE3301-PLUS, LTE7461 | ⚪ | |
| NR5103 (v1, EE branded) | ⚪ | Login known to fail on some EE firmwares |
| LTE7460-M608, LTE4506-M606 | ❌ | Older web interface |

### DSL

| Model | Status | Notes |
| --- | --- | --- |
| VMG8825-T50, VMG8623-T50B, VMG4005-B50A | 🟢 | VMG4005: use a poll interval of 60 s or more |
| DX3301-T0, EX3301-T0 | 🟢 | |
| VMG3625-T50B | 🟢 | Login problems reported with some firmwares |
| DX3300, DX5401, EX5501 | ⚪ | |
| VMG1312-B10A/B30A, VMG3006-D70A, VMG8924 | ❌ | Older web interface |

### Fiber / Ethernet WAN

| Model | Status | Notes |
| --- | --- | --- |
| AX7501-B0/B1 | 🟢 | |
| EX5601-T1 | 🟢 | |
| EX3510, EX5510, PX3321-T1 | ⚪ | |
| PMG5617-R20B, EE5301, T56 | ❌ | Login not working with this interface generation |

DSL routers currently show the sync rates and line status; detailed line statistics (SNR margin,
attenuation) are not available through the interface yet.

**Your model is not listed, or you tested one marked 🟢 / ⚪?** Please
[report your device](https://github.com/Gulasch404/ha_zyxel/issues/new?template=device_report.yml)
and attach the diagnostics file. This is how models move to ✅.

## Installation

### Marketplace / HACS (recommended)

1. Click the button above. Or add the repository manually:
   - Home Assistant 2026.11 and newer: **Settings → Marketplace** → ⋮ → **Custom repositories**
   - Older versions with HACS: HACS → ⋮ → **Custom repositories**

   Repository `https://github.com/Gulasch404/ha_zyxel`, type **Integration**.
2. Download **Zyxel Router**. With HACS, restart Home Assistant afterwards.

### Manual

Copy `custom_components/zyxel_router` into your `config/custom_components/` folder and restart
Home Assistant.

## Setup

**Settings → Devices & services → Add integration → Zyxel Router**

| Field | Description |
| --- | --- |
| Host | Address of the router's web interface, e.g. `http://192.168.1.1`. `https://` works too. |
| Username / Password | The login of the router's web interface. Usually `admin`; some provider firmwares use `user`. Use the account with the most rights. |
| Verify SSL certificate | Leave off; the routers use a self-signed certificate. |

## What you get

### Sensors

| Area | Entities |
| --- | --- |
| Internet | WAN type, WAN IPv4/IPv6, download and upload rate, data received/sent, connected since |
| Device | Last boot, temperatures, link speed per LAN port, connected clients, WiFi clients |
| 5G/LTE connection | Access technology (e.g. 5G NSA), operator, primary band, aggregated bands (with per-carrier details), number of carriers, total bandwidth |
| LTE signal | RSSI, RSRP, RSRQ, SINR, CQI, MCS, rank indicator |
| 5G signal | Band, RSRP, RSRQ, SINR, PCI, ARFCN |
| Cell | Cell ID, eNB ID, PCI, EARFCN, TAC, uplink/downlink bandwidth |
| SIM | SIM status, APN, preferred bands, IMEI, IMSI, ICCID |
| GPS | Satellites, altitude, last fix, position (device tracker) |
| SMS | Inbox count |
| DSL | Line status, downstream/upstream sync rate, encapsulation |
| Fiber | Optical RX/TX power, optical module temperature |

Each group only appears if the device supports it.

### Binary sensors

Internet connection, plus for 5G/LTE devices: 5G active, roaming allowed, SIM problem, band lock,
LTE cell lock, 5G cell lock, IP passthrough.

### Controls

- **Restart** button
- **Refresh** button (reads everything from the router immediately)
- **WiFi** on/off
- **Network mode** select and **data roaming** switch (only after enabling cellular changes, see
  below)

### Privacy

IMEI, IMSI, ICCID, the GPS position and some diagnostic sensors are **disabled by default**. Enable
them on the device page if you need them.

## Options

**Settings → Devices & services → Zyxel Router → Configure**

| Option | Default | Description |
| --- | --- | --- |
| Fast poll interval | 30 s | Signal and traffic |
| Slow poll interval | 300 s | Device info, SIM, bands, locks, WiFi, GPS, SMS |
| Allow cellular changes | off | Enables network mode, band/cell lock and roaming controls |
| Auto-revert timeout | 240 s | See below |
| Allow raw DAL writes | off | Enables the expert action `dal_set` |

The router cannot push updates, so the integration polls it.

## Changing bands, cells and network mode safely

A wrong band or cell lock can take a router offline, which is a serious problem for a roof-mounted
outdoor unit. The integration therefore protects every connection-relevant change:

1. **Disabled by default.** Cellular controls only appear after you enable
   *Allow cellular changes* in the options.
2. **Automatic revert.** The current setting is saved before each change. If the cellular
   connection is not stable again within the auto-revert timeout, the previous setting is restored
   automatically and a repair notice appears under **Settings → Repairs**.
   Home Assistant reaches the router via the LAN, so this works even when the mobile connection is
   down, as long as Home Assistant keeps running during that time.
3. **Sanity checks.** Unsupported bands are rejected. A band list without any LTE band is rejected
   unless the network mode is 5G SA, because 5G NSA needs an LTE anchor.
4. The router's cell scan is deliberately not offered, as it interrupts the data connection.

`dal_set` is **not** protected by the automatic revert. Only use it if you know exactly what you
are doing.

## Actions

| Action | Description |
| --- | --- |
| `zyxel_router.set_preferred_bands` | Restrict the modem to specific bands, or `auto` |
| `zyxel_router.set_network_mode` | `Auto`, `NR5G-NSA`, `NR5G` (SA), `LTE`, `UMTS` |
| `zyxel_router.set_cell_lock` / `clear_cell_lock` | Lock LTE to up to 5 cells |
| `zyxel_router.set_nr_cell_lock` / `clear_nr_cell_lock` | Lock to a 5G cell (5G SA mode only) |
| `zyxel_router.delete_sms` | Delete an SMS from the inbox |
| `zyxel_router.dal_get` | Read any value from the router's API (returns a response) |
| `zyxel_router.dal_set` | Write any value (expert, must be enabled in the options) |

The band and cell actions need *Allow cellular changes* enabled.

```yaml
# Lock to the bands currently in use
action: zyxel_router.set_preferred_bands
data:
  bands: ["B3", "B1", "B8", "n78"]
```

```yaml
# Back to automatic band selection
action: zyxel_router.set_preferred_bands
data:
  bands: ["auto"]
```

```yaml
# Lock LTE to one cell (PCI and EARFCN are shown on the "Cell ID" sensor)
action: zyxel_router.set_cell_lock
data:
  cells:
    - pci: 400
      earfcn: 1300
```

```yaml
# Read raw data from the router
action: zyxel_router.dal_get
data:
  oid: cellwan_status
response_variable: result
```

## Events

| Event | When |
| --- | --- |
| `zyxel_router_sms_received` | A new SMS arrived (models with SMS support) |
| `zyxel_router_cellular_change_reverted` | A cellular change was reverted automatically |

## Troubleshooting

- **Cannot connect:** Open the host address in a browser from the Home Assistant network. If
  `https://` times out (e.g. blocked by a firewall), use `http://`. The login is encrypted by the
  integration just like in the router's own web interface.
- **"User is already logged in" / entities briefly unavailable:** Many Zyxel routers allow only
  one session per user. While you are logged into the web interface with the same account, the
  integration cannot log in; it retries automatically. Log out of the web interface (or wait about
  5 minutes), or use a separate account for Home Assistant if your router allows it. The same
  applies the other way round: if the web interface refuses your login, temporarily disable the
  integration (device page → ⋮ → Disable).
- **Router slow or unresponsive:** Some models (e.g. VMG4005-B50A) struggle with frequent polling.
  Increase the fast poll interval in the options to 60 seconds or more.
- **LED, SMS sending or MQTT missing:** The router firmware hides these functions from the
  `admin` account, so they cannot be offered.
- **Cellular controls:** Network mode, band and cell lock only exist on 5G/LTE devices.
- **Report a problem:** Open the device page → ⋮ → **Download diagnostics** and attach the file to
  an [issue](https://github.com/Gulasch404/ha_zyxel/issues). Serial number, IMEI, IMSI, ICCID, IP
  and MAC addresses, WiFi password and GPS position are removed from the file automatically.

## Notes

- The Zyxel logo is shown from Home Assistant 2026.3 onward.
- This is an unofficial community project and is not affiliated with or endorsed by Zyxel.
  Zyxel and the Zyxel logo are trademarks of Zyxel Group.

## License

[MIT](LICENSE)
