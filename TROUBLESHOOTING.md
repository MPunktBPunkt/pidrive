# PiDrive — Troubleshooting-Runbook

**Stand v0.11.36 · Plattform: Debian 13 (x86) / Raspberry Pi OS**

Dieses Runbook deckt die häufigsten Fehlerbilder im Alltag ab. Jeder Abschnitt folgt dem Muster: Symptom → Ursache → Prüfbefehle → Maßnahmen.

---

## Inhaltsverzeichnis

1. [Core / Dienste](#1-core--dienste)
2. [Audio / PulseAudio](#2-audio--pulseaudio)
3. [Bluetooth](#3-bluetooth)
4. [AVRCP / BMW iDrive](#4-avrcp--bmw-idrive)
5. [DAB / RTL-SDR](#5-dab--rtl-sdr)
6. [FM / Scanner](#6-fm--scanner)
7. [Installer / Deployment](#7-installer--deployment)

---

## 1. Core / Dienste

### `pidrivectl status` → Core offline

**Symptom:** CLI meldet `Core offline`, WebUI nicht erreichbar.

**Ursachen:**
- `pidrive_core.service` ist abgestürzt oder gestartet-/startet noch
- Python-Traceback beim Core-Start (Importfehler, Syntax)
- `/tmp/pidrive_status.json` fehlt oder ist veraltet

**Prüfen:**
```bash
systemctl status pidrive_core
journalctl -u pidrive_core -n 30 --no-pager
pidrivectl log core
ls -la /tmp/pidrive_status.json /tmp/pidrive_source_state.json
```

**Maßnahmen:**
```bash
systemctl restart pidrive_core
sleep 5 && pidrivectl status
# Bei Python-Fehler:
cd /home/pidrive/pidrive/pidrive && python3 -c "import main_core"
```

**Erwartet oder echter Fehler?** Echter Fehler — Core muss stabil laufen. Kurzfristige `offline`-Phasen beim Neustart sind normal (< 10s).

---

### `pidrive_core.service` Restart-Loop

**Symptom:** `systemctl status` zeigt wiederholt `Active: activating → active → failed`.

**Ursachen:**
- Python-Exception im Core-Loop (ImportError, UnboundLocalError, AttributeError)
- Fehlende Abhängigkeit (Modul nicht gefunden)
- Defekte `/tmp/pidrive_status.json` oder Berechtigungsproblem

**Prüfen:**
```bash
journalctl -u pidrive_core -n 50 --no-pager | grep -E "Traceback|Error|Exception"
python3 /home/pidrive/pidrive/pidrive/main_core.py   # direkt testen
```

**Maßnahmen:**
```bash
# Alle IPC-Dateien löschen und neu starten
rm -f /tmp/pidrive_*.json /tmp/pidrive_cmd
systemctl restart pidrive_core
```

---

### `boot_phase=steady` wird nicht erreicht

**Symptom:** `pidrivectl quick` zeigt `boot_phase: starting` dauerhaft.

**Ursachen:**
- BT-Agent startet nicht (fehlendes `hci0`)
- Audio-Initialisierung schlägt fehl
- Resume-Logik blockiert (letzte Quelle nicht spielbar)

**Prüfen:**
```bash
cat /tmp/pidrive_source_state.json | python3 -m json.tool
pidrivectl log core | grep -i "boot\|steady\|agent"
```

**Maßnahmen:**
```bash
# Boot-Phase manuell überschreiben:
pidrivectl stop
# Oder Core neu starten:
systemctl restart pidrive_core
```

---

### `status.json` / `source_state.json` fehlt oder veraltet

**Symptom:** CLI meldet `Fehler: Core offline`, obwohl Core läuft.

**Prüfen:**
```bash
ls -la /tmp/pidrive_*.json
python3 -c "import time,os; print(time.time()-os.path.getmtime('/tmp/pidrive_status.json'))"
```

**Maßnahmen:**
```bash
# tmpfiles.d neu anwenden:
systemd-tmpfiles --create /etc/tmpfiles.d/pidrive.conf
# Rechte prüfen:
ls -la /tmp/pidrive_cmd   # soll 0660 root:pidrive sein
```

---

## 2. Audio / PulseAudio

### `pidrivectl audio test` zeigt keine Sinks

**Symptom:** Testton schlägt fehl, `Keine PA-Sinks vorhanden`.

**Ursachen:**
- PulseAudio im System-Mode nicht gestartet
- Kein Audio-Gerät erkannt (kein ALSA-Gerät)
- `/etc/pulse/system.pa` nicht korrekt konfiguriert

**Prüfen:**
```bash
systemctl status pulseaudio
PULSE_SERVER=unix:/var/run/pulse/native pactl list short sinks
aplay -l
cat /etc/pulse/system.pa | grep load-module
```

**Maßnahmen:**
```bash
systemctl restart pulseaudio
sleep 2 && PULSE_SERVER=unix:/var/run/pulse/native pactl list short sinks
# Falls Klinke fehlt:
sudo sed -i 's/device_id=0/device_id=0\nload-module module-alsa-card device_id=1/' /etc/pulse/system.pa
systemctl restart pulseaudio
```

---

### `[WEB] mpv rc=2` / mpv startet nicht

**Symptom:** Log zeigt `mpv rc=2 nach 5s`, kein Audio.

**Ursachen:**
- Kein PulseAudio-Sink vorhanden (BT nicht verbunden, Klinke nicht erkannt)
- mpv-Audigerät falsch gesetzt
- URL nicht erreichbar (Netz)

**Prüfen:**
```bash
PULSE_SERVER=unix:/var/run/pulse/native pactl list short sinks
pidrivectl bt status
pidrivectl audio status
```

**Maßnahmen:**
```bash
# BT verbinden:
pidrivectl bt connect <MAC>
# Oder Klinke erzwingen:
pidrivectl audio route klinke
pidrivectl play web 1
```

**Erwartet?** `mpv rc=2` ohne verbundenes Gerät ist erwartetes Verhalten — kein Bug.

---

### Audio über BT nicht hörbar

**Symptom:** BT-Gerät verbunden, aber kein Ton.

**Ursachen:**
- PulseAudio hat keinen BT-Sink erkannt
- A2DP nicht ausgehandelt (nur HFP verbunden)
- mpv spielt auf falschem Sink

**Prüfen:**
```bash
PULSE_SERVER=unix:/var/run/pulse/native pactl list short sinks | grep bluez
pidrivectl audio status
journalctl -u bluetooth | grep -i "a2dp\|sink\|failed"
```

**Maßnahmen:**
```bash
# PA-Module neu laden:
PULSE_SERVER=unix:/var/run/pulse/native pactl load-module module-bluetooth-discover
# BT-Verbindung neu aufbauen:
pidrivectl bt connect <MAC>
sleep 3
pidrivectl play web 1
```

---

### Klinke / HDMI / Auto-Routing unklar

**Prüfen:**
```bash
pidrivectl audio status
pidrivectl audio route auto
pidrivectl audio test
```

**Maßnahmen:** `pidrivectl audio route klinke|bt|hdmi` je nach gewünschtem Ausgang.

---

## 3. Bluetooth

### `bt_state=failed`

**Symptom:** Status zeigt `BT: failed`.

**Erwartet?** Ja — wenn kein BT-Gerät in Reichweite ist. Kein Fehler.

**Prüfen:**
```bash
hciconfig hci0
pidrivectl bt status
```

**Maßnahmen:**
```bash
pidrivectl bt scan    # Scan starten
pidrivectl bt connect <MAC>
```

---

### BT-Gerät gepairt, aber nicht verbunden

**Prüfen:**
```bash
bluetoothctl info <MAC>   # paired=yes, connected=no?
pidrivectl bt known
hciconfig hci0
```

**Maßnahmen:**
```bash
# rfkill prüfen:
rfkill list
rfkill unblock bluetooth
# Manuell verbinden:
pidrivectl bt connect <MAC>
```

---

### BT verbunden, aber kein A2DP-Sink

**Symptom:** `bluetoothctl info` zeigt Connected=yes, aber kein Sink in `pactl`.

**Ursachen:**
- PulseAudio-Bluetooth-Module nicht geladen
- A2DP-Codec-Aushandlung fehlgeschlagen

**Prüfen:**
```bash
PULSE_SERVER=unix:/var/run/pulse/native pactl list modules | grep bluetooth
journalctl -u bluetooth -n 20 | grep -i "a2dp\|profile"
```

**Maßnahmen:**
```bash
PULSE_SERVER=unix:/var/run/pulse/native pactl load-module module-bluetooth-discover
pidrivectl bt connect <MAC>
```

---

### Auto-Reconnect funktioniert nicht

**Prüfen:**
```bash
pidrivectl log core | grep -i "reconnect\|watcher\|bt"
systemctl status pidrive_avrcp
```

**Maßnahmen:**
```bash
# Manuell:
pidrivectl bt reconnect
# Neu pairen falls nötig:
bluetoothctl remove <MAC>
pidrivectl bt pair <MAC>
```

---

### `AF_BLUETOOTH: not supported`

**Ursache:** LXC-Container mit eingeschränktem Kernel-Bluetooth.

**Erwartet?** Ja — im Container-Betrieb normal. Auf Pi 4 tritt das nicht auf.

---

## 4. AVRCP / BMW iDrive

### `pidrivectl avrcp monitor` zeigt keine Events

**Symptom:** Monitor läuft, aber keine Ausgabe bei BMW-Tastendruck.

**Ursachen:**
- `pidrive_avrcp.service` läuft nicht
- BMW iDrive nicht per BT verbunden
- dbus-monitor empfängt keine BlueZ-Signale

**Prüfen:**
```bash
systemctl status pidrive_avrcp
pidrivectl log avrcp
dbus-monitor --system "type=signal,interface=org.bluez.MediaPlayer1" &
```

**Maßnahmen:**
```bash
systemctl restart pidrive_avrcp
pidrivectl bt connect <BMW-MAC>
pidrivectl avrcp    # dann BMW-Taste drücken
```

---

### Trigger landen nicht im Core

**Symptom:** AVRCP-Events ankommen (Monitor zeigt sie), aber Core reagiert nicht.

**Prüfen:**
```bash
cat /tmp/pidrive_avrcp_events.json | python3 -m json.tool
ls -la /tmp/pidrive_cmd        # Trigger-Datei vorhanden?
pidrivectl debug inject next   # Direkttest ohne BMW
```

**Maßnahmen:**
```bash
# IPC-Datei manuell testen:
echo "nav_up" >> /tmp/pidrive_cmd
sleep 1 && pidrivectl quick
```

---

## 5. DAB / RTL-SDR

### DAB: `partial_sync` / `no_lock` / `SyncOnPhase failed`

**Erwartet?** Ja, innen ohne Fahrzeugantenne. Das ist ein Signal-Problem, kein Software-Fehler.

**Prüfen:**
```bash
pidrivectl dab status
pidrivectl dab live --changes
```

**Maßnahmen:** DAB erfordert eine DAB-Antenne. Im Fahrzeug mit Antenne am RTL-SDR testen.

---

### `usb_claim_interface error -6` / DVB-Treiber blockiert SDR

**Symptom:** `rtl_fm` oder `welle-cli` startet nicht.

**Ursachen:**
- Kernel DVB-USB-Treiber belegt den RTL-SDR

**Prüfen:**
```bash
lsmod | grep dvb
dmesg | grep rtl
```

**Maßnahmen:**
```bash
modprobe -r dvb_usb_rtl28xxu rtl2832 rtl2830
# Dauerhaft (nach Reboot):
echo "blacklist dvb_usb_rtl28xxu" >> /etc/modprobe.d/rtlsdr.conf
```

---

## 6. FM / Scanner

### FM startet, aber `quick` bleibt `idle`

**Ursache:** FM-Source wird gestartet, aber nicht als `active` committed (kein PA-Sink).

**Prüfen:**
```bash
pidrivectl quick
cat /tmp/pidrive_source_state.json
PULSE_SERVER=unix:/var/run/pulse/native pactl list short sinks
```

**Maßnahmen:** BT-Gerät verbinden oder Klinke aktivieren, dann nochmals `pidrivectl play fm 104.4`.

---

### Scanner liefert kein Audio

**Prüfen:**
```bash
pidrivectl scanner
pidrivectl audio status
pidrivectl scanner squelch 0   # Squelch deaktivieren (Test)
```

**Maßnahmen:**
```bash
pidrivectl scanner ppm 49      # PPM-Wert setzen
pidrivectl scanner pmr446 freq 446.09375  # Direkt auf Kanal 1
```

---

## 7. Installer / Deployment

### Installer läuft durch, aber Core startet nicht

**Prüfen:**
```bash
journalctl -u pidrive_core -n 30
python3 /home/pidrive/pidrive/pidrive/main_core.py
```

**Maßnahmen:**
```bash
# Syntax- und Import-Check manuell:
cd /home/pidrive/pidrive/pidrive
python3 -c "
import sys; sys.path.insert(0, '.')
import importlib
for m in ['main_core','trigger.trigger_dispatcher','cli.cli']:
    try: importlib.import_module(m); print('✓', m)
    except Exception as e: print('✗', m, e)
"
```

---

### Altimport-Check schlägt an

**Symptom:** Installer meldet `✗ Veraltete Imports gefunden`.

**Prüfen:**
```bash
grep -rn "import td_nav\|import td_radio\|import td_hardware\|import td_scanner\|import td_system" \
  /home/pidrive/pidrive/pidrive --include="*.py"
```

**Maßnahmen:** Betroffene Datei auf `from trigger import td_nav` umstellen. Installer erneut ausführen.

---

### Runtime-Smoke-Test schlägt an

**Symptom:** Installer bricht mit `KRITISCH: Restart-Loop erkannt` oder `Traceback im Log` ab.

**Prüfen:**
```bash
journalctl -u pidrive_core --since "2 minutes ago" --no-pager
```

Der Runtime-Smoke-Test ist kein Fehler im Installer, sondern ein korrekter Gate: der Core ist instabil.

---

### Rechte / Gruppen / `pidrive_cmd` Probleme

**Prüfen:**
```bash
ls -la /tmp/pidrive_cmd   # soll 0660 root:pidrive
id pidrive                # Gruppen: video, audio, input, render, tty
PULSE_SERVER=unix:/var/run/pulse/native pactl info   # als pidrive-User
```

**Maßnahmen:**
```bash
# Rechte reparieren:
chmod 660 /tmp/pidrive_cmd
chown root:pidrive /tmp/pidrive_cmd
# User zu Gruppe hinzufügen (dann logout/login):
usermod -aG audio,pulse-access,render pidrive
```

---

## Wichtige Log-Pfade

| Quelle | Befehl |
|---|---|
| Core-Log (INFO) | `tail -40 /var/log/pidrive/pidrive.log` |
| systemd Core | `journalctl -u pidrive_core -f` |
| systemd AVRCP | `journalctl -u pidrive_avrcp -f` |
| systemd Web | `journalctl -u pidrive_web -f` |
| AVRCP Raw | `tail -f /var/log/pidrive/avrcp_raw.log` |
| IPC-Status | `cat /tmp/pidrive_status.json` |
| Source-State | `cat /tmp/pidrive_source_state.json` |

> INFO-Level-Logs gehen nur in `/var/log/pidrive/pidrive.log`, **nicht** nach journalctl (nur WARNING und höher).

---

*Weiterführend: `ARCHITECTURE.md` (Systemaufbau), `DEVELOPER_GUIDE.md` (Codestruktur)*
