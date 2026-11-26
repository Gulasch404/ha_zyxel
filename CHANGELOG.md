# Changelog

All notable changes to this integration are documented here. The newest version is at the top.

## [0.2.4] - 2026-11-26

Privacy and robustness improvements from a review of the whole integration.

### Changed

- The clients sensor no longer lists host names, IP and MAC addresses in its attributes; only the count remains.
- The `zyxel_router_sms_received` event now carries `entry_id`, `index`, `from` and `time`. The message text is only included when the new option *Include SMS text in events* is enabled, because events are stored in the recorder database.
- The fast poll interval option was removed (Home Assistant guideline). Signal and traffic are polled every 30 seconds; to poll less often, disable polling in the system options and update from an automation, see the README.
- Diagnostics redact passwords, PINs, PUKs, APN and GPON credentials and similar fields on all models, not only a fixed list, and no longer send a request to the router.
- Network mode select and roaming switch are removed from the entity registry when *Allow cellular changes* is turned off instead of staying as unavailable entities.
- SIM status and WAN type are enum sensors; the SIM ready binary sensor is unknown instead of "problem" when the router reports no SIM status.
- Reconfigure keeps the stored password when the field is left empty; reauthentication checks that the credentials belong to the same router.
- Device information (firmware version) updates without a reload.
- Minimum Home Assistant version is 2025.3.
- Errors from the router are shown translated; precondition errors (cellular changes disabled, change in progress) no longer produce a traceback.

### Fixed

- If Home Assistant reloads the integration or restarts while a cellular change is being verified, the watchdog logs a warning that the change was not verified instead of disappearing silently.
- An unexpected error during setup shows "Unexpected error" instead of crashing the dialog.
- Values of a router object that stops responding are cleared instead of staying stale.
- Error messages no longer embed whole HTTP response bodies.

## [0.2.3] - 2026-11-26

### Changed

- The `dal_get` and `dal_set` actions can now only be called by administrators. They return and write raw router objects, including Wi-Fi passphrases and other secrets.
- README: the installation section now starts with the Marketplace / HACS search.

## [0.2.2] - 2026-11-25

### Fixed

- The translation source now contains the WiFi switch error messages added in 0.2.1, so the translation check in CI passes again. No functional change.

## [0.2.1] - 2026-11-25

Fixes from the HACS review: no SMS contents in sensor attributes, safer WiFi switches, closed HTTP sessions.

### Changed

- The SMS inbox sensor no longer exposes message contents (sender, text) as attributes; attributes are stored in the recorder database and visible to every dashboard user. The sensor keeps the message count; use the `zyxel_router_sms_received` event for message contents.
- WiFi switches only write settings the router actually returned. If the SSID, the passphrase or the WiFi object is missing, or the security mode is not WPA2-Personal or open, the switch raises an error instead of guessing values that could change the WiFi configuration.

### Fixed

- HTTP sessions are now closed when login or the first refresh fails and when the integration is unloaded.

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

[0.2.4]: https://github.com/Gulasch404/ha_zyxel/compare/v0.2.3...v0.2.4
[0.2.3]: https://github.com/Gulasch404/ha_zyxel/compare/v0.2.2...v0.2.3
[0.2.2]: https://github.com/Gulasch404/ha_zyxel/compare/v0.2.1...v0.2.2
[0.2.1]: https://github.com/Gulasch404/ha_zyxel/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/Gulasch404/ha_zyxel/compare/v0.1.3...v0.2.0
[0.1.3]: https://github.com/Gulasch404/ha_zyxel/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/Gulasch404/ha_zyxel/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/Gulasch404/ha_zyxel/releases/tag/v0.1.1
