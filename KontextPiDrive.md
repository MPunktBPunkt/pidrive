# PiDrive — Kontext & Projektdokumentation v0.10.76

## Projektbeschreibung

**PiDrive** ist ein Raspberry Pi-basiertes Car-Infotainment-System für BMW 118d 2017 (NBT EVO).
Emuliert einen iPod gegenüber dem BMW iDrive via AVRCP. WebUI auf Port 8080 + `pidrivectl` CLI.

**GitHub:** https://github.com/MPunktBPunkt/pidrive
**Install/Update:** `curl -sL https://raw.githubusercontent.com/MPunktBPunkt/pidrive/main/install.sh | sudo bash`

---

## Hardware

| Komponente | Details |
|---|---|
| Raspberry Pi | **Pi 4** (aktiv) / Pi 3B (Legacy) |
| Display | — (TFT-Display entfernt aus Standardbetrieb) |
| RTL-SDR | RTL2838 DVB-T (ID 0bda:2838, Rafael Micro R820T) |
| Bluetooth | Cambridge Silicon Radio Dongle |
| Audio | 3.5mm Klinke → BMW AUX-IN |
| BMW | BMW 118d 2017, NBT EVO |

**Zielplattformen:**
- **Primär:** Raspberry Pi 4 (arm64, 2–4 GB RAM)
- **Legacy:** Raspberry Pi 3B (armv7l)
- **Geplant:** x86_64 Thin Client (Debian 12 headless)

---

## Aktueller Stand (v0.10.76)

### Services

| Service | Beschreibung | Status |
|---|---|---|
| `pidrive_core` | Hauptprozess | ✓ aktiv |
| `pidrive_web` | Flask WebUI Port 8080 | ✓ aktiv |
| `pidrive_avrcp` | BMW iDrive AVRCP | ✓ aktiv |
| `pidrive_display` | TFT-Display | ✗ deaktiviert (kein TFT mehr) |

**WebUI:** http://192.168.178.93:8080

### Quellen

| Quelle | Status |
|---|---|
| DAB+ | ✓ (instabiler Innenraum-Empfang, im Auto besser) |
| FM | ✓ |
| Webradio | ✓ |
| Bluetooth A2DP | ✓ (Pairing nötig) |
| Spotify Connect | ✓ Raspotify, OAuth-Setup nötig |

---

## Verzeichnisstruktur (v0.10.76)

```
pidrive/
├── main_core.py / main_display.py      ← systemd-Einstieg (Blocker core/ Move)
├── ipc.py / status.py / settings.py / log.py / diagnose.py
├── avrcp_trigger.py / mpris2.py / mpv_meta.py
├── trigger_dispatcher.py / td_*.py     ← Root-Shims → trigger/
├── menu_model.py / menu_state.py / ... ← Root-Shims → menu/
│
├── cli/                ← UMGEBAUT ✓
├── web/                ← UMGEBAUT ✓
├── modules/
│   ├── bluetooth/      ← UMGEBAUT ✓
│   ├── radio/          ← UMGEBAUT ✓
│   └── bt_*.py ...     ← DEPRECATED SHIM (→ v0.11)
├── menu/               ← UMGEBAUT ✓ (Phase 3a)
├── trigger/            ← UMGEBAUT ✓ (Phase 3b)
│
├── config/
│   ├── settings.json / dab_stations.json / fm_stations.json
│   ├── stations.json / favorites.json
│
├── tools/              ← Feldtest-Tools
│   ├── inject_trigger.sh
│   └── watch_avrcp.sh
│
└── VERSION
```

---

## pidrivectl Kommandoreferenz (v0.10.76)

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
pidrivectl stop

# Sender
pidrivectl station list dab|fm|web
pidrivectl favorites list
pidrivectl favorites add       # Aktuellen Sender hinzufügen
pidrivectl favorites remove 1  # Favorit entfernen
pidrivectl favorites play 1    # Favorit abspielen

# Bluetooth
pidrivectl bt scan             # Live-Scan (22s)
pidrivectl bt pair <mac>       # Pairen (Gerät in Pairing-Modus!)
pidrivectl bt connect <mac>    # Verbinden (Live-Feedback)
pidrivectl bt known            # Bekannte Geräte (paired/BLE-gefiltert)
pidrivectl bt status

# Audio + Volume
pidrivectl volume up           # Lauter (zeigt neue %)
pidrivectl volume 70           # Direkt setzen
pidrivectl audio route klinke  # Ausgang setzen
pidrivectl audio status        # requested/effective/reason/sink

# DAB+
pidrivectl dab status          # Snapshot: Lock/PCM/Sync
pidrivectl dab live            # Live-Monitor (Empfang, Lock, PCM, DLS)
pidrivectl dab live --changes  # Nur Zustandsänderungen (ideal im Auto)
pidrivectl dab live --once     # Einzel-Snapshot
pidrivectl dab scan

# PPM-Kalibrierung
pidrivectl ppm                 # Aktuellen Wert zeigen
pidrivectl ppm set 49          # RTL-SDR PPM setzen

# System
pidrivectl system / system resources
pidrivectl log [core|display|avrcp]
pidrivectl debug avrcp         # Letzte AVRCP-Events (Ringbuffer)
pidrivectl debug inject down   # Trigger direkt injizieren
```

---

## BMW iDrive / AVRCP Steuerarchitektur

```
BMW iDrive (Drehen/Drücken/Zurück)
        ↓ Bluetooth AVRCP
avrcp_trigger.py
  - empfängt AVRCP Events
  - mappt auf PiDrive-Trigger
  - Ringbuffer: /tmp/pidrive_avrcp_events.json
  - Simulate: python3 avrcp_trigger.py --simulate next
        ↓ /tmp/pidrive_cmd
main_core.py (Polling 100ms)
        ↓
trigger_dispatcher.py → td_nav / td_radio / td_hardware / td_scanner / td_system
```

### AVRCP Button-Mapping

| BMW-Taste | Menü | Radio DAB | Scanner |
|---|---|---|---|
| Drehen rechts (Next) | nav_down | dab_next | scan_up |
| Drehen links (Prev) | nav_up | dab_prev | scan_down |
| Drücken (Play) | enter | radio_stop | scan_next |
| Zurück (Stop) | back | back | back |
| VolumeUp/Down | vol_up/down | vol_up/down | vol_up/down |

---

## Installer-Plattform-Logik (v0.10.76)

| Feature | Bedingung |
|---|---|
| RPi.GPIO | nur auf ARM (arm*/aarch64) |
| fbcon=nodeconfig | nur wenn `/sys/class/graphics/fb1` vorhanden |
| vtcon1 unbind (rc.local) | nur wenn fb1 vorhanden |
| pidrive_display Service | deaktiviert (kein TFT im Standardbetrieb) |
| pidrivectl Wrapper | dynamisch mit `$REAL_HOME` |
| sudoers | dynamisch mit `$REAL_USER` |

---

## v0.11 Readiness

| Bereich | Reifegrad |
|---|---|
| `menu/` | ✓ bereit |
| `trigger/` | ~ fast bereit (Imports modernisieren) |
| `integration/` | machbar mit Vorlauf |
| `core/` | ✗ noch fragil (systemd, sys.path) |

Empfohlene Reihenfolge: integration/ → trigger/ (Imports) → core/ Hilfsdateien → main_core.py

---

## Offene Punkte

| Thema | Status |
|---|---|
| BT Pairing BMW | ⚠ Erster Cartest ausstehend |
| Raspotify OAuth | ⚠ Einmalige Browser-Anmeldung |
| play fm | ⚠ Fragile Implementierung, zurückgestellt |
| radio next/prev | ⏳ Mittelfristig |
| stop --wait | ⏳ Mittelfristig |
| Pi 4 Cartest | ⏳ Nächster Schritt |
| x86_64 Thin Client | ⏳ Geplant (Debian 12) |

---

## Erwartete Warnungen (kein Fehler)

| Meldung | Bedeutung |
|---|---|
| `fbcon not available` | Kein TFT (erwartet, Display deaktiviert) |
| `DAB: partial_sync` | Innenraum-Empfang, im Auto besser |
| `bt_state=failed` | Kein BT-Gerät in Reichweite |
| `throttled=0x20002` | 5V/3A Netzteil empfohlen |
| `Raspotify: nicht aktiv` | OAuth-Setup nötig |
| `usb_claim_interface error -6` | RTL-SDR bereits belegt |

---

## Arbeitsweise mit Claude

1. Reviews per externem AI → Maßnahmen ableiten
2. Claude auditiert Dateien aus Arbeitsverzeichnis
3. Python-Patches via str.replace mit assert-Prüfung
4. Syntax-Check mit py_compile + bash -n
5. Version bump + ZIP → GitHub-Upload → Pi-Update per SSH
