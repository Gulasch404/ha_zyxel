# Zyxel Router – Home Assistant Integration

Lokale Integration für Zyxel-Router mit der Vue-basierten Weboberfläche (DAL-API), z. B. **NR7101**.
Weitere Modelle der NR/FWA/VMG/EX-Serie sollten funktionieren. Was das jeweilige Gerät unterstützt,
wird automatisch erkannt.

Getestet: **NR7101**, Firmware `1.00(ABUV.11)C0`, Modem `RG502QEAAAR11A03M4G`.

## Funktionen

**Sensoren**
- Mobilfunk: Zugangstechnologie, Betreiber/PLMN, Primärband, aggregierte Bänder (CA) mit
  Detail-Attributen je Träger, Anzahl Träger, gesamte Downlink-Bandbreite
- Signal: RSSI, RSRP, RSRQ, SINR, CQI, MCS, RI (LTE) sowie RSRP/RSRQ/SINR/Band/PCI/ARFCN (5G)
- Zelle: Cell-ID, eNB-ID, PCI, EARFCN, TAC, UL/DL-Bandbreite
- WAN: IPv4/IPv6, DNS, Download-/Upload-Rate (wrap-sicher aus 32-Bit-Zählern berechnet),
  Datenvolumen, verbunden seit
- System: letzter Neustart, Temperaturen (CPU, Modem, Umgebung), LAN-Geschwindigkeit,
  verbundene Geräte, WLAN-Geräte
- SIM: Status, IMEI/IMSI/ICCID (standardmäßig deaktiviert), APN, bevorzugte Bänder
- GNSS: Satelliten, Höhe, letzte Positionsbestimmung, Position als Device-Tracker
  (standardmäßig deaktiviert)
- SMS-Posteingang inkl. Event `zyxel_router_sms_received`, wenn das Gerät SMS unterstützt

**Binärsensoren:** Mobilfunkverbindung, 5G aktiv, Roaming erlaubt, SIM-Problem, Band-Lock,
LTE-/5G-Zell-Lock, IP-Passthrough

**Steuerung**
- Neustart-Button, Aktualisieren-Button
- WLAN an/aus
- *(nach Freigabe)* Netzmodus (Select), Daten-Roaming (Switch)
- *(nach Freigabe)* Aktionen `set_preferred_bands`, `set_network_mode`, `set_cell_lock`,
  `clear_cell_lock`, `set_nr_cell_lock`, `clear_nr_cell_lock`
- `dal_get`: liest eine beliebige DAL-OID (Antwort als Service-Response)
- `dal_set`: schreibt eine beliebige DAL-OID (Experte, muss in den Optionen freigegeben werden)

## Sicherheit bei Mobilfunk-Änderungen

Ein falscher Band- oder Zell-Lock kann einen Außen-Router dauerhaft offline nehmen. Deshalb gilt:

1. **Alle verbindungsrelevanten Änderungen sind standardmäßig gesperrt.** Freigabe unter
   *Einstellungen → Geräte & Dienste → Zyxel Router → Konfigurieren → Mobilfunk-Änderungen erlauben*.
2. **Auto-Revert-Watchdog:** Vor jeder Änderung wird der aktuelle Zustand gesichert. Steht die
   Mobilfunkverbindung (Status *Up* und WAN-IP vorhanden) nicht innerhalb des Zeitlimits
   (Standard: 240 s) zweimal hintereinander, stellt die Integration die vorherige Einstellung
   automatisch wieder her. Dazu kommen eine Benachrichtigung und das Event
   `zyxel_router_cellular_change_reverted`.
   Das funktioniert, weil HA den Router über das LAN erreicht, auch wenn die Mobilfunkverbindung
   weg ist. **Voraussetzung:** HA läuft während des Zeitfensters weiter.
3. Band-Listen ohne LTE-Band werden abgelehnt, solange der Modus nicht *5G SA* ist, weil 5G NSA
   einen LTE-Anker braucht.
4. Der Zell-Scan (QSCAN) ist bewusst nicht eingebaut, weil er die Datenverbindung unterbricht.
5. `dal_set` ist **nicht** durch den Watchdog geschützt.

### Beispiele

```yaml
action: zyxel_router.set_preferred_bands
data:
  bands: ["B3", "B1", "B8", "n78"]   # oder ["auto"]
```

```yaml
action: zyxel_router.set_cell_lock
data:
  cells:
    - pci: 400
      earfcn: 1300
```

```yaml
action: zyxel_router.dal_get
data:
  oid: cellwan_status
response_variable: result
```

## Installation

### HACS
1. HACS → Benutzerdefinierte Repositories → dieses Repository als *Integration* hinzufügen
2. „Zyxel Router“ installieren, Home Assistant neu starten
3. *Einstellungen → Geräte & Dienste → Integration hinzufügen → Zyxel Router*

### Manuell
`custom_components/zyxel_router` nach `<config>/custom_components/` kopieren und HA neu starten.

## Hinweise
- Polling: Signal und Traffic alle 30 s (einstellbar), alles andere alle 300 s und nach jeder
  Änderung. Der Router bietet weder Push noch Events. Sein MQTT-Client ist für `admin`
  ausgeblendet.
- Ist der Router über HTTPS mit selbstsigniertem Zertifikat erreichbar, „SSL-Zertifikat prüfen“
  deaktiviert lassen. Über HTTP verschlüsselt die Integration die Daten wie die Weboberfläche
  selbst (RSA + AES-256).
- Der Benutzer `admin` hat bei Zyxel nur das Level „medium“. LED, SMS-Versand und MQTT sind damit
  nicht verfügbar.
- Diagnosedaten (Geräteseite → Diagnose herunterladen) sind anonymisiert und helfen bei der
  Unterstützung weiterer Modelle.

## Entwicklung

```bash
python tools/gen_translations.py   # strings.json + en/de aus einer Quelle
```

Home Assistant läuft nicht nativ unter Windows. Tests daher unter Linux/WSL oder per Docker:

```powershell
# einmalig: Image mit HA-Testabhängigkeiten bauen
docker run --name zyxel-test-build python:3.14-slim pip install -q pytest-homeassistant-custom-component
docker commit zyxel-test-build zyxel-ha-test:latest; docker rm zyxel-test-build

# Tests
docker run --rm -v "${PWD}:/src:ro" zyxel-ha-test:latest bash -c `
  "mkdir /work && cd /src && tar --exclude=.venv -cf - . | tar -xf - -C /work && cd /work && pytest -q"
```

`tools/probe.py` liest alle bekannten OIDs eines Geräts aus (nur lesend), um neue Modelle zu
analysieren:

```bash
ZYXEL_HOST=http://192.168.1.1 ZYXEL_USER=admin ZYXEL_PASS=... python tools/probe.py dumps/
```
