# PiDrive — Kontext & Projektdokumentation v0.11.3

## Projektbeschreibung

**PiDrive** ist ein Raspberry Pi / Debian-basiertes Car-Infotainment-System für BMW iDrive (NBT EVO).  
Steuerung über BMW iDrive AVRCP, WebUI (Port 8080) und `pidrivectl` CLI.  
Kein TFT-Display mehr — GUI-los, vollständig über SSH / WebUI bedienbar.

**GitHub:** https://github.com/MPunktBPunkt/pidrive  
**Install:** `curl -sL https://raw.githubusercontent.com/MPunktBPunkt/pidrive/main/install.sh | bash`

---

## Hardware-Stack

| Komponente | Details |
|---|---|
| Primär (Entwicklung) | Fujitsu Futro S920 · Debian 13 · IP 192.168.178.100 · User `pidrive` |
| Proxmox LXC (Test) | debian13-lite · IP 192.168.178.96 (temporär) |
| Ziel (Fahrzeug) | Raspberry Pi 4 · Raspberry Pi OS |
| RTL-SDR | RTL2838 DVB-T (ID 0bda:2838, Rafael Micro R820T) |
| Bluetooth | Cambridge Silicon Radio Dongle |
| BMW | 118d 2017, NBT EVO, AVRCP 1.5 |
| Display | — (TFT dauerhaft entfernt v0.10.83) |
| GPIO | — (dauerhaft entfernt v0.10.83) |

---

## CAPS-System (`modules/platform.py`)

Einmalig beim Import ausgewertet. Alle Subsysteme prüfen CAPS statt `/proc/cpuinfo`.

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

**Monitor:** `pidrivectl avrcp` — Live-Anzeige aller BMW iDrive Tasten-Events

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

## Erwartete Warnungen (kein Fehler)

| Meldung | Bedeutung |
|---|---|
| `DAB: partial_sync / no_lock` | Signal zu schwach — innen ohne Antenne normal |
| `bt_state=failed` | Kein BT-Gerät in Reichweite |
| `PLL not locked` | RTL-SDR ohne DAB-Signal |
| `DVB-Treiber noch geladen` | Reboot nötig (`modprobe -r dvb_usb_rtl28xxu`) |
| `Raspotify: nicht aktiv` | OAuth nötig |
| `AF_BLUETOOTH: not supported` | LXC BT-Socket gesperrt |
| `pidrive_display.service: dauerhaft deaktiviert` | TFT entfernt v0.10.83 |
| `system.pa: Container-Modus` | Nur Null-Sink (Development) |
| `no A2DP-Sink` | BT verbunden auf BlueZ-Ebene, aber kein PA-Sink |

---

## BT Pairing — Ablauf (manuell)

Wenn `pidrivectl bt pair` fehlschlägt ("bond: inkonsistent"):

```bash
bluetoothctl remove 00:16:94:2E:85:DB
# Gerät in Pairing-Modus bringen
bluetoothctl scan on
# Warten bis [NEW] Device erscheint
bluetoothctl pair 00:16:94:2E:85:DB
bluetoothctl trust 00:16:94:2E:85:DB
bluetoothctl connect 00:16:94:2E:85:DB
```

`repair_device()` in v0.10.90 macht das automatisch:
1. `remove` → alten Bond löschen
2. `scan on` + 15s warten bis Gerät sichtbar
3. `pair + trust + connect`

---

## DAB / RTL-SDR

- **DVB-Treiber:** Nach Erstinstall muss `dvb_usb_rtl28xxu` entladen werden: `reboot` oder `modprobe -r dvb_usb_rtl28xxu rtl2832 rtl2830`
- **PPM-Offset:** Automatisch kalibrierbar via `pidrivectl ppm calibrate` (Fujitsu: PPM=49)
- **Kein Lock indoor:** `SyncOnPhase failed` ist Signal-Problem, kein Code-Bug. Im Auto mit Antenne behoben.
- **Fatal Errors:** `No valid device found` → sofortiger Abbruch (v0.10.86)

---

## Audio-Routing

```
PulseAudio (System-Mode)
  ├── Klinke:    ALSA hw:X,0  (dynamisch via _get_headphone_card())
  ├── Bluetooth: bluez_sink.<MAC>  (nach BT-Connect + PA-Sink-Erkennung)
  ├── HDMI:      ALSA hw:0,0
  └── Container: pidrive_null  (Null-Sink, zeigt "virtuell")
```

**Test:** `pidrivectl audio test` → 440 Hz Sinuston, 3 Sekunden

---

## pidrivectl — Vollständige Befehlsreferenz

```bash
pidrivectl status / now / quick / version
pidrivectl play dab "SENDER" | dab 27 | web "Bayern 1" | web 3 | fm 104.4 | spotify
pidrivectl stop
pidrivectl station list dab|fm|web
pidrivectl favorites list/add/remove/play
pidrivectl bt scan / pair <mac|name> / connect <mac> / known / status
pidrivectl volume up/down/70 / volume set 70
pidrivectl audio route klinke|bt|hdmi|auto / audio status / audio test
pidrivectl dab status / dab live [--once|--changes] / dab scan (live!)
pidrivectl ppm / ppm set 49 / ppm calibrate
pidrivectl system / system resources / system diagnose
pidrivectl log [core|app|display|avrcp]
pidrivectl avrcp              # Live-Monitor BMW iDrive Tasten
pidrivectl avrcp status       # Letztes AVRCP-Event
pidrivectl avrcp events       # Ringbuffer letzte 20
pidrivectl avrcp inject next  # Trigger simulieren
pidrivectl debug avrcp / debug inject <trigger>
```

---

## Bekannte offene Punkte

| Thema | Status |
|---|---|
| BMW Cartest (AVRCP, BT-Pairing) | ⏳ Pi 4 noch nicht konfiguriert |
| RTL-SDR DVB-Treiber | ⚠ nach Erstinstall Reboot nötig |
| DAB kein Lock indoor | ⚠ Signal-Problem, kein SW-Bug |
| librespot auf x86 | ⚠ nicht in Debian-Repo → `cargo install librespot` |
| Spotify OAuth | ⚠ `librespot --name PiDrive --enable-oauth --system-cache /var/cache/raspotify` |
| `sudo` auf Debian | ℹ nicht installiert — als root direkt ausführen |
| `pidrivectl log` als non-root | ⚠ Re-Login nötig nach `usermod -a -G systemd-journal pidrive` |
| Phase 3c core/ | ⏳ v0.11 |

---

## Schlüssel-Entscheidungen & Lerneffekte

- **TFT/GPIO entfernt (v0.10.83):** kein Mehrwert, ersetzt durch WebUI/CLI/AVRCP
- **Silent patch failures:** `str.replace()` ohne Assertion ist der Hauptrisikofaktor — immer `assert old in src` vor Ersetzung
- **`$@` in Heredoc:** unquoted Delimiter expandiert `$@` → `""` im Wrapper → `\$@` verwenden
- **`git pull` ohne `-C`:** CWD-abhängig → immer `git -C "$INSTALL_DIR"` nutzen
- **BT "not available":** bluetoothctl pair braucht Gerät im Scan-Cache — erst `scan on`, dann `pair`
- **mpv rc=-15:** SIGTERM ≠ URL-Fehler; meist PulseAudio-Sink fehlt
- **CAPS vor Hardware-Starts:** `if CAPS["bluetooth"]:` verhindert 6s-Timeout bei fehlendem Adapter
- **REAL_USER:** Fallback-Reihenfolge: SUDO_USER → pidrive → pi → UID≥1000 → root → /opt/pidrive

---

## Arbeitsweise mit Claude

1. Logs / Reviews → Maßnahmen ableiten
2. Python-Patches via `str.replace()` + `assert old in src`
3. Zeilenbasiert bei Einrückungsproblemen
4. `py_compile` + `bash -n` als Syntaxcheck
5. Version bump → ZIP → GitHub-Upload → `curl | bash` auf Zielmaschine

**Wichtig:** Version bump nur in `VERSION`, `install.sh` (`PIDRIVE_VERSION`), `README.md` Badge — nie in Changelog-Dateien mit `re.sub()`.
