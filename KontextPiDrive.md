# PiDrive — Kontext & Projektdokumentation v0.11.19

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
| Ziel (Fahrzeug) | Raspberry Pi 4 · Raspberry Pi OS |
| RTL-SDR | RTL2838 DVB-T (ID 0bda:2838, Rafael Micro R820T) |
| Bluetooth | Cambridge Silicon Radio Dongle |
| BMW | 118d 2017, NBT EVO, AVRCP 1.5 |
| Display | — (TFT dauerhaft entfernt v0.10.83) |
| GPIO | — (dauerhaft entfernt v0.10.83) |

---

## Funktionsstatus v0.11.19

| Feature | Status |
|---|---|
| Webradio (13 Sender inkl. Rock) | ✅ stabil, Metadaten, Playlist |
| FM Radio (rtl_fm \| mpv, BT) | ✅ stabil |
| FM Scanner (wbfm, Squelch, PPM) | ✅ v0.11.19 |
| DAB+ Code | ✅ kein Lock innen = Signal-Problem, nicht SW |
| BT A2DP Auto-Reconnect | ✅ stabil |
| Metadata (now/playlist) | ✅ via mpv IPC Socket |
| Scanner CLI (pmr446/vhf/uhf/cb/fm) | ✅ v0.11.5 |
| AVRCP Phase 1 (Kontextmapping) | ✅ v0.8.6 |
| Boot-Restore | ✅ teilweise |
| **Pi 4 Einbau / BMW Feldtest** | ⏳ noch nicht |

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
CAPS["pulseaudio"]       # PA-Socket /var/run/pulse/native
CAPS["spotify"]          # librespot oder raspotify
CAPS["mpv"]              # mpv vorhanden
CAPS["display"]          # immer False (TFT entfernt)
CAPS["gpio"]             # immer False (GPIO entfernt)
```

---

## BMW iDrive — AVRCP Architektur

```
BMW iDrive → Bluetooth AVRCP → avrcp_trigger.py
  Ringbuffer:  /tmp/pidrive_avrcp_events.json  (30 Events)
  Status:      /tmp/pidrive_avrcp_status.json
  Simulate:    pidrivectl avrcp inject next
         ↓ /tmp/pidrive_cmd
main_core.py → trigger/ → td_nav / td_radio / td_hardware / td_scanner / td_system
```

**AVRCP Kontexte (map_event):**
- `menu` — Navigation im Menü (up/down/enter/back)
- `radio` — FM / DAB / Webradio läuft (next/prev = Sender wechseln)
- `scanner` — Funk-Scanner aktiv (next/prev = Kanal/Frequenz)
- `list_overlay` — Listenauswahl überlagert

**Monitor:** `pidrivectl avrcp` — Live-Anzeige aller BMW iDrive Tasten-Events

---

## Audio-Routing

```
PulseAudio (System-Mode)
  ├── Bluetooth: bluez_sink.<MAC>  (nach BT-Connect + PA-Sink-Erkennung)
  ├── Klinke:    ALSA hw:X,0  (dynamisch via _get_headphone_card(), Pi 4)
  ├── HDMI:      ALSA hw:0,0
  └── Container: pidrive_null  (Null-Sink, zeigt "virtuell")
```

**Kritisch:** mpv muss `--audio-device=pulse/<sink>` explizit übergeben bekommen.  
Ohne BT-Sink → `mpv rc=2` — das ist erwartet, kein Code-Bug.

**Test:** `pidrivectl audio test` → 440 Hz Sinuston, 3 Sekunden

---

## Audio-Pfade der Player

| Quelle | Prozess | Besonderheit |
|---|---|---|
| Webradio | `mpv` mit `Popen(list, env=dict)` | IPC-Socket für Metadaten |
| FM Radio | `rtl_fm \| mpv` via `shell=True` | `--demuxer=rawaudio --rate=32000` |
| FM Scanner | `rtl_fm \| mpv` via `shell=True` | `-M wbfm` für Broadcast, `-M fm` für Schmalband |
| DAB+ | `welle-cli \| mpv` | Lock braucht Signal (Fahrzeugantenne) |
| Scanner (PMR/VHF) | `rtl_fm \| mpv` | `-M fm`, Output-Rate 32000 |

**mpv IPC-Socket:** `/tmp/pidrive_mpv.sock`
- Wird von `webradio.py` **vor** mpv-Start mit `os.unlink()` gelöscht
- Wird von mpv beim Start erstellt
- `mpv_meta.start()` darf KEIN `os.unlink()` mehr aufrufen (v0.11.3 Fix)

---

## IPC-Dateien (`/tmp/`)

| Datei | Rechte | Inhalt |
|---|---|---|
| `pidrive_cmd` | 0660 root:pidrive | Trigger-Datei |
| `pidrive_status.json` | 0664 | Wiedergabe, BT, WiFi |
| `pidrive_source_state.json` | 0664 | Aktive Quelle, Transitions |
| `pidrive_avrcp_events.json` | — | Ringbuffer 30 Events |
| `pidrive_avrcp_status.json` | — | Letztes AVRCP-Event |
| `pidrive_dab_scan_debug.json` | — | Scan-Fortschritt |
| `pidrive_progress.json` | — | Task-Fortschritt |

---

## Installer-Plattform-Logik

| Feature | Bedingung |
|---|---|
| RPi.GPIO | IS_ARM |
| fbcon=nodeconfig | IS_PI + fb1 vorhanden |
| fake-hwclock | IS_PI && !IS_CONTAINER |
| dhcpcd5 | IS_PI |
| Raspotify | IS_ARM; sonst `apt install librespot` oder Cargo |
| system.pa | Container → Null-Sink; sonst dynamisch |
| amixer | !IS_CONTAINER && amixer vorhanden |
| REAL_USER Erkennung | SUDO_USER → pidrive → pi → UID≥1000 → root |
| INSTALL_DIR | /home/\<user>/pidrive (User) oder /opt/pidrive (root) |
| git-Befehle | immer `git -C "$INSTALL_DIR"` |

---

## Erwartete Warnungen (kein Fehler)

| Meldung | Bedeutung |
|---|---|
| `DAB: partial_sync / no_lock` | Signal zu schwach — innen ohne Antenne normal |
| `bt_state=failed` | Kein BT-Gerät in Reichweite |
| `PLL not locked` | RTL-SDR ohne DAB-Signal |
| `DVB-Treiber noch geladen` | Reboot nötig (`modprobe -r dvb_usb_rtl28xxu`) |
| `Raspotify: nicht aktiv` | OAuth nötig |
| `[WEB] Kein PA-Sink verfügbar` | BT getrennt → BT verbinden, dann play |
| `[WEB] mpv rc=2 nach 5s` | Kein PA-Sink vorhanden → kein Audio-Bug |
| `AF_BLUETOOTH: not supported` | LXC BT-Socket gesperrt |
| `pidrive_display.service: dauerhaft deaktiviert` | TFT entfernt v0.10.83 |
| `system.pa: Container-Modus` | Nur Null-Sink (Development) |
| `no A2DP-Sink` | BT verbunden auf BlueZ-Ebene, aber kein PA-Sink |

---

## BT Pairing — Ablauf (manuell)

```bash
bluetoothctl remove 00:16:94:2E:85:DB
# Gerät in Pairing-Modus bringen
bluetoothctl scan on
# Warten bis [NEW] Device erscheint
bluetoothctl pair 00:16:94:2E:85:DB
bluetoothctl trust 00:16:94:2E:85:DB
bluetoothctl connect 00:16:94:2E:85:DB
```

---

## DAB / RTL-SDR

- **DVB-Treiber:** Nach Erstinstall Reboot oder `modprobe -r dvb_usb_rtl28xxu rtl2832 rtl2830`
- **PPM-Offset Fujitsu:** PPM=49 (via `pidrivectl ppm calibrate`)
- **Kein Lock indoor:** `SyncOnPhase failed` ist Signal-Problem, kein Code-Bug
- **welle-cli Gain:** `-g -1` = Software-AGC (empfohlen), `-g 22` = ~40 dB, `-g 28` = max 49.6 dB
- **welle-cli FM Band:** `BANDS["fm"]` hat `bw=200000` → `-M wbfm -s 250000 -r 32000`

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
pidrivectl play fm 1          # → Antenne Bayern (aus fm_stations.json)
pidrivectl stop

# Senderlisten
pidrivectl station list dab|fm|web

# Favoriten
pidrivectl favorites list/add/remove/play

# Bluetooth
pidrivectl bt scan / pair <mac|name> / connect <mac> / known / status / reconnect

# Lautstärke
pidrivectl volume up/down / volume set 70

# Audio
pidrivectl audio route klinke|bt|hdmi|auto / audio status / audio test

# DAB
pidrivectl dab status / dab live [--once|--changes] / dab scan (live!)
pidrivectl dab stop

# Scanner
pidrivectl scanner BAND ch N          # direkt auf Kanal N (1-basiert)
pidrivectl scanner BAND freq F        # direkt auf Frequenz F MHz
pidrivectl scanner BAND scan          # Scan starten
pidrivectl scanner BAND next|prev     # Kanal vor/zurück
pidrivectl scanner squelch 0          # Squelch 0=aus, 25=normal, 50=streng
pidrivectl scanner ppm 49             # PPM-Korrektur setzen
pidrivectl scanner stop               # stoppen
pidrivectl scanner                    # Status + alle Bänder

# PPM
pidrivectl ppm / ppm set 49 / ppm calibrate

# System
pidrivectl system / system resources / system diagnose

# Logs
pidrivectl log [core|app|display|avrcp]
tail -f /var/log/pidrive/core.log     # INFO-Level (nicht in journalctl)

# AVRCP
pidrivectl avrcp                      # Live-Monitor BMW iDrive Tasten
pidrivectl avrcp status               # Letztes AVRCP-Event
pidrivectl avrcp events               # Ringbuffer letzte 20
pidrivectl avrcp inject next          # Trigger simulieren
pidrivectl debug avrcp / debug inject <trigger>

# Playlist
pidrivectl playlist today | all | last | 2026-05-17
```

---

## Bekannte offene Punkte

| Thema | Status |
|---|---|
| **Pi 4 Erstinstall** | 🔴 Hauptblocker für Feldtest |
| **BMW BT-Pairing (iDrive)** | 🔴 noch nicht getestet |
| **AVRCP Feldtest BMW iDrive** | 🔴 |
| DAB mit Fahrzeugantenne | 🟡 |
| Webradio Auto-Resume nach BT-Connect | 🟡 mpv startet neu wenn BT sich verbindet |
| AVRCP Phase 2 (State Machine) | 🟡 nach Feldtest |
| Raspotify auf ARM (Pi 4) | 🟢 |
| `AVRCP scanner fm` Context | 🟡 fm-Band fehlt in map_event |
| librespot auf x86 | ⚠ nicht in Debian-Repo → cargo |
| RTL-SDR DVB-Treiber nach Install | ⚠ Reboot nötig |

---

## Schlüssel-Entscheidungen & Lerneffekte

### Patch-Sicherheit
- **`assert old in src`** vor jedem `str.replace()` — silent failures sind der Hauptrisikofaktor
- Bei Einrückungsproblemen: zeilenbasiertes Insert statt str.replace
- `.gitignore` muss `play_history.json` enthalten (Nutzerdaten, nicht versionieren)

### mpv + Audio
- **`shell=True` für mpv**: verhindert zuverlässige IPC-Socket-Erstellung → `Popen(list, env=dict)`
- **`mpv_meta.start()` darf KEIN `os.unlink()` mehr** — löscht den Socket den mpv gerade erstellt hat
- **`--audio-device=pulse/<sink>` muss explizit übergeben werden** — PA-Default-Sink ist oft leer
- **`--demuxer=rawaudio --demuxer-rawaudio-rate=32000`** für rtl_fm-Rohaudio
- **FM-Broadcast braucht `-M wbfm`** — `-M fm` ist Schmalband (PMR), kein Audio für Radiosender

### StationStore Bug
- `StationStore.__init__` setzt `self.fm = []` — ruft nie `_load()` auf → immer leer
- Workaround: `json.load(open(fm_stations_path))` direkt in `trigger/td_radio.py`

### PulseAudio
- **INFO-Level-Logs** gehen nur in `/var/log/pidrive/core.log`, NICHT nach journalctl
- journalctl zeigt nur WARNING und höher
- mpv-Metadaten-Events (Stream-Titel) nur in `core.log` sichtbar

### Version-Bump
- Nur `VERSION`, `install.sh` (`PIDRIVE_VERSION`), `README.md` Badge
- NIEMALS `re.sub()` auf Changelog-Abschnitte — korrumpiert History-Header
- `.gitignore` fehlt in Claude-Container → nicht auf Existenz prüfen, direkt schreiben

### Sonstiges
- **`$@` in Heredoc:** unquoted Delimiter expandiert → `\$@` verwenden
- **BT "not available":** `scan on` vor `pair` — Gerät braucht Cache-Eintrag
- **CAPS vor Hardware-Starts:** verhindert 6s-Timeout bei fehlendem Adapter

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
