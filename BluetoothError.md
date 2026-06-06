# PiDrive — Bluetooth A2DP Fehleranalyse

**Zeitraum:** ca. 2026-05-31 – 2026-06-05  
**Versionen:** v0.11.71 → v0.11.91  
**Plattform:** Raspberry Pi 4, Raspberry Pi OS (Debian Trixie), Kernel 6.18.33+rpt-rpi-v8  
**Betroffene Hardware:** Cambridge Silicon Radio Bluetooth-Dongle, Sennheiser HD 4.40BT (00:16:94:2E:85:DB)

---

## Kurzfassung

Bluetooth A2DP-Verbindungen schlugen mit `br-connection-profile-unavailable` fehl.  
Die eigentliche Ursache lag **nicht** in Bluetooth selbst, sondern in einer fehlenden Zeile in einer D-Bus-Konfigurationsdatei, die verhinderte, dass WirePlumber die ALSA-Soundkarte in PipeWire registrieren konnte. Ohne registriertes Audio-Device konnte BlueZ kein A2DP-Profil aufbauen.

---

## Systemarchitektur (Soll-Zustand)

```
BMW iDrive (BT)
      │ A2DP
      ▼
CSR BT-Dongle (hci0)
      │ BlueZ
      ▼
WirePlumber  ←→  D-Bus (system bus)
      │ registriert ALSA + BT als PipeWire-Devices
      ▼
PipeWire (pipewire-0)
      │
      ▼
pipewire-pulse → /var/run/pulse/native (Compat-Socket)
      │
      ▼
PiDrive (mpv --ao=pulse) → Audio
```

Alle drei Dienste (`pipewire`, `pipewire-pulse`, `wireplumber`) laufen als User `pulse` im System-Mode.

---

## Symptome

### Bluetooth
```
bluetoothctl connect 00:16:94:2E:85:DB
→ Failed to connect: org.bluez.Error.Failed br-connection-profile-unavailable

journalctl -u bluetooth:
→ a2dp-sink profile connect failed for 00:16:94:2E:85:DB: Protocol not available
```

### Audio
```
pactl list sinks short
→ 35  auto_null  PipeWire  float32le 2ch 48000Hz  SUSPENDED

pw-cli ls Device
→ (leer)

pw-cli ls Node
→ nur Dummy-Driver, Freewheel-Driver, auto_null
```

Kein echter ALSA-Sink. Kein `bluez_card`. Kein `bluez_sink`. Nur `auto_null`.

---

## Diagnose-Verlauf

### Was zuerst vermutet wurde

1. Bluetooth-Pairing kaputt → `AlreadyExists`, `Device not available` → war normales BlueZ-Verhalten nach falscher Reihenfolge (remove → scan off → pair)
2. Fehlende PipeWire-Pakete → wurden nachinstalliert (`pipewire`, `wireplumber`, `libspa-0.2-bluetooth`, etc.)
3. Fehlender `pulse`-User → wurde angelegt
4. `DBUS_SESSION_BUS_ADDRESS` fehlte in WirePlumber- und PipeWire-Services → wurde ergänzt
5. D-Bus Policy für `org.pulseaudio.Server` fehlte → wurde ergänzt

Keines dieser Fixes löste das Problem vollständig.

### Entscheidende Diagnose

Mit `WIREPLUMBER_DEBUG=5` als `pulse`-User (System-WirePlumber gestoppt):

```
I 09:43:02.791624  s-monitors  alsa.lua:488: Enabling the use of ACP on alsa_card.platform-fe00b840.mailbox
D 09:43:02.792711  m-reserve-device: request ownership of org.freedesktop.ReserveDevice1.Audio0
D 09:43:02.795905  m-reserve-device: org.freedesktop.ReserveDevice1.Audio0 lost
I 09:43:02.797328  m-reserve-device: Audio0: Could not call RequestRelease:
  Cannot invoke method; proxy is for the well-known name
  "org.freedesktop.ReserveDevice1.Audio0" without an owner,
  and proxy was constructed with the G_DBUS_PROXY_FLAGS_DO_NOT_AUTO_START flag
```

WirePlumber findet die ALSA-Karte korrekt (`bcm2835 Headphones`), versucht dann die D-Bus-Gerätereservierung zu übernehmen — und verliert sie sofort.

---

## Root Cause

### Was ist `org.freedesktop.ReserveDevice1`?

Das ist ein D-Bus-Standard-Mechanismus (freedesktop.org), der verhindert, dass mehrere Audio-Server gleichzeitig dieselbe ALSA-Karte exklusiv nutzen. Wenn PipeWire/WirePlumber eine ALSA-Karte öffnen will, reserviert es sie per D-Bus unter dem Namen `org.freedesktop.ReserveDevice1.AudioN`. Andere Audio-Server (z.B. ein Legacy-PulseAudio-Daemon) können dann prüfen, ob die Karte belegt ist, und ggf. nachfragen.

### Was fehlte

Die D-Bus System-Bus-Policy erlaubte dem `pulse`-User nicht, diesen Namen zu **ownen**:

**Fehlende Zeile in `/etc/dbus-1/system.d/pipewire-pidrive.conf`:**
```xml
<allow own="org.freedesktop.ReserveDevice1.*"/>
```

### Warum fehlte sie

Beim Vorbereiten des Pi wurde der Desktop-Audio-Stack (`pulseaudio`, `pipewire` als User-Dienste) entfernt. Dabei gingen auch die zugehörigen D-Bus-Policy-Dateien verloren, die normalerweise von diesen Paketen mitgeliefert werden. Der PiDrive-Installer legte zwar eine eigene Policy-Datei an (`pipewire-pidrive.conf`), hatte aber diese spezifische Berechtigung nicht enthalten.

### Wirkungskette

```
pulse-User fehlt "own org.freedesktop.ReserveDevice1.*" in D-Bus Policy
    │
    ▼
WirePlumber findet bcm2835 ALSA-Karte via udev ✓
WirePlumber versucht D-Bus-Reservation → verliert sie sofort ✗
    │
    ▼
WirePlumber registriert KEIN Device-Objekt in PipeWire
    │
    ▼
pw-cli ls Device → leer
pactl list sinks → nur auto_null
    │
    ▼
BlueZ versucht A2DP-Profil aufzubauen
Kein lokaler Audio-Endpoint vorhanden
    │
    ▼
a2dp-sink profile connect failed: Protocol not available
br-connection-profile-unavailable
```

Das BT-Problem war also ein **Folgefehler** des ALSA-Problems, das wiederum ein **Folgefehler** des D-Bus-Policy-Problems war.

---

## Lösung

### Sofortfix (manuell)
```bash
sudo tee /etc/dbus-1/system.d/pipewire-pidrive.conf > /dev/null << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE busconfig PUBLIC "-//freedesktop//DTD D-Bus Bus Configuration 1.0//EN"
  "http://www.freedesktop.org/standards/dbus/1.0/busconfig.dtd">
<busconfig>
  <policy user="pulse">
    <allow own="org.pulseaudio.Server"/>
    <allow own="org.freedesktop.ReserveDevice1.*"/>
    <allow send_destination="org.bluez"/>
    <allow receive_sender="org.bluez"/>
    <allow send_interface="org.bluez.Profile1"/>
    <allow send_interface="org.bluez.MediaEndpoint1"/>
    <allow send_interface="org.bluez.MediaTransport1"/>
    <allow send_destination="org.freedesktop.DBus"/>
  </policy>
  <policy context="default">
    <allow send_destination="org.pulseaudio.Server"/>
    <allow send_destination="org.freedesktop.ReserveDevice1"/>
  </policy>
</busconfig>
EOF
sudo reboot
```

**Wichtig:** D-Bus-Policy-Änderungen werden erst nach einem vollständigen Reboot wirksam. `systemctl reload dbus` oder `restart dbus` reicht nicht, weil alle laufenden Dienste ihre bestehenden D-Bus-Verbindungen behalten.

### Fix im Installer (ab v0.11.91)

Der Installer schreibt `pipewire-pidrive.conf` jetzt mit der vollständigen Policy inklusive `ReserveDevice1`.

---

## Nebenprobleme behoben

Während der Fehlersuche wurden weitere Probleme entdeckt und behoben:

| Version | Problem | Fix |
|---------|---------|-----|
| v0.11.79 | `pulse`-User fehlte auf Debian Trixie | `useradd --system pulse` im Installer |
| v0.11.81 | `pipewire`, `wireplumber`, `libspa-0.2-bluetooth` nicht installiert | zu apt-Paketen hinzugefügt |
| v0.11.83 | `dbus-monitor` in `avrcp_trigger.py` ohne `start_new_session=True` → Zombie-Prozesse → 49% dbus-CPU | `Popen(..., start_new_session=True)` |
| v0.11.84 | `DBUS_SESSION_BUS_ADDRESS` fehlte in `wireplumber.service` | `Environment=DBUS_SESSION_BUS_ADDRESS=unix:path=/run/dbus/system_bus_socket` |
| v0.11.85 | `DBUS_SESSION_BUS_ADDRESS` fehlte in `pipewire.service` | gleicher Fix |
| v0.11.85 | `pipewire-pulse` bekam `AccessDenied` für `org.pulseaudio.Server` | `<allow own="org.pulseaudio.Server"/>` in Policy |
| v0.11.85 | `diagnose.py` crashte mit `NameError: info is not defined` | `info(...)` → `nfo(...)` |
| v0.11.86 | `_raw_log()` bekam `start_new_session=True` als falsches Argument | Argument entfernt |
| v0.11.88 | `ReserveDevice1`-Wildcard `.*` funktioniert nicht auf Debian Trixie | Policy nach `/usr/share/dbus-1/system.d/` + explizite Namen `Audio0/1/2` |
| v0.11.89 | WirePlumber BT-Monitor deaktiviert sich: `Seat state changed: offline` | `bluez.lua` lokal nach `/etc/wireplumber/scripts/monitors/` kopiert, `config.seat_monitoring = false` |
| v0.11.90 | `support.logind = disabled` → WirePlumber hängt nach `metadata.lua` | Nur `monitor.bluez.seat-monitoring = disabled` im Profil, logind aktiv lassen |
| **v0.11.91** | **`hfp_ag` Rolle → `org.pipewire.Telephony` D-Bus Fehler → BT-Monitor blockiert** | **`hfp_ag` aus Rollen entfernt, nur `a2dp_source`; `org.pipewire.Telephony` in Policy** |

---

## WirePlumber System-Mode: Bekannte Fallstricke

### Fallstrick 1: Seat-Monitoring blockiert BT-Monitor

**Symptom:** `Seat state changed: offline` — BT-Monitor deaktiviert sich sofort.

**Ursache:** `bluez.lua` prüft logind-Seat. Im System-Mode ohne User-Session meldet logind `offline`.

**Fix:** `bluez.lua` lokal überschreiben:
```bash
sudo mkdir -p /etc/wireplumber/scripts/monitors
sudo cp /usr/share/wireplumber/scripts/monitors/bluez.lua \
   /etc/wireplumber/scripts/monitors/bluez.lua
sudo sed -i 's/config\.seat_monitoring = Core\.test_feature.*/config.seat_monitoring = false/' \
   /etc/wireplumber/scripts/monitors/bluez.lua
```
WirePlumber sucht Scripts zuerst in `/etc/wireplumber/scripts/` — diese Datei hat Vorrang.

---

### Fallstrick 2: `support.logind = disabled` → WirePlumber hängt

**Symptom:** WirePlumber stoppt nach `Loading profile 'main'` / `metadata.lua` und hängt 10+ Sekunden.

**Ursache:** Logind ist intern als Abhängigkeit mehrerer Komponenten nötig. Beim Deaktivieren entsteht ein Dependency-Deadlock.

**Fix:** logind NICHT deaktivieren. Stattdessen nur das Seat-Monitoring im BT-Monitor ausschalten (siehe Fallstrick 1).

---

### Fallstrick 3: `hfp_ag` Rolle → Telephony-Fehler

**Symptom:** `spa.bluez5.telephony: D-Bus RequestName() error: org.pipewire.Telephony — not allowed`

**Ursache:** Die Rolle `hfp_ag` (Hands-Free Profile Gateway) zwingt WirePlumber zur Registrierung von `org.pipewire.Telephony` auf dem System-Bus. Das ist im System-Mode ohne spezielle Policy verboten.

**Fix:** `hfp_ag` aus den Rollen entfernen. Für PiDrive (A2DP-Audio) ist nur `a2dp_source` nötig:
```
monitor.bluez.properties = {
    bluez5.roles = [ a2dp_source ]
    ...
}
```

---

### Fallstrick 4: `wireplumber.profiles.main = {}` vs `wireplumber.profiles = { main = {} }`

**Symptom:** Feature-Flags wie `monitor.bluez.seat-monitoring = disabled` greifen nicht.

**Ursache:** In WirePlumber 0.5.x ist die korrekte Profil-Syntax:
```
wireplumber.profiles = {
  main = {
    feature-name = disabled
  }
}
```
Nicht `wireplumber.profiles.main = { ... }` (point-notation).

---

## Diagnose-Hilfsmittel

### ALSA-Device in PipeWire prüfen
```bash
sudo -u pulse env \
  XDG_RUNTIME_DIR=/run/pipewire \
  PIPEWIRE_RUNTIME_DIR=/run/pipewire \
  DBUS_SESSION_BUS_ADDRESS=unix:path=/run/dbus/system_bus_socket \
  pw-cli ls Device
# Soll: ALSA-Device "bcm2835 Headphones" erscheinen
# War: leer
```

### WirePlumber Debug (System-Service stoppen!)
```bash
sudo systemctl stop wireplumber
sudo -u pulse env \
  XDG_RUNTIME_DIR=/run/pipewire \
  PIPEWIRE_RUNTIME_DIR=/run/pipewire \
  DBUS_SESSION_BUS_ADDRESS=unix:path=/run/dbus/system_bus_socket \
  WIREPLUMBER_DEBUG=5 \
  wireplumber > /tmp/wp_debug.log 2>&1 &
sleep 8 && kill %1
sudo systemctl start wireplumber
grep -E "alsa|reserve|error|failed|lost" /tmp/wp_debug.log | grep -v "^T\|^D"
```

### Soll-Zustand nach Fix
```bash
pactl list sinks short
# → alsa_output.platform-fe00b840.mailbox.analog-stereo  (bcm2835)

bluetoothctl connect 00:16:94:2E:85:DB
# → Connection successful

pactl list cards short
# → bluez_card.00_16_94_2E_85_DB

pactl list sinks short
# → bluez_sink.00_16_94_2E_85_DB.a2dp_sink
```

---

## Lerneffekt für zukünftige Installationen

**Kein manuelles Cleanup vor dem PiDrive-Installer.** Der `pidrive_car_only_cleanup.sh` entfernt gezielt Desktop-Ballast, aber ein freihändiges `apt remove` des Audio-Stacks entfernt auch D-Bus-Policy-Dateien, die PipeWire/WirePlumber für den korrekten Betrieb benötigen. Der PiDrive-Installer setzt alles auf, was er braucht — er sollte die einzige Audio-Konfigurationsquelle sein.

---

*Dokumentiert nach Debugging-Session v0.11.71–v0.11.91 · Juni 2026*
