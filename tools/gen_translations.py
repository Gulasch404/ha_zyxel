"""Generate strings.json, translations/en.json and translations/de.json.

Single source of truth so that both languages always have identical keys.
Run: python tools/gen_translations.py
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "custom_components" / "zyxel_router"

# key: (en, de)
SENSORS = {
    "access_technology": ("Access technology", "Zugangstechnologie"),
    "operator": ("Operator", "Netzbetreiber"),
    "band": ("Primary band", "Primärband"),
    "ca_bands": ("Aggregated bands", "Aggregierte Bänder"),
    "carrier_count": ("Carriers", "Träger (CA)"),
    "total_bandwidth": ("Total downlink bandwidth", "Gesamte Downlink-Bandbreite"),
    "rssi": ("RSSI", "RSSI"),
    "rsrp": ("RSRP", "RSRP"),
    "rsrq": ("RSRQ", "RSRQ"),
    "sinr": ("SINR", "SINR"),
    "cqi": ("CQI", "CQI"),
    "mcs": ("MCS", "MCS"),
    "ri": ("Rank indicator", "Rank Indicator"),
    "cell_id": ("Cell ID", "Zell-ID"),
    "enb_id": ("eNB ID", "eNB-ID"),
    "pci": ("PCI", "PCI"),
    "earfcn": ("EARFCN", "EARFCN"),
    "tac": ("TAC", "TAC"),
    "dl_bandwidth": ("Primary downlink bandwidth", "Primäre Downlink-Bandbreite"),
    "ul_bandwidth": ("Primary uplink bandwidth", "Primäre Uplink-Bandbreite"),
    "nr_band": ("5G band", "5G-Band"),
    "nr_rsrp": ("5G RSRP", "5G RSRP"),
    "nr_rsrq": ("5G RSRQ", "5G RSRQ"),
    "nr_sinr": ("5G SINR", "5G SINR"),
    "nr_pci": ("5G PCI", "5G PCI"),
    "nr_arfcn": ("5G ARFCN", "5G ARFCN"),
    "sim_status": ("SIM status", "SIM-Status"),
    "imei": ("IMEI", "IMEI"),
    "imsi": ("IMSI", "IMSI"),
    "iccid": ("ICCID", "ICCID"),
    "preferred_bands": ("Preferred bands", "Bevorzugte Bänder"),
    "modem_firmware": ("Modem firmware", "Modem-Firmware"),
    "wan_ipv4": ("WAN IPv4", "WAN IPv4"),
    "wan_ipv6": ("WAN IPv6", "WAN IPv6"),
    "download_rate": ("Download rate", "Download-Rate"),
    "upload_rate": ("Upload rate", "Upload-Rate"),
    "wan_received": ("WAN received", "WAN empfangen"),
    "wan_sent": ("WAN sent", "WAN gesendet"),
    "wan_connected_since": ("WAN connected since", "WAN verbunden seit"),
    "last_boot": ("Last boot", "Letzter Neustart"),
    "clients": ("Connected clients", "Verbundene Geräte"),
    "wifi_clients": ("WiFi clients", "WLAN-Geräte"),
    "lan_speed": ("LAN link speed", "LAN-Verbindungsgeschwindigkeit"),
    "apn": ("APN", "APN"),
    "temperature_cpu": ("CPU temperature", "CPU-Temperatur"),
    "temperature_modem": ("Modem temperature", "Modem-Temperatur"),
    "temperature_ambient": ("Ambient temperature", "Umgebungstemperatur"),
    "gnss_satellites":("GNSS satellites", "GNSS-Satelliten"),
    "gnss_altitude": ("GNSS altitude", "GNSS-Höhe"),
    "gnss_last_fix": ("GNSS last fix", "GNSS letzte Positionsbestimmung"),
    "sms_inbox": ("SMS inbox", "SMS-Posteingang"),
}
BINARY = {
    "wan_connected": ("Mobile connection", "Mobilfunkverbindung"),
    "nr_connected": ("5G active", "5G aktiv"),
    "roaming": ("Roaming allowed", "Roaming erlaubt"),
    "sim_ready": ("SIM problem", "SIM-Problem"),
    "band_lock": ("Band lock", "Band-Lock"),
    "cell_lock": ("LTE cell lock", "LTE Zell-Lock"),
    "nr_cell_lock": ("5G cell lock", "5G Zell-Lock"),
    "ip_passthrough": ("IP passthrough", "IP-Passthrough"),
}
SIM_STATES = {
    "ready": ("Ready", "Bereit"),
    "not_inserted": ("Not inserted", "Nicht eingelegt"),
    "pin_required": ("PIN required", "PIN erforderlich"),
    "puk_required": ("PUK required", "PUK erforderlich"),
    "error": ("Error", "Fehler"),
}
NETWORK_MODES = {
    "auto": ("Automatic", "Automatisch"),
    "nr5g_nsa": ("5G NSA (with LTE)", "5G NSA (mit LTE)"),
    "nr5g_sa": ("5G SA only", "Nur 5G SA"),
    "lte": ("LTE only", "Nur LTE"),
    "umts": ("3G only", "Nur 3G"),
}
EXCEPTIONS = {
    "cellular_changes_disabled": (
        "Cellular changes are disabled. Enable them in the integration options first.",
        "Mobilfunk-Änderungen sind deaktiviert. Aktiviere sie zuerst in den Optionen der Integration.",
    ),
    "change_in_progress": (
        "Another cellular change is still being verified. Please wait.",
        "Eine andere Mobilfunk-Änderung wird noch überprüft. Bitte warten.",
    ),
    "invalid_band": (
        "Band {band} is not supported. Supported: {supported}",
        "Band {band} wird nicht unterstützt. Unterstützt: {supported}",
    ),
    "invalid_mode": (
        "Mode {mode} is not supported. Supported: {supported}",
        "Modus {mode} wird nicht unterstützt. Unterstützt: {supported}",
    ),
    "no_lte_anchor": (
        "The band list contains no LTE band. Without an LTE anchor 5G NSA cannot connect. Switch to 5G SA mode first or add an LTE band.",
        "Die Bandliste enthält kein LTE-Band. Ohne LTE-Anker kann 5G NSA nicht verbinden. Zuerst auf 5G SA umstellen oder ein LTE-Band ergänzen.",
    ),
    "cell_count": ("Between 1 and 5 cells are required.", "Es sind 1 bis 5 Zellen erforderlich."),
    "invalid_cell": ("Invalid PCI or EARFCN.", "Ungültige PCI oder EARFCN."),
    "invalid_scs": ("SCS must be 15, 30, 60 or 120 kHz.", "SCS muss 15, 30, 60 oder 120 kHz sein."),
    "unknown_device": ("Unknown device.", "Unbekanntes Gerät."),
    "device_required": (
        "Please select a Zyxel device.",
        "Bitte ein Zyxel-Gerät auswählen.",
    ),
    "sms_not_supported": (
        "This device does not support SMS.",
        "Dieses Gerät unterstützt keine SMS.",
    ),
    "raw_writes_disabled": (
        "Raw DAL writes are disabled in the integration options.",
        "Rohe DAL-Schreibzugriffe sind in den Optionen deaktiviert.",
    ),
}
ISSUES = {
    "cellular_change_reverted": (
        ("Zyxel: cellular change reverted", "Zyxel: Mobilfunk-Änderung zurückgenommen"),
        (
            "After the change **{change}** the cellular connection did not come back within {timeout} seconds. The previous setting has been restored automatically. This message disappears after the next successful change.",
            "Nach der Änderung **{change}** kam die Mobilfunkverbindung nicht innerhalb von {timeout} Sekunden zurück. Die vorherige Einstellung wurde automatisch wiederhergestellt. Diese Meldung verschwindet nach der nächsten erfolgreichen Änderung.",
        ),
    ),
    "cellular_revert_failed": (
        ("Zyxel: restoring cellular settings failed", "Zyxel: Wiederherstellung der Mobilfunk-Einstellungen fehlgeschlagen"),
        (
            "After the change **{change}** the cellular connection did not come back within {timeout} seconds, and restoring the previous setting failed. Check the router web interface (via LAN) and reset band/cell lock and network mode to automatic.",
            "Nach der Änderung **{change}** kam die Mobilfunkverbindung nicht innerhalb von {timeout} Sekunden zurück, und die Wiederherstellung der vorherigen Einstellung ist fehlgeschlagen. Prüfe die Weboberfläche des Routers (über LAN) und setze Band-/Zell-Lock und Netzmodus auf automatisch zurück.",
        ),
    ),
}
DEVICE_FIELD =("Device", "Gerät", "Zyxel device (optional with only one router).", "Zyxel-Gerät (optional bei nur einem Router).")
SERVICES = {
    "set_preferred_bands": (
        ("Set preferred bands", "Bevorzugte Bänder setzen"),
        (
            "Restricts the modem to the given bands. Protected by the auto-revert watchdog.",
            "Beschränkt das Modem auf die angegebenen Bänder. Durch den Auto-Revert-Watchdog geschützt.",
        ),
        {
            "bands": (
                "Bands",
                "Bänder",
                'List like ["B3","B1","n78"] or ["auto"] for automatic.',
                'Liste wie ["B3","B1","n78"] oder ["auto"] für automatisch.',
            )
        },
    ),
    "set_network_mode": (
        ("Set network mode", "Netzmodus setzen"),
        ("Sets the preferred access technology (watchdog protected).", "Setzt die bevorzugte Zugangstechnologie (Watchdog-geschützt)."),
        {"mode": ("Mode", "Modus", "Access technology.", "Zugangstechnologie.")},
    ),
    "set_cell_lock": (
        ("Set LTE cell lock", "LTE Zell-Lock setzen"),
        ("Locks LTE to up to 5 cells (watchdog protected).", "Sperrt LTE auf bis zu 5 Zellen (Watchdog-geschützt)."),
        {
            "cells": (
                "Cells",
                "Zellen",
                "List of up to 5 cells, each with pci and earfcn (see example).",
                "Liste von bis zu 5 Zellen, jeweils mit pci und earfcn (siehe Beispiel).",
            )
        },
    ),
    "clear_cell_lock": (
        ("Clear LTE cell lock", "LTE Zell-Lock aufheben"),
        ("Disables the LTE cell lock.", "Deaktiviert den LTE Zell-Lock."),
        {},
    ),
    "set_nr_cell_lock": (
        ("Set 5G SA cell lock", "5G SA Zell-Lock setzen"),
        ("Locks to a 5G cell. Only effective in 5G SA mode (watchdog protected).", "Sperrt auf eine 5G-Zelle. Nur im 5G-SA-Modus wirksam (Watchdog-geschützt)."),
        {
            "pci": ("PCI", "PCI", "Physical cell ID.", "Physikalische Zell-ID."),
            "arfcn": ("ARFCN", "ARFCN", "NR-ARFCN.", "NR-ARFCN."),
            "band": ("Band", "Band", "NR band number, e.g. 78.", "NR-Bandnummer, z. B. 78."),
            "scs": ("SCS", "SCS", "Subcarrier spacing in kHz.", "Unterträgerabstand in kHz."),
        },
    ),
    "clear_nr_cell_lock": (
        ("Clear 5G cell lock", "5G Zell-Lock aufheben"),
        ("Disables the 5G cell lock.", "Deaktiviert den 5G Zell-Lock."),
        {},
    ),
    "delete_sms": (
        ("Delete SMS", "SMS löschen"),
        ("Deletes an SMS from the inbox.", "Löscht eine SMS aus dem Posteingang."),
        {"index": ("Index", "Index", "Index of the message.", "Index der Nachricht.")},
    ),
    "dal_get": (
        ("Read DAL object", "DAL-Objekt lesen"),
        ("Reads any DAL OID from the router and returns it.", "Liest eine beliebige DAL-OID vom Router und gibt sie zurück."),
        {"oid": ("OID", "OID", "e.g. cellwan_status, status, wan", "z. B. cellwan_status, status, wan")},
    ),
    "dal_set": (
        ("Write DAL object (expert)", "DAL-Objekt schreiben (Experte)"),
        (
            "Writes any DAL OID. NOT protected by the watchdog! Must be enabled in the options.",
            "Schreibt eine beliebige DAL-OID. NICHT durch den Watchdog geschützt! Muss in den Optionen aktiviert sein.",
        ),
        {
            "oid": ("OID", "OID", "DAL object ID.", "DAL-Objekt-ID."),
            "method": ("Method", "Methode", "HTTP method.", "HTTP-Methode."),
            "payload": ("Payload", "Payload", "JSON object to send.", "Zu sendendes JSON-Objekt."),
            "params": ("Parameters", "Parameter", "Additional query parameters (e.g. Index).", "Zusätzliche Query-Parameter (z. B. Index)."),
        },
    ),
}


def build(lang: int) -> dict:
    i = lang  # 0 = en, 1 = de
    en = i == 0
    host_desc = (
        "URL of the web interface, e.g. http://192.168.1.1 (HTTPS also works)."
        if en
        else "URL der Weboberfläche, z. B. http://192.168.1.1 (HTTPS geht auch)."
    )
    user_fields = {
        "host": "Host",
        "username": "Username" if en else "Benutzername",
        "password": "Password" if en else "Passwort",
        "verify_ssl": "Verify SSL certificate" if en else "SSL-Zertifikat prüfen",
    }
    errors = {
        "cannot_connect": "Failed to connect" if en else "Verbindung fehlgeschlagen",
        "invalid_auth": "Invalid authentication" if en else "Ungültige Anmeldedaten",
        "unknown": "Unexpected error" if en else "Unerwarteter Fehler",
    }
    services = {}
    for name, (title, desc, fields) in SERVICES.items():
        f = {
            "device_id": {"name": DEVICE_FIELD[i], "description": DEVICE_FIELD[2 + i]}
        }
        for fk, fv in fields.items():
            f[fk] = {"name": fv[i], "description": fv[2 + i]}
        services[name] = {"name": title[i], "description": desc[i], "fields": f}

    return {
        "config": {
            "step": {
                "user": {
                    "title": "Zyxel Router",
                    "description": "Connect to a Zyxel router (NR/FWA/VMG/EX series)."
                    if en
                    else "Verbindung zu einem Zyxel-Router (NR/FWA/VMG/EX-Serie).",
                    "data": user_fields,
                    "data_description": {"host": host_desc},
                },
                "reauth_confirm": {
                    "title": "Re-authenticate" if en else "Erneut anmelden",
                    "data": {"username": user_fields["username"], "password": user_fields["password"]},
                },
                "reconfigure": {
                    "title": "Reconfigure" if en else "Neu konfigurieren",
                    "data": user_fields,
                    "data_description": {"host": host_desc},
                },
            },
            "error": errors,
            "abort": {
                "already_configured": "Device is already configured" if en else "Gerät ist bereits eingerichtet",
                "reauth_successful": "Re-authentication was successful" if en else "Erneute Anmeldung erfolgreich",
                "reconfigure_successful": "Reconfiguration was successful" if en else "Neukonfiguration erfolgreich",
                "unique_id_mismatch": "This is a different device" if en else "Das ist ein anderes Gerät",
            },
        },
        "options": {
            "step": {
                "init": {
                    "title": "Options" if en else "Optionen",
                    "data": {
                        "scan_interval": "Fast poll interval (s)" if en else "Schnelles Abfrageintervall (s)",
                        "slow_interval": "Slow poll interval (s)" if en else "Langsames Abfrageintervall (s)",
                        "allow_cellular_changes": "Allow cellular changes" if en else "Mobilfunk-Änderungen erlauben",
                        "revert_timeout": "Auto-revert timeout (s)" if en else "Auto-Revert-Zeitlimit (s)",
                        "allow_raw_writes": "Allow raw DAL writes (expert)" if en else "Rohe DAL-Schreibzugriffe erlauben (Experte)",
                    },
                    "data_description": {
                        "scan_interval": "Signal and traffic." if en else "Signal und Traffic.",
                        "slow_interval": "Device info, SIM, bands, locks, WLAN, GNSS, SMS." if en else "Geräteinfo, SIM, Bänder, Locks, WLAN, GNSS, SMS.",
                        "allow_cellular_changes": (
                            "Enables network mode, band/cell lock and roaming controls. Every change is verified and reverted automatically if the connection does not come back."
                            if en
                            else "Aktiviert Netzmodus, Band-/Zell-Lock und Roaming. Jede Änderung wird überwacht und automatisch zurückgenommen, wenn die Verbindung nicht wiederkommt."
                        ),
                        "revert_timeout": (
                            "Time the connection has to come back after a cellular change before the previous setting is restored."
                            if en
                            else "Zeit, in der die Verbindung nach einer Mobilfunk-Änderung wiederkommen muss, bevor die vorherige Einstellung wiederhergestellt wird."
                        ),
                        "allow_raw_writes": (
                            "Allows the dal_set action. Not protected by the watchdog!"
                            if en
                            else "Erlaubt die Aktion dal_set. Nicht durch den Watchdog geschützt!"
                        ),
                    },
                }
            }
        },
        "entity": {
            "sensor": {
                k: {"name": v[i], **({"state": {s: t[i] for s, t in SIM_STATES.items()}} if k == "sim_status" else {})}
                for k, v in SENSORS.items()
            },
            "binary_sensor": {k: {"name": v[i]} for k, v in BINARY.items()},
            "switch": {
                "wlan": {"name": "WLAN {band}"},
                "roaming": {"name": "Data roaming" if en else "Daten-Roaming"},
            },
            "select": {
                "network_mode": {
                    "name": "Network mode" if en else "Netzmodus",
                    "state": {k: v[i] for k, v in NETWORK_MODES.items()},
                }
            },
            "button": {"refresh": {"name": "Refresh" if en else "Aktualisieren"}},
            "device_tracker": {"gnss": {"name": "GNSS position" if en else "GNSS-Position"}},
        },
        "exceptions": {k: {"message": v[i]} for k, v in EXCEPTIONS.items()},
        "issues": {k: {"title": v[0][i], "description": v[1][i]} for k, v in ISSUES.items()},
        "services": services,
    }


def main() -> None:
    en = build(0)
    (ROOT / "translations").mkdir(exist_ok=True)
    for path, data in (
        (ROOT / "strings.json", en),
        (ROOT / "translations" / "en.json", en),
        (ROOT / "translations" / "de.json", build(1)),
    ):
        path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
        )
        print("wrote", path)


if __name__ == "__main__":
    main()
