# PiDrive — Kontext & Projektdokumentation v0.10.71

## Projektbeschreibung

**PiDrive** ist ein Raspberry Pi 3B-basiertes Car-Infotainment-System für BMW 118d 2017 (NBT EVO).
Emuliert einen iPod gegenüber dem BMW iDrive via AVRCP. WebUI auf Port 8080 + `pidrivectl` CLI.

**GitHub:** https://github.com/MPunktBPunkt/pidrive
**Install/Update:** `curl -sL https://raw.githubusercontent.com/MPunktBPunkt/pidrive/main/install.sh | sudo bash`

---

## Hardware

| Komponente | Details |
|---|---|
| Raspberry Pi | Pi 3 Model B Rev 1.2 |
| Display | Joy-IT RB-TFT3.5, 480×320, SPI, fb1 |
| RTL-SDR | RTL2838 DVB-T (ID 0bda:2838, Rafael Micro R820T) |
| Bluetooth | Cambridge Silicon Radio Dongle |
| Audio | 3.5mm Klinke (hw:1,0) → BMW AUX-IN |
| BMW | BMW 118d 2017, NBT EVO |

---

## Aktueller Stand (v0.10.71)

### Services

| Service | Beschreibung | Status |
|---|---|---|
| `pidrive_core` | Hauptprozess | ✓ aktiv |
| `pidrive_web` | Flask WebUI Port 8080 | ✓ aktiv |
| `pidrive_avrcp` | BMW iDrive AVRCP | ✓ aktiv |
| `pidrive_display` | TFT-Display | ⚠ optional |

**WebUI:** http://192.168.178.93:8080

### Quellen

| Quelle | Status |
|---|---|
| DAB+ | ✓ (instabiler Innenraum-Empfang, im Auto OK) |
| FM | ✓ |
| Webradio | ✓ |
| Bluetooth A2DP | ✓ (Pairing nötig) |
| Spotify Connect | ✓ Raspotify installiert, OAuth-Setup nötig |

---

## Verzeichnisstruktur (v0.10.71)

```
pidrive/
├── main_core.py / main_display.py          ← systemd-Einstiegspunkte (Blocker für core/ Move)
├── ipc.py / status.py / settings.py
├── log.py / diagnose.py
├── avrcp_trigger.py / mpris2.py / mpv_meta.py
├── trigger_dispatcher.py / td_*.py         ← Root-Shims → trigger/
├── menu_model.py / menu_state.py / ...     ← Root-Shims → menu/
│
├── cli/                    ← UMGEBAUT ✓ (pidrivectl)
├── web/                    ← UMGEBAUT ✓ (Flask WebUI)
│   ├── app.py / shared/ / api/ / templates/ / static/
├── modules/
│   ├── bluetooth/          ← UMGEBAUT ✓
│   ├── radio/              ← UMGEBAUT ✓
│   └── bt_*.py / dab_*.py  ← DEPRECATED SHIM
├── menu/                   ← UMGEBAUT ✓ (Phase 3a)
│   ├── menu_model.py / menu_state.py / menu_builder.py / station_store.py
├── trigger/                ← UMGEBAUT ✓ (Phase 3b)
│   ├── trigger_dispatcher.py / td_nav.py / td_hardware.py
│   ├── td_radio.py / td_scanner.py / td_system.py
│
├── config/
│   ├── settings.json / dab_stations.json / fm_stations.json
│   ├── stations.json / favorites.json
│
├── tools/                  ← NEU (Feldtest-Hilfsmittel)
│   ├── inject_trigger.sh   ← Trigger direkt senden
│   └── watch_avrcp.sh      ← AVRCP Live-Monitor
│
└── VERSION
```

### Shim-Status (23+ Shims → Abbau in v0.11)
- Root-Shims für menu/ und trigger/ vorhanden
- `webui.py`, `cli.py`, `modules/bt_*.py` etc. → DEPRECATED
- Abbau erst wenn systemd-Services umgestellt

---

## pidrivectl Kommandoreferenz (v0.10.71)

```bash
# Basis
pidrivectl status              # Systemstatus inkl. Volume + Spotify
pidrivectl now                 # Was läuft gerade? (Titel + DLS)
pidrivectl quick               # Schnellübersicht
pidrivectl version             # Installierte Version

# Wiedergabe
pidrivectl play dab "ROCK FM"  # DAB+ (Name oder Nummer)
pidrivectl play dab 27         # DAB+ per Listennummer
pidrivectl play web "Bayern 1" # Webradio
pidrivectl play spotify        # Spotify Connect
pidrivectl stop                # Stoppen

# Sender
pidrivectl station list dab|fm|web
pidrivectl favorites list      # Merged: favorites.json + ★
pidrivectl favorites add       # Aktuellen Sender hinzufügen

# Bluetooth
pidrivectl bt scan             # Live-Scan (22s, Fortschrittsbalken)
pidrivectl bt pair <mac>       # Pairen (Gerät in Pairing-Modus!)
pidrivectl bt connect <mac>    # Verbinden (Live-Feedback)
pidrivectl bt known            # Bekannte Geräte (paired/BLE-gefiltert)
pidrivectl bt status           # Verbindungsstatus

# Audio + Volume
pidrivectl volume up           # Lauter (zeigt neue %)
pidrivectl volume 70           # Direkt setzen
pidrivectl audio route klinke  # Audio-Ausgang
pidrivectl audio status

# DAB+
pidrivectl dab status          # Lock/PCM/Sync/Fehler
pidrivectl dab scan            # Sendersuchlauf

# PPM-Kalibrierung
pidrivectl ppm                 # Aktuellen Wert zeigen
pidrivectl ppm set 49          # RTL-SDR PPM setzen

# System
pidrivectl system              # Info + Spotify-Status
pidrivectl system resources    # RAM, Disk, Uptime
pidrivectl log [core|display|avrcp]

# Debug (Feldtest)
pidrivectl debug avrcp         # Letzte AVRCP-Events (Ringbuffer)
pidrivectl debug inject down   # Trigger direkt injizieren
```

---

## BMW iDrive / AVRCP Steuerarchitektur

```
BMW iDrive Drehen/Drücken/Zurück
        ↓ Bluetooth AVRCP
avrcp_trigger.py (Adapter)
  - empfängt AVRCP Events
  - mappt auf PiDrive-Trigger
  - schreibt in /tmp/pidrive_cmd
  - Ringbuffer: /tmp/pidrive_avrcp_events.json
        ↓
main_core.py (Polling alle 100ms)
        ↓
trigger_dispatcher.py
        ↓
td_nav.py / td_radio.py / td_hardware.py etc.
        ↓
Menü-Navigation / Sender-Start / Audio
```

### AVRCP Button-Mapping (context-basiert)

| BMW-Taste | Kontext: Menü | Kontext: Radio DAB | Kontext: Scanner |
|---|---|---|---|
| Drehen rechts (Next) | nav_down | dab_next | scan_up |
| Drehen links (Prev) | nav_up | dab_prev | scan_down |
| Drücken (Play) | enter | radio_stop | scan_next |
| Zurück (Stop) | back | back | back |
| VolumeUp/Down | vol_up / vol_down | vol_up / vol_down | vol_up / vol_down |

### Offline-Test Tools

```bash
# AVRCP-Event simulieren:
python3 pidrive/avrcp_trigger.py --simulate next
python3 pidrive/avrcp_trigger.py --simulate play_pause

# Trigger direkt injizieren:
./tools/inject_trigger.sh nav_down
./tools/inject_trigger.sh enter

# Live-Monitor im Auto:
./tools/watch_avrcp.sh
```

---

## v0.11 Readiness (Review-Ergebnis)

### Bewertung nach Review

| Bereich | Reifegrad | Bereit für Move? |
|---|---|---|
| `menu/` | hoch | ✓ bereit |
| `trigger/` | mittel-hoch | fast bereit (Imports modernisieren) |
| `integration/` (avrcp, mpris2) | mittel | mit Vorlauf bereit |
| `core/` (main_core.py etc.) | mittel-niedrig | noch zu fragil |

### Größte Blocker für v0.11

1. **systemd startet Root-Dateien direkt** — `main_core.py`, `webui.py`, `avrcp_trigger.py`
2. **sys.path-basierte Root-Annahmen** — in main_core, trigger/, integration/
3. **Installer + Diagnose** erwarten Root-Pfade in Smoke-Tests
4. **main_core.py als Zentralknoten** — importiert alles, schwer isoliert verschiebbar

### Empfohlene Migrationsreihenfolge (v0.11)

```
Phase 3a: menu/     ← bereits physisch done, Imports modernisieren
Phase 3b: trigger/  ← physisch done, interne Imports bereinigen
Phase 3c: integration/ (avrcp_trigger, mpris2, mpv_meta)
Phase 3d: core/ Hilfsdateien (ipc, settings, log, status, diagnose)
Phase 3e: main_core.py / main_display.py (systemd erst dann umstellen)
```

---

## Offene Punkte

| Thema | Status |
|---|---|
| Display-Treiber | ⚠ TFT-Treiber fehlt (LCD-show) |
| Raspotify OAuth | ⚠ Einmalige Browser-Anmeldung nötig |
| BT Pairing BMW | ⚠ Erster Cartest ausstehend |
| Webradio Antenne Bayern URL | ⚠ mpv-Fehler |
| v0.11 Phase 3c-e | ⏳ Geplant |

---

## Erwartete Warnungen (kein Fehler)

| Meldung | Bedeutung |
|---|---|
| `fbcon not available` | TFT nicht angesteckt |
| `DAB: partial_sync` | Innenraum-Empfang, im Auto besser |
| `bt_state=failed` | Kein BT-Gerät in Reichweite |
| `throttled=0x20002` | 5V/3A Netzteil empfohlen |
| `Raspotify: nicht aktiv` | OAuth-Setup nötig |
| `usb_claim_interface error -6` | RTL-SDR bereits belegt |
