# PiDrive — Kontext & Projektdokumentation v0.11.66

## Projektbeschreibung

**PiDrive** ist ein Raspberry Pi / Debian-basiertes Car-Infotainment-System für BMW iDrive (NBT EVO).  
Steuerung über BMW iDrive AVRCP, WebUI (Port 8080) und `pidrivectl` CLI.  
Kein TFT-Display — GUI-los, vollständig über SSH / WebUI bedienbar.

**GitHub:** https://github.com/MPunktBPunkt/pidrive  
**Install:** `curl -sL https://raw.githubusercontent.com/MPunktBPunkt/pidrive/main/install.sh | bash`

---

## Hardware-Stack

| Komponente | Details |
|---|---|
| Primär (Entwicklung) | Fujitsu Futro S920 · Debian 13 · IP 192.168.178.100 · User `pidrive` |
| Ziel (Fahrzeug) | Raspberry Pi 4 · Raspberry Pi OS · Kühlkörper auf CPU/RAM/USB |
| RTL-SDR | RTL2838 DVB-T (ID 0bda:2838, Rafael Micro R820T) |
| Bluetooth | Cambridge Silicon Radio Dongle |
| BMW | 118d 2017, NBT EVO, AVRCP 1.4–1.5 |
| Display | — (TFT dauerhaft entfernt v0.10.83) |
| GPIO | — (dauerhaft entfernt v0.10.83) |

---

## Funktionsstatus v0.11.66

| Feature | Status |
|---|---|
| Webradio (13 Sender inkl. Rock) | ✅ stabil, Metadaten, Playlist |
| FM Radio (rtl_fm \| mpv, BT) | ✅ stabil |
| FM Scanner (wbfm, Squelch, PPM) | ✅ stabil |
| DAB+ | ✅ kein Lock innen = Signal-Problem, nicht SW |
| BT A2DP Auto-Reconnect | ✅ stabil |
| Metadata (now/playlist) | ✅ via mpv IPC Socket |
| Scanner CLI (pmr446/vhf/uhf/cb/fm) | ✅ stabil |
| AVRCP Phase 1 (Kontextmapping) | ✅ v0.8.6 |
| AVRCP Phase 2 (State Machine) | 🟡 nach Feldtest |
| MPRIS2 (BMW-Metadaten + Watchdog) | ✅ v0.11.66 — noch nicht im Auto validiert |
| Spotify Connect (librespot/raspotify) | ✅ OAuth vorhanden |
| USB-Musik + lokale Wiedergabe | ✅ v0.11.38 |
| **Audio-Stack: PipeWire System-Mode** | ✅ v0.11.66 — ersetzt System-PulseAudio |
| **BT-Pairing Auto-Confirm** | ✅ v0.11.66 — DisplayYesNo + yes-Handler |
| **AVRCP MPRIS2 D-Bus Stabilität** | 🟡 Watchdog läuft, Feldtest ausstehend |
| **Pi 4 BMW Feldtest** | 🟡 BT gepairt, Audio bestätigt, AVRCP ausstehend |
| Boot-Restore | ✅ teilweise |
| pidrivectl test all | ✅ v0.11.66 — Komplett-Systemtest |

---

## Audio-Stack: PipeWire System-Mode (ab v0.11.66)

**Architektur:**
```
pipewire.service       (User=pulse, System-Service)
pipewire-pulse.service (User=pulse, Socket: /var/run/pulse/native)
wireplumber.service    (User=pulse, verwaltet BT A2DP automatisch)
```

**Socket:** `/var/run/pulse/native` — identisch zum alten PulseAudio-System-Mode.  
Kein einziger Code musste geändert werden — `pactl`, `--ao=pulse`, `PULSE_SERVER` funktionieren unverändert.

**WirePlumber ersetzt:**
- `module-bluetooth-discover` → automatisch
- `module-bluetooth-policy` → automatisch
- `pactl set-card-profile` → automatisch bei BT-Connect

**CPU-Last:** PipeWire ~3–5% statt System-PA ~15%.

**Kein Cleanup-Script mehr nötig** — PipeWire User-Units sind systemweit maskiert.

---

## CAPS-System (`modules/platform.py`)

```python
from modules.platform import CAPS

CAPS["is_pi"]            # True auf Raspberry Pi
CAPS["is_container"]     # True in LXC/Docker
CAPS["is_arm"]           # True auf ARM
CAPS["rtlsdr"]           # rtl_fm oder rtl_sdr vorhanden
CAPS["rtl_fm"]           # rtl_fm vorhanden
CAPS["dab"]              # welle-cli vorhanden
CAPS["bluetooth"]        # hci-Adapter vorhanden + Socket-Zugriff
CAPS["bt_lxc_restricted"] # hci sichtbar aber AF_BLUETOOTH gesperrt (LXC)
CAPS["bluetoothctl"]     # bluetoothctl binary vorhanden
CAPS["alsa_card"]        # int (Kartenindex) oder None
CAPS["alsa_device"]      # "hw:1,0" oder None
CAPS["pulseaudio"]       # PA-Socket /var/run/pulse/native (gilt auch für PipeWire)
CAPS["pipewire"]         # pipewire Binary vorhanden
CAPS["spotify"]          # librespot oder raspotify
CAPS["mpv"]              # mpv vorhanden
CAPS["display"]          # immer False (TFT entfernt)
CAPS["gpio"]             # immer False (GPIO entfernt)
```

---

## BMW iDrive — AVRCP + MPRIS2 Architektur

```
BMW iDrive → Bluetooth AVRCP → integration/avrcp_trigger.py
  Ringbuffer:  /tmp/pidrive_avrcp_events.json  (30 Events)
  Status:      /tmp/pidrive_avrcp_status.json
  Simulate:    pidrivectl avrcp inject next
         ↓ /tmp/pidrive_cmd
main_core.py → trigger/ → td_nav / td_radio / td_hardware / td_scanner / td_system

mpris2.py → org.mpris.MediaPlayer2.pidrive (System-D-Bus)
  → BlueZ liest MPRIS2-Properties
  → BMW zeigt Titel/Artist/Album im iDrive-Display
  → Watchdog (alle 30s): prüft ob Service auf D-Bus registriert ist
```

**AVRCP Kontexte (map_event):**
- `menu` — Navigation im Menü (up/down/enter/back)
- `radio` — FM / DAB / Webradio läuft (next/prev = Sender wechseln)
- `scanner` — Funk-Scanner aktiv (next/prev = Kanal/Frequenz)
- `list_overlay` — Listenauswahl überlagert

**MPRIS2 Metadaten je Quelle:**
| Feld | FM | DAB | Webradio | Scanner | Spotify |
|---|---|---|---|---|---|
| title | Sendername | Sendername | Icy-Titel | Kanal/Freq | Track |
| artist | Freq/Station | DAB+ | Interpret | Frequenz | Artist |
| album | "UKW / FM" | "DAB+" | Sendername | Band | Album |

**BMW-Display Diagnose:** `pidrivectl debug mpris status`  
**Test-Push:** `pidrivectl debug mpris push --title "Test" --artist "PiDrive"`

---

## Audio-Routing

```
PipeWire (System-Mode) / Socket: /var/run/pulse/native
  ├── Bluetooth A2DP: bluez_sink.<MAC>.a2dp_sink  (WirePlumber automatisch)
  ├── Klinke:         alsa_output.X.stereo-fallback
  ├── HDMI:           alsa_output.0.stereo-fallback
  └── Fallback:       pidrive_null  (Null-Sink, zeigt "virtuell")
```

**mpv:** `--ao=pulse --audio-device=pulse/<sink>` explizit nötig.  
**welle-cli:** ALSA via PipeWire-ALSA-Plugin (PULSE_SERVER wird gesetzt).  
**librespot:** `--device pulse` → PipeWire-Pulse-Compat-Layer.

---

## Audio-Pfade der Player

| Quelle | Prozess | Besonderheit |
|---|---|---|
| Webradio | `mpv` mit `Popen(list, env=dict)` | IPC-Socket für Metadaten |
| FM Radio | `rtl_fm \| mpv` via `shell=True` | `--demuxer=rawaudio --rate=32000` |
| FM Scanner | `rtl_fm \| mpv` via `shell=True` | `-M wbfm` Broadcast, `-M fm` Schmalband |
| DAB+ | `welle-cli` mit PULSE_SERVER | ALSA → PipeWire-Plugin → BT/Klinke |
| Scanner (PMR/VHF) | `rtl_fm \| mpv` | `-M fm`, Output-Rate 32000 |
| Spotify | `librespot`/`raspotify` | `--device pulse` → PipeWire |
| Lokal | `mpv` mit `Popen(list)` | `--audio-device=pulse/<sink>` |

---

## IPC-Dateien (`/tmp/`)

| Datei | Rechte | Inhalt |
|---|---|---|
| `pidrive_cmd` | 0660 root:pidrive | Trigger-Queue (append-only) |
| `pidrive_status.json` | 0664 | Wiedergabe, BT, WiFi |
| `pidrive_source_state.json` | 0664 | Aktive Quelle, boot_phase |
| `pidrive_avrcp_events.json` | — | Ringbuffer 30 Events |
| `pidrive_avrcp_status.json` | — | Letztes AVRCP-Event |
| `pidrive_dab_scan_debug.json` | — | DAB-Scan-Fortschritt |
| `pidrive_progress.json` | — | Task-Fortschritt |
| `pidrive_dab_welle.err` | — | welle-cli Fehlerlog (rotierend, wird überschrieben) |
| `pidrive_mpv.sock` | — | mpv IPC-Socket |
| `pidrive_test_results.json` | — | Ergebnis pidrivectl test all |

---

## Installer-Plattform-Logik

| Feature | Bedingung |
|---|---|
| RPi.GPIO | IS_ARM |
| fbcon=nodeconfig | IS_PI + fb1 vorhanden |
| fake-hwclock | IS_PI && !IS_CONTAINER |
| dhcpcd5 | IS_PI |
| Raspotify | IS_ARM; sonst librespot Binary von GitHub oder Cargo |
| PipeWire | immer (ersetzt PulseAudio ab v0.11.66) |
| amixer | !IS_CONTAINER && amixer vorhanden |
| REAL_USER Erkennung | SUDO_USER → pidrive → pi → UID≥1000 → root |
| INSTALL_DIR | /home/\<user>/pidrive (User) oder /opt/pidrive (root) |

---

## Bluetooth: Geräte-Erkennung

```python
from modules.bluetooth.bt_helpers import _device_type, _is_avrcp_controller

_device_type(info_out)  # → 'avrcp_controller' | 'headphones' | 'speaker' | 'audio' | 'unknown'
```

| UUID | Bedeutung | Gerät |
|---|---|---|
| 0x110b | Audio Sink | Kopfhörer, Lautsprecher |
| 0x110c | A/V Remote Control Target | BMW iDrive (AVRCP-Controller) |
| 0x110d | Advanced Audio Distribution | BMW iDrive |
| 0x110e | A/V Remote Control | Kopfhörer + BMW |

**Pairing:** Agent läuft mit `DisplayYesNo` → bestätigt `Request confirmation` automatisch mit `yes`.  
`_ensure_avrcp_player()` wird nur für AVRCP-Controller aufgerufen (nicht für Kopfhörer).

---

## Erwartete Warnungen (kein Fehler)

| Meldung | Bedeutung |
|---|---|
| `DAB: partial_sync / no_lock` | Signal zu schwach — innen ohne Antenne normal |
| `bt_state=failed` | Kein BT-Gerät in Reichweite |
| `PLL not locked` | RTL-SDR ohne DAB-Signal |
| `DVB-Treiber noch geladen` | Reboot nötig (`modprobe -r dvb_usb_rtl28xxu`) |
| `Raspotify: nicht aktiv` | OAuth nötig |
| `[WEB] Kein PA-Sink verfügbar` | BT getrennt → verbinden, dann play |
| `[WEB] mpv rc=2 nach 5s` | Kein PA-Sink → kein Audio-Bug |
| `AF_BLUETOOTH: not supported` | LXC BT-Socket gesperrt |
| `pidrive_display.service: deaktiviert` | TFT entfernt v0.10.83 |
| `Audio: virtual` | Kein BT-Sink (pidrive_null aktiv) |
| `throttled=0xf0008` | Unterspannung seit Boot — Netzteil prüfen |

---

## BT Pairing — Automatisch (v0.11.66)

```python
# bt_agent.py: pair_with_agent() bestätigt automatisch:
# "Request confirmation" → yes
# "Request passkey"      → 000000
# "Authorize service"    → yes
```

Manuell falls nötig:
```bash
bluetoothctl scan on
pidrivectl bt pair D4:36:39:CF:E1:B5
pidrivectl bt connect D4:36:39:CF:E1:B5
```

---

## DAB / RTL-SDR

- **DVB-Treiber:** Nach Erstinstall Reboot oder `modprobe -r dvb_usb_rtl28xxu rtl2832 rtl2830`
- **PPM-Offset Fujitsu:** PPM=49 (via `pidrivectl ppm calibrate`)
- **Kein Lock indoor:** `SyncOnPhase failed` ist Signal-Problem, kein Code-Bug
- **welle-cli Gain:** `-g -1` = Software-AGC (empfohlen), `-g 22` = ~40 dB, `-g 28` = max 49.6 dB
- **DAB-Fehlerlog:** `/tmp/pidrive_dab_welle.err` — wird bei jedem Start überschrieben (kein Akkumulieren)

---

## Scanner-Konfiguration

| Band | Modulation | Kanäle/Bereich | Squelch-Typ |
|---|---|---|---|
| pmr446 | fm (schmal) | 16 Kanäle, 446 MHz | `-l {sq}` |
| freenet | fm (schmal) | 6 Kanäle, 149 MHz | `-l {sq}` |
| lpd433 | fm (schmal) | 69 Kanäle, 433 MHz | `-l {sq}` |
| vhf | fm (schmal) | 144–146 MHz | `-l {sq}` |
| uhf | fm (schmal) | 430–440 MHz | `-l {sq}` |
| cb | fm (schmal) | 40 Kanäle, 26–27 MHz | `-l {sq}` |
| **fm** | **wbfm** | **87.5–108 MHz** | **kein Squelch** |

**Squelch Default:** 25 — `pidrivectl scanner squelch 0` für Test ohne Squelch

---

## pidrivectl — Vollständige Befehlsreferenz

```bash
# Status
pidrivectl status / now / quick / version

# Wiedergabe
pidrivectl play dab "SENDER" | dab 27 | web "Bayern 1" | web 3 | fm 104.4 | spotify
pidrivectl play local /pfad/zur/musik  [--shuffle]
pidrivectl stop

# Senderlisten
pidrivectl station list dab|fm|web|local

# Favoriten
pidrivectl favorites list/add/remove/play

# Bluetooth
pidrivectl bt scan / pair <mac|name> / connect <mac> / known / status / reconnect

# Lautstärke
pidrivectl volume up/down / volume set 70

# Audio
pidrivectl audio route klinke|bt|hdmi|auto / audio status / audio test

# DAB
pidrivectl dab status / dab live [--once|--changes] / dab scan
pidrivectl dab stop

# Scanner
pidrivectl scanner BAND ch N / freq F / scan / next / prev / stop
pidrivectl scanner squelch N / ppm N

# PPM
pidrivectl ppm / ppm set 49 / ppm calibrate

# System
pidrivectl system / system resources / system diagnose
pidrivectl system spotify-oauth

# Logs
pidrivectl log [core|app|display|avrcp]
tail -f /var/log/pidrive/pidrive.log     # INFO-Level

# AVRCP
pidrivectl avrcp / avrcp status / avrcp events / avrcp inject next

# Debug
pidrivectl debug mpris status            # MPRIS2 D-Bus Check
pidrivectl debug mpris push --title "T"  # Test-Metadaten ans BMW senden
pidrivectl debug inject <trigger>        # Beliebigen Trigger auslösen

# System-Test (komplett)
pidrivectl test all                      # Alle Quellen + Audio + BT + AVRCP
pidrivectl test system|audio|bt|mpris|webradio|fm|dab|dabscan|spotify|avrcp|log
```

---

## Bekannte offene Punkte

| Thema | Status |
|---|---|
| **AVRCP Feldtest BMW iDrive** | 🔴 BT verbunden, Audio ok, MPRIS2-Display + Tasten ausstehend |
| **welle-cli + PipeWire ALSA** | 🟡 Feldtest ausstehend (theoretisch kompatibel) |
| **MPRIS2 stabil auf D-Bus** | 🟡 Watchdog implementiert, Feldtest ausstehend |
| DAB mit Fahrzeugantenne | 🟡 RTL-SDR vorhanden, Antenne im Auto testen |
| AVRCP Phase 2 (State Machine) | 🟡 nach Feldtest |
| Webradio Auto-Resume nach BT | 🟡 mpv startet neu wenn BT sich verbindet |
| RTL-SDR DVB-Treiber nach Install | ⚠ Reboot nötig |
| `AVRCP scanner fm` Context | 🟡 fm-Band fehlt in map_event |
| pidrivectl bt remove/trust | ⚠ fehlen noch als Subkommandos |

---

## Schlüssel-Entscheidungen & Lerneffekte

### Patch-Sicherheit
- **`assert old in src`** vor jedem `str.replace()` — silent failures sind der Hauptrisikofaktor
- Bei Einrückungsproblemen: zeilenbasiertes Insert statt str.replace
- `.gitignore` muss `play_history.json` enthalten (Nutzerdaten, nicht versionieren)

### Audio / PipeWire
- **PipeWire System-Mode** ab v0.11.66 — `pulseaudio --system` komplett ersetzt
- **Socket gleich:** `/var/run/pulse/native` — kein Code-Umbau nötig
- **WirePlumber** übernimmt BT A2DP automatisch — kein `module-bluetooth-discover` mehr
- **`_ensure_bt_pa_modules()`** prüft jetzt ob PipeWire läuft (pactl info) und überspringt load-module
- **User-PipeWire maskiert** via `/etc/systemd/user/*.service` → kein SSH-Login-Konflikt mehr

### mpv + Audio
- **`shell=True` für mpv**: verhindert zuverlässige IPC-Socket-Erstellung → `Popen(list, env=dict)`
- **`mpv_meta.start()` darf KEIN `os.unlink()` mehr** — löscht den Socket den mpv gerade erstellt hat
- **`--audio-device=pulse/<sink>` muss explizit übergeben werden**
- **`--demuxer=rawaudio --demuxer-rawaudio-rate=32000`** für rtl_fm-Rohaudio
- **FM-Broadcast braucht `-M wbfm`** — `-M fm` ist Schmalband (PMR)

### MPRIS2 / D-Bus
- **`DBusGMainLoop(set_as_default=True)`** muss beim Modulimport gesetzt werden, nicht in start_mpris2()
- **Watchdog alle 30s:** prüft ob Service auf Bus, startet GLib-Loop neu falls nicht
- **`announce_wifi_ip()`:** zeigt Pi-IP für 8s im BMW-Display nach WiFi-Connect (Hotspot-Debug)
- **`pidrivectl debug mpris push`:** Test-Push ohne laufendes Radio

### Bluetooth
- **Agent `DisplayYesNo`** statt `NoInputNoOutput` — BMW sendet `Request confirmation`, kein `yes` = AuthFailed
- **`_device_type()`:** unterscheidet AVRCP-Controller (BMW) von Kopfhörern via UUID 0x110c
- **`_ensure_avrcp_player()`:** wartet auf /player0 nach BT-Connect, nur für avrcp_controller

### DAB-Fehlerlog
- Session-spezifische Dateien akkumulierten auf 305 MB — `_err_file_for_session()` gibt jetzt immer `ERR_FILE` zurück

### AVRCP CPU-Last
- `bufsize=1` in dbus-monitor + bluetoothctl Popen → 65% CPU — gefixt auf `bufsize=4096`

### Version-Bump
- Nur `VERSION`, `install.sh` (`PIDRIVE_VERSION`), `README.md` Badge
- NIEMALS `re.sub()` auf Changelog-Abschnitte
- `.gitignore` fehlt im Container → direkt open/write

---

## Arbeitsweise mit Claude

1. GitHub-Repo klonen → `/home/claude/pidrive_work/`
2. Relevante Files mit `bash_tool/view` lesen
3. Patches via `str.replace()` + `assert old in src` VOR Ersetzung
4. Zeilenbasiert bei Einrückungsproblemen
5. `py_compile` + `bash -n` nach jeder Änderung
6. Version bump: `VERSION`, `install.sh`, `README.md` Badge — niemals Changelog
7. ZIP → `present_files`
8. **KontextPiDrive.md nach jeder Session aktualisieren**
