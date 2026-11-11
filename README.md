# Zyxel Router for Home Assistant

[![Open your Home Assistant instance and open this repository in the Marketplace.](https://my.home-assistant.io/badges/marketplace_repository.svg)](https://my.home-assistant.io/redirect/marketplace_repository/?owner=Gulasch404&repository=ha_zyxel&category=integration)

Monitor and control Zyxel 5G/LTE routers locally from Home Assistant: signal quality, cells and
bands, throughput, temperatures, GPS position and more. No cloud involved.

## Supported devices

| Device | Status |
| --- | --- |
| **NR7101** (5G outdoor router) | Tested (firmware `1.00(ABUV.11)C0`) |
| Other Zyxel NR / FWA / VMG / EX models with the same web interface | Expected to work. Available features are detected automatically. |

Running a different model? Please open an issue and attach the diagnostics file (see
[Troubleshooting](#troubleshooting)).

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
| Username / Password | The login of the router's web interface (usually `admin`). |
| Verify SSL certificate | Leave off; the routers use a self-signed certificate. |

## What you get

### Sensors

| Area | Entities |
| --- | --- |
| Connection | Access technology (e.g. 5G NSA), operator, primary band, aggregated bands (with per-carrier details), number of carriers, total bandwidth |
| LTE signal | RSSI, RSRP, RSRQ, SINR, CQI, MCS, rank indicator |
| 5G signal | Band, RSRP, RSRQ, SINR, PCI, ARFCN |
| Cell | Cell ID, eNB ID, PCI, EARFCN, TAC, uplink/downlink bandwidth |
| Internet | WAN IPv4/IPv6, download and upload rate, data received/sent, connected since |
| Device | Last boot, CPU/modem/ambient temperature, LAN link speed, connected clients, WiFi clients |
| SIM | SIM status, APN, preferred bands, IMEI, IMSI, ICCID |
| GPS | Satellites, altitude, last fix, position (device tracker) |
| SMS | Inbox count (only on models that support SMS) |

### Binary sensors

Mobile connection, 5G active, roaming allowed, SIM problem, band lock, LTE cell lock, 5G cell
lock, IP passthrough.

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
- **Entities briefly unavailable:** The router allows only a limited number of sessions. Logging
  into the web interface in a browser can end the integration's session; it logs in again
  automatically.
- **LED, SMS sending or MQTT missing:** The router firmware hides these functions from the
  `admin` account, so they cannot be offered.
- **Report a problem:** Open the device page → ⋮ → **Download diagnostics** and attach the file to
  an [issue](https://github.com/Gulasch404/ha_zyxel/issues). Serial number, IMEI, IMSI, ICCID, IP
  and MAC addresses, WiFi password and GPS position are removed from the file automatically.

## Notes

- The Zyxel logo is shown from Home Assistant 2026.3 onward.
- This is an unofficial community project and is not affiliated with or endorsed by Zyxel.
  Zyxel and the Zyxel logo are trademarks of Zyxel Group.

## License

[MIT](LICENSE)
