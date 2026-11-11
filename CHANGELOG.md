# Changelog

All notable changes to this integration are documented here. The newest version is at the top.

## [0.2.0] - 2026-11-11

Support for more Zyxel models: 5G/LTE, DSL and fiber/Ethernet WAN routers with the current web interface. Only the NR7101 is tested so far; see the supported devices list in the README and please [report your device](https://github.com/Gulasch404/ha_zyxel/issues/new?template=device_report.yml).

### Added

- DSL: line status, downstream/upstream sync rate and encapsulation sensors.
- Fiber: optical RX/TX power and optical module temperature sensors.
- WAN type sensor (cellular, DSL, Ethernet, fiber, …).
- One link speed sensor per LAN port on routers with more than one port.
- Supported devices list with test status in the README.
- "Device report" issue template.
- Diagnostics now include the router's menu structure, which shows the features of a model.

### Changed

- The internet connection status and traffic counters now work for all WAN types, including PPPoE.
- Guest WiFi switches get unique names (band and SSID).
- Device information is now read with the fast poll interval (one additional request per interval).

### Fixed

- "User is already logged in" (single-session firmwares) no longer asks for re-authentication; the integration retries automatically.
- Login and write compatibility with newer firmwares (session cookie, session key and CSRF token).
- Tolerant decryption for firmwares that use a different padding.

## [0.1.3] - 2026-11-11

### Added

- Home Assistant Marketplace category and "Open in Marketplace" button in the README.

## [0.1.2] - 2026-11-11

### Changed

- A reverted cellular change now shows a repair notice under **Settings → Repairs** instead of a persistent notification. The notice disappears after the next successful change.
- A separate repair notice appears if restoring the previous setting failed.
- Watchdog messages and logs are in English.
- README rewritten for end users.

## [0.1.1] - 2026-11-11

First release.

### Added

- Setup via the UI, with re-authentication, reconfiguration and options.
- Sensors for internet, device, 5G/LTE signal, cell, SIM, GPS and SMS.
- Binary sensors for connection, 5G, roaming, SIM, band lock and cell locks.
- WiFi switches, restart and refresh buttons, GPS device tracker.
- Network mode select and roaming switch, band and cell lock actions, all protected by the automatic revert and disabled by default.
- `dal_get` and `dal_set` expert actions, SMS event, diagnostics.
- English and German translations, Zyxel logo.

[0.2.0]: https://github.com/Gulasch404/ha_zyxel/compare/v0.1.3...v0.2.0
[0.1.3]: https://github.com/Gulasch404/ha_zyxel/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/Gulasch404/ha_zyxel/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/Gulasch404/ha_zyxel/releases/tag/v0.1.1
