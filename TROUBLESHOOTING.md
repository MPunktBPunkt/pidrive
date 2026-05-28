# PiDrive — Troubleshooting-Runbook

**Stand v0.11.58 · Plattform: Debian 13 (x86) / Raspberry Pi OS**

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
python3 /home/pidrive/pidrive/pidrive/main_core.py
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
journalctl -u bluetooth | grep -i "a2dp\|sink"
```

WirePlumber sollte A2DP-Sink automatisch erstellen. Falls nicht:
```bash
systemctl restart wireplumber
sleep 3
pidrivectl bt connect <MAC>
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

Ab v0.11.58 bestätigt der Agent `Request confirmation` automatisch.  
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

WirePlumber sollte automatisch. Falls nicht:
```bash
PULSE_SERVER=unix:/var/run/pulse/native pactl list cards short
# bluez_card.MAC sollte erscheinen
PULSE_SERVER=unix:/var/run/pulse/native \
  pactl set-card-profile bluez_card.D4_36_39_CF_E1_B5 a2dp-sink
```

---

### BMW erscheint als `avrcp_controller` in bt known?

```bash
pidrivectl bt known
# BMW 38304 [AVRCP]    ← korrekt
# HD 4.40BT [Kopfhörer] ← korrekt
```

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

Ab v0.11.58 gefixt (bufsize: 1→4096). Falls noch hoch:
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
In `mpris2.py` ist das ab v0.11.58 korrekt — beim Import, nicht in `start_mpris2()`.

---

## 8. Installer / Deployment

### Installer bricht ab — Core startet nicht

```bash
journalctl -u pidrive_core -n 30
python3 /home/pidrive/pidrive/pidrive/main_core.py
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

*Weiterführend: `DEVELOPER_GUIDE.md`, `KontextPiDrive.md`*
