# PiDrive — Troubleshooting-Runbook

**Stand:** v0.11.132 · Plattform: Debian 13 (x86) / Raspberry Pi OS (Pi 4)

> Pfad-Hinweis: Das Installationsverzeichnis (`INSTALL_DIR`) ist
> `/home/<user>/pidrive` (bei Installation als User) oder `/opt/pidrive` (als root).
> Der Core-Entry liegt unter `$INSTALL_DIR/pidrive/main_core.py`. In den Beispielen
> unten ggf. an die eigene Installation anpassen.

---

## 1. Core / Dienste

### `pidrivectl status` → Core offline

```bash
systemctl status pidrive_core
journalctl -u pidrive_core -n 30 --no-pager
pidrivectl log core
ls -la /tmp/pidrive_status.json
```

```bash
systemctl restart pidrive_core
sleep 5 && pidrivectl status
```

---

### `pidrive_core.service` Restart-Loop

```bash
journalctl -u pidrive_core -n 50 --no-pager | grep -E "Traceback|Error|Exception"
python3 "$INSTALL_DIR/pidrive/main_core.py"   # INSTALL_DIR = /home/<user>/pidrive o. /opt/pidrive
rm -f /tmp/pidrive_*.json /tmp/pidrive_cmd
systemctl restart pidrive_core
```

---

## 2. Audio / PipeWire

### Keine PA-Sinks nach Reboot

```bash
systemctl status pipewire pipewire-pulse wireplumber
PULSE_SERVER=unix:/var/run/pulse/native pactl list sinks short
```

```bash
systemctl restart pipewire pipewire-pulse wireplumber
sleep 3
PULSE_SERVER=unix:/var/run/pulse/native pactl list sinks short
```

---

### PipeWire-Konflikt (User-PipeWire läuft parallel)

```bash
ps ax | grep -E 'pipewire|pulseaudio' | grep -v grep
```

Falls User-PipeWire läuft (PID unter pidrive-User):
```bash
# Dauerhaft maskieren:
for unit in pipewire pipewire-pulse wireplumber; do
    mkdir -p /etc/systemd/user/${unit}.service.d
    cat > /etc/systemd/user/${unit}.service.d/disable.conf << 'EOF'
[Unit]
ConditionUser=!pidrive
EOF
done
pkill -u pidrive -x pipewire 2>/dev/null
pkill -u pidrive -x wireplumber 2>/dev/null
systemctl restart pipewire pipewire-pulse wireplumber
```

---

### mpv rc=2 / kein Audio

```bash
PULSE_SERVER=unix:/var/run/pulse/native pactl list sinks short
pidrivectl bt status
pidrivectl audio status
```

Erwartet ohne BT-Verbindung — kein Bug.

---

### Audio über BT nicht hörbar

```bash
PULSE_SERVER=unix:/var/run/pulse/native pactl list sinks short | grep bluez
pidrivectl audio status
journalctl -u wireplumber -u bluetooth | grep -i "a2dp\|sink"
```

> **Sink-Name:** Unter PipeWire/WirePlumber heißt der Sink `bluez_output.<MAC>.<N>`
> (nicht `bluez_sink.<MAC>.a2dp_sink`). PiDrive ermittelt ihn ab v0.11.121 via
> `find_bt_sink_for_mac()`.

WirePlumber sollte den A2DP-Sink automatisch erstellen. Falls nicht:
```bash
systemctl restart wireplumber
sleep 3
pidrivectl bt connect <MAC>
```

> **A2DP-Recovery (ab v0.11.122):** Bei einem bereits verbundenen Gerät startet PiDrive
> den `bluetooth`-Dienst während der Recovery **nicht** neu — ein Neustart hatte zuvor
> die Verbindung abreißen lassen. Hilfsskript: `scripts/fix-bt-a2dp.sh`.

---

### WebUI startet erst nach 1–2 Minuten

**Ursache:** `pidrive_web.service` hing an `network-online.target`. Das wartet oft auf
`systemd-networkd-wait-online` / WLAN (~2 Min.), obwohl die UI nur `0.0.0.0:8080` braucht.

**Fix (ab Repo):** `After=`/`Wants=` → `network.target`. Auf dem Pi anwenden:

```bash
sudo cp ~/pidrive/systemd/pidrive_web.service /etc/systemd/system/pidrive_web.service
# Install-Pfade ggf. anpassen, dann:
sudo systemctl daemon-reload
sudo systemctl restart pidrive_web
```

Oder: `bash ~/apply-web-fast-boot.sh` (legt die Unit und startet neu).

---

### DAB im Fahrzeug stumm, Webradio hörbar

**Kein Bluetooth-Fehler.** DAB (`welle-cli`) schreibt heute **direkt auf ALSA/Klinke** und
umgeht PipeWire — A2DP bleibt unerreichbar. Webradio/FM/Spotify laufen über `mpv` →
PipeWire und sind am Fahrzeug hörbar.

Messung / Umbau: [AUFTRAG-DAB-AUDIOWEG.md](../archiv/auftraege/AUFTRAG-DAB-AUDIOWEG.md)
(DA1–DA5, Ziel: `welle-cli -w` + `mpv`).

Schnellcheck am Pi (Klinke vs. BT):
```bash
pidrivectl play dab "…"     # Ton an der Klinke?
pidrivectl play webradio …  # Ton am Fahrzeug?
```

---

### CPU-Throttling / Überhitzung

```bash
vcgencmd get_throttled     # 0x0 = ok, 0x5xxxx = Unterspannung/Throttling
vcgencmd measure_temp      # >80°C = kritisch
pidrivectl system resources
```

Ursache: Netzteil zu schwach (Pi 4 braucht 5V/3A) oder keine Kühlung.

---

## 3. Bluetooth

### BT-Gerät kann nicht gepairt werden (`AuthenticationFailed`)

Ab v0.11.96 bestätigt der Agent `Request confirmation` automatisch.  
Falls noch ein Problem:
```bash
systemctl status pidrive_core   # Agent läuft als Teil des Core
pidrivectl log core | grep "agent\|pair\|confirm"
```

Manuell:
```bash
bluetoothctl
> scan on
> pair D4:36:39:CF:E1:B5     # [agent] Confirm passkey → yes eingeben
> trust D4:36:39:CF:E1:B5
> connect D4:36:39:CF:E1:B5
```

---

### BT verbunden, kein A2DP-Sink

WirePlumber sollte das A2DP-Profil automatisch aktivieren. Falls nicht:
```bash
PULSE_SERVER=unix:/var/run/pulse/native pactl list cards short
# bluez_card.MAC sollte erscheinen
PULSE_SERVER=unix:/var/run/pulse/native \
  pactl set-card-profile bluez_card.D4_36_39_CF_E1_B5 a2dp-sink
# Sink prüfen (PipeWire-Schema):
PULSE_SERVER=unix:/var/run/pulse/native pactl list sinks short | grep bluez_output
```

> Pairing-/Reconnect-Robustheit wurde in v0.11.111–v0.11.116 deutlich verbessert
> (Auto-Restore bekannter Geräte, Reconnect für Kopfhörer ohne Pairing-Modus,
> Pause des Boot-Reconnects während eines aktiven Pairings). Siehe [`KontextPiDrive.md`](../KontextPiDrive.md).

---

### BMW erscheint als `avrcp_controller` in bt known?

```bash
pidrivectl bt known
# BMW 38304 [AVRCP]    ← korrekt
# HD 4.40BT [Kopfhörer] ← korrekt
```

---

### WirePlumber BT-Monitor startet nicht (System-Mode)

**Symptom:** `br-connection-profile-unavailable` trotz gepairtem Gerät.

**Diagnose:**
```bash
journalctl -u wireplumber -b | grep -iE "seat|bluez|telephony|offline"
```

**Ursache A:** `Seat state changed: offline`
```bash
sudo mkdir -p /etc/wireplumber/scripts/monitors
sudo cp /usr/share/wireplumber/scripts/monitors/bluez.lua \
   /etc/wireplumber/scripts/monitors/bluez.lua
sudo sed -i 's/config.seat_monitoring = Core.test_feature.*/config.seat_monitoring = false/' \
   /etc/wireplumber/scripts/monitors/bluez.lua
sudo systemctl restart wireplumber
```

**Ursache B:** `spa.bluez5.telephony: D-Bus RequestName() error`
In `/etc/wireplumber/wireplumber.conf.d/50-bt-pidrive.conf`:
`bluez5.roles = [ a2dp_source ]` — kein `hfp_ag`

**ACHTUNG:** `support.logind = disabled` NICHT setzen → blockiert WirePlumber.

---

## 4. AVRCP / BMW iDrive

### AVRCP-Monitor zeigt keine Events

```bash
systemctl status pidrive_avrcp
pidrivectl log avrcp
dbus-monitor --system "type=signal,interface=org.bluez.MediaPlayer1" &
```

---

### BMW-Display zeigt keine Metadaten

```bash
# MPRIS2 auf D-Bus?
pidrivectl debug mpris status

# Test-Push:
pidrivectl debug mpris push --title "Test" --artist "PiDrive"
```

Falls MPRIS2 nicht registriert:
```bash
systemctl restart pidrive_core
sleep 5
dbus-send --system --print-reply \
  --dest=org.freedesktop.DBus \
  / org.freedesktop.DBus.ListNames 2>/dev/null | grep mpris
```

---

### AVRCP Service verbraucht viel CPU

Ab v0.11.96 gefixt (bufsize: 1→4096). Falls noch hoch:
```bash
systemctl status pidrive_avrcp | grep CPU
journalctl -u pidrive_avrcp --no-pager | tail -20
systemctl restart pidrive_avrcp
```

---

## 5. DAB / RTL-SDR

### `partial_sync` / `no_lock` / `SyncOnPhase failed`

Erwartet innen ohne Fahrzeugantenne. Signal-Problem, kein Code-Bug.

```bash
pidrivectl dab status
```

---

### `usb_claim_interface error -6` / DVB-Treiber blockiert

```bash
lsmod | grep dvb
modprobe -r dvb_usb_rtl28xxu rtl2832 rtl2830
# Dauerhaft:
echo "blacklist dvb_usb_rtl28xxu" >> /etc/modprobe.d/rtlsdr.conf
```

---

### DAB-Fehlerlog zu groß

Ab v0.11.47 gefixt — `/tmp/pidrive_dab_welle.err` wird bei jedem Start überschrieben.  
Alte Dateien manuell: `rm /tmp/pidrive_dab_*.err`

---

## 6. FM / Scanner

### FM startet, aber kein Audio

```bash
pidrivectl audio status
PULSE_SERVER=unix:/var/run/pulse/native pactl list sinks short
pidrivectl bt connect <MAC>
```

---

### Scanner: RTL-SDR belegt

```bash
pidrivectl stop
sleep 2
pidrivectl scanner pmr446 ch 1
```

### Spektrum-Snapshot zeigt JSON / „RTL-SDR belegt“ trotz Idle

**Stand 2026-09-18:** Snapshot-Pfad gefixt (siehe [`WEBUI-REVIEW-2026-09-18.md`](WEBUI-REVIEW-2026-09-18.md) R1–R3).
Historisches Protokoll: [`../ABNAHMEN.md`](../ABNAHMEN.md) (2026-09-15 Spektrum-Snapshot).

Erwartung nach Fix:
- Button sendet `mode=snapshot&center_mhz=…`
- `rtl_sdr … -` (stdout); Stale-Lock-Cleanup vor Busy-Check
- UI: Summary + einfacher Canvas (kein voller Band-Plot)

Falls weiterhin „belegt“: `pidrivectl stop`, RTL-Prozesse prüfen, Lock `/tmp/pidrive_rtlsdr*`.
---

## 7. MPRIS2 / D-Bus

### `dbus-python` ImportError

```bash
python3 -c "import dbus; import dbus.service; print('OK')"
apt install python3-dbus
```

---

### DBusGMainLoop Fehler

`DBusGMainLoop(set_as_default=True)` muss beim Modulimport gesetzt werden.  
In `mpris2.py` ist das ab v0.11.96 korrekt — beim Import, nicht in `start_mpris2()`.

---

## 8. Installer / Deployment

### OTA-Update (`pidrivectl update`)

```bash
pidrivectl update --check          # Lokal vs. origin/main
pidrivectl update                  # mit Bestätigung
# Nach Update:
pidrivectl version
systemctl is-active pidrive_core pidrive_web
```

Nur bei Commits hinter `origin/main` (`behind > 0`). Braucht Netzwerk + git;
Service-Restart per `sudo -n /bin/systemctl restart …` (NOPASSWD nur `restart`).

`git fetch` fehlgeschlagen → Fehlermeldung; Fallback nur VERSION-Vergleich via raw.githubusercontent.

### Installer bricht ab — Core startet nicht

```bash
journalctl -u pidrive_core -n 30
python3 "$INSTALL_DIR/pidrive/main_core.py"   # INSTALL_DIR = /home/<user>/pidrive o. /opt/pidrive
```

---

### PipeWire startet nicht nach Install

```bash
systemctl status pipewire pipewire-pulse wireplumber
journalctl -u pipewire -u pipewire-pulse -u wireplumber --no-pager | tail -30
# Prüfen ob pulse-User in audio + bluetooth Gruppe:
groups pulse
usermod -aG audio,bluetooth pulse
systemctl restart pipewire pipewire-pulse wireplumber
```

---

## 9. Netzwerk / WLAN

### Handy-Hotspot im Fahrzeug einrichten

Im Fahrzeug ist normalerweise kein WLAN verfügbar. Für Webradio wird bei Bedarf ein
Hotspot am Handy eingeschaltet — damit der Pi sich dann von selbst verbindet, muss das
Netz einmalig als Konfiguration angelegt werden.

**Am Handy** einrichten (Android: *Einstellungen → Hotspot*, iOS: *Persönlicher Hotspot*):

| | |
|---|---|
| SSID / Netzwerkname | `pidrive` |
| Sicherheit | WPA2-PSK |
| Band | 2,4 GHz — der Pi-Funkchip ist dort zuverlässiger, und die Reichweite im Auto genügt |

> **Passwortlänge:** WPA2-PSK verlangt **8 bis 63 Zeichen**. Das ist eine Grenze des
> Standards, keine Einstellung. Kürzere Passwörter — etwa `pidrive` mit sieben Zeichen —
> lehnen sowohl Android/iOS als auch `wpa_passphrase` ab.

**Am Pi** anlegen:

```bash
sudo bash ~/pidrive/scripts/wifi-add-network.sh pidrive
# Passwort wird abgefragt (nicht als Argument übergeben — sonst steht es in der History)
```

Das Skript erkennt den Stack selbst (NetworkManager oder `wpa_supplicant`), ist
wiederholbar ohne Duplikate anzulegen, sichert `wpa_supplicant.conf` vorher, und schreibt
dort nur den Hash statt des Klartextpassworts.

Das Passwort steht **absichtlich nicht im Repository**. Wer es dauerhaft festhalten will,
legt es außerhalb des Repos ab — nicht in `docs/`.

**Priorität:** der Hotspot wird mit `autoconnect-priority -10` niedriger eingestuft als das
Heimnetz (Standard `0`). Damit nimmt der Pi zu Hause das Heim-WLAN, auch wenn das Handy mit
aktivem Hotspot in der Nähe liegt — sonst würde er unbemerkt Mobildaten verbrauchen.

Gegenprobe mit eingeschaltetem Hotspot:

```bash
iwgetid -r                      # muss 'pidrive' zeigen
ip -4 addr show wlan0           # muss eine IPv4 haben
nmcli -t -f NAME,AUTOCONNECT,AUTOCONNECT-PRIORITY connection show | grep pidrive
# bzw. bei wpa_supplicant:
sudo wpa_cli -i wlan0 list_networks
```

### Recovery läuft im Fahrzeug alle 5 Minuten ins Leere

Bekannt und **noch nicht behoben** — siehe Paket W-A in
[../archiv/auftraege/AUFTRAG-SPOTIFY-UND-TESTKETTE.md](../archiv/auftraege/AUFTRAG-SPOTIFY-UND-TESTKETTE.md) §12.1.

`wlan_ok()` in `scripts/wifi-recover.sh` fragt nur, ob eine SSID anliegt. Im Fahrzeug ohne
eingeschalteten Hotspot ist das dauerhaft falsch, und der Timer (`OnUnitActiveSec=5min`)
startet die vollständige Prozedur immer wieder — bis hin zum Neuladen von `brcmfmac`.

Das Anlegen des Hotspot-Netzes allein behebt das **nicht**: solange der Hotspot aus ist,
liegt weiterhin keine SSID an. Erst wenn die Vorbedingung auf *„ist ein konfiguriertes Netz
im Scan sichtbar?"* umgestellt ist (W-A), unterscheidet die Automatik Normalzustand von
Störung.

Zwischenlösung, falls die Leerläufe im Journal stören:

```bash
sudo systemctl stop pidrive-wifi-recover.timer
sudo systemctl disable pidrive-wifi-recover.timer
# Boot-Service bleibt aktiv — der reicht für den Stromausfall-Fall
```

Häufigkeit der Leerläufe nach einer Fahrt zählen (Messung H11):

```bash
journalctl -u pidrive-wifi-recover -b | grep -c 'Recovery starten'
```

### Nach Stromausfall: nur LAN erreichbar, WLAN tot

Bekanntes Muster: `eth0` hat IP (z. B. `.107`), `wlan0` ohne SSID/IPv4. Credentials liegen im OS (`wpa_supplicant` / NetworkManager) — oft hängt nur der Stack.

```bash
# Status
ip -4 addr show wlan0 eth0
iwgetid -r
rfkill list wifi

# Einmalig reparieren
sudo bash ~/pidrive/scripts/wifi-recover.sh
# oder:
sudo systemctl start pidrive-wifi-recover.service
journalctl -u pidrive-wifi-recover -b --no-pager
```

Ab Install: **Boot-Service** (`pidrive-wifi-recover.service`) läuft bei jedem Start (~30 s nach `network-online`); der Timer macht Nachversuche.

```bash
systemctl is-enabled pidrive-wifi-recover.service
systemctl status pidrive-wifi-recover.timer
```

---

## Log-Pfade

| Quelle | Befehl |
|---|---|
| Core-Log (INFO) | `tail -40 /var/log/pidrive/pidrive.log` |
| systemd Core | `journalctl -u pidrive_core -f` |
| systemd AVRCP | `journalctl -u pidrive_avrcp -f` |
| systemd PipeWire | `journalctl -u pipewire -u pipewire-pulse -u wireplumber -f` |
| AVRCP Raw | `tail -f /var/log/pidrive/avrcp_raw.log` |
| IPC-Status | `cat /tmp/pidrive_status.json` |
| Test-Ergebnisse | `cat /tmp/pidrive_test_results.json` |

> INFO-Level-Logs gehen nur in `/var/log/pidrive/pidrive.log`, **nicht** nach journalctl.

---

*Weiterführend: [`DEVELOPER_GUIDE.md`](../architektur/DEVELOPER_GUIDE.md), [`KontextPiDrive.md`](../KontextPiDrive.md)*
