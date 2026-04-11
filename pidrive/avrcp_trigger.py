#!/usr/bin/env python3
"""
avrcp_trigger.py - PiDrive AVRCP → File-Trigger Bridge
v0.7.10

Lauscht auf bluetoothctl-Events und übersetzt AVRCP-Befehle
des BMW iDrive in /tmp/pidrive_cmd File-Trigger.

BMW iDrive NBT EVO Mapping:
  Drehsteller rechts (NEXT)       → down
  Drehsteller links  (PREV)       → up
  Drehsteller drücken (PLAY/PAUSE)→ enter
  Zurück-Taste (STOP)             → back
  Lang drücken (~1.5s PLAY/PAUSE) → back   (Fallback)
  Doppelklick PLAY/PAUSE          → cat:0  (direkt "Jetzt läuft")
"""

import subprocess
import sys
import os
import time
import signal
import threading

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

import log

CMD_FILE  = "/tmp/pidrive_cmd"
READY_FILE= "/tmp/pidrive_ready"

# BMW NBT EVO AVRCP → Trigger Mapping
# AVRCP 1.5 (stabiler Volume-Sync, beste Balance Pi 3B + BMW NBT EVO)
# Hinweis: BlueZ Version via /etc/bluetooth/main.conf steuerbar
AVRCP_MAP = {
    "next":           "down",
    "previous":       "up",
    "play":           "enter",
    "pause":          "enter",
    "play_pause":     "enter",
    "stop":           "back",
    "fast_forward":   "down",
    "rewind":         "up",
    # AVRCP 1.4: Lautstärke-Events
    "volumeup":       "vol_up",
    "volumedown":     "vol_down",
    "volume_up":      "vol_up",
    "volume_down":    "vol_down",
}

# Doppelklick-Erkennung: 2x enter in <0.5s → "Jetzt läuft"
_last_enter_time  = 0.0
_press_start_time = 0.0  # für Long-Press-Erkennung

# LONG_PRESS: PLAY/PAUSE > 1.5s gehalten → back
LONG_PRESS_SEC  = 1.5
DOUBLE_TAP_SEC  = 0.5


def write_cmd(cmd: str):
    """Trigger-Datei schreiben."""
    try:
        with open(CMD_FILE, "w") as f:
            f.write(cmd.strip() + "\n")
        log.info(f"AVRCP → {cmd}")
    except Exception as e:
        log.error(f"write_cmd: {e}")


def handle_avrcp(event: str):
    """AVRCP-Event verarbeiten und in Trigger übersetzen."""
    global _last_enter_time, _press_start_time

    event = event.strip().lower()

    # Warte bis Core bereit
    if not os.path.exists(READY_FILE):
        return

    if event in ("play", "pause", "play_pause"):
        now = time.time()
        # Doppelklick → direkt "Jetzt läuft"
        if now - _last_enter_time < DOUBLE_TAP_SEC:
            write_cmd("cat:0")
            _last_enter_time = 0.0
            return
        _last_enter_time = now
        _press_start_time = now
        write_cmd("enter")

    elif event == "stop":
        write_cmd("back")

    elif event in AVRCP_MAP:
        trigger = AVRCP_MAP[event]
        write_cmd(trigger)


def parse_bluetoothctl_line(line: str) -> str | None:
    """bluetoothctl-Ausgabe auf AVRCP-Events parsen."""
    line = line.lower()

    # Format: "[CHG] Player /org/bluez/... Status: playing"
    # oder:   "avrcp-player: Action: Next"
    if "avrcp" in line or "player" in line:
        for keyword in AVRCP_MAP.keys():
            if keyword in line:
                return keyword

    # dbus-monitor Format:
    # string "Next" / string "Previous" / string "PlayPause" etc.
    for keyword in ("next", "previous", "play", "pause", "stop",
                    "fast_forward", "rewind"):
        if f'"{keyword}"' in line or f"'{keyword}'" in line:
            return keyword.lower()

    return None


def monitor_bluetoothctl():
    """bluetoothctl monitor auf AVRCP-Events lauschen."""
    log.info("AVRCP: starte bluetoothctl monitor ...")
    try:
        proc = subprocess.Popen(
            ["bluetoothctl", "monitor"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1
        )
        for line in proc.stdout:
            event = parse_bluetoothctl_line(line)
            if event:
                handle_avrcp(event)
    except Exception as e:
        log.error(f"AVRCP monitor: {e}")


def monitor_dbus():
    """dbus-monitor als Alternative zu bluetoothctl monitor."""
    log.info("AVRCP: starte dbus-monitor (MediaPlayer2)...")
    try:
        proc = subprocess.Popen(
            ["dbus-monitor",
             "interface=org.mpris.MediaPlayer2.Player",
             "type=signal"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1
        )
        for line in proc.stdout:
            # Parsing MPRIS2 D-Bus Signals
            line_s = line.strip()
            # PropertiesChanged mit PlaybackStatus, Rate, Metadata
            event = None
            if '"Next"'      in line_s: event = "next"
            elif '"Previous"' in line_s: event = "previous"
            elif '"PlayPause"'in line_s: event = "play_pause"
            elif '"Play"'     in line_s: event = "play"
            elif '"Pause"'    in line_s: event = "pause"
            elif '"Stop"'     in line_s: event = "stop"
            if event:
                handle_avrcp(event)
    except Exception as e:
        log.error(f"AVRCP dbus: {e}")


def check_avrcp_version():
    """Prüft ob AVRCP 1.4 konfiguriert ist (Empfehlung für BMW NBT EVO)."""
    config = "/etc/bluetooth/main.conf"
    try:
        content = open(config).read()
        if "0x0104" in content or "0x0105" in content:
            log.info("AVRCP: Version 1.4/1.5 konfiguriert ✓")
        else:
            log.warn("AVRCP: Version nicht explizit gesetzt")
            log.warn("  BMW NBT EVO empfiehlt AVRCP 1.4")
            log.warn("  Fix: /etc/bluetooth/main.conf → [AVRCP] Version = 0x0105")
    except Exception:
        pass


def auto_connect_bmw():
    """BMW Bluetooth automatisch verbinden beim Start."""
    # Gespeicherte Geräte prüfen und verbinden
    try:
        r = subprocess.run(
            "bluetoothctl devices Paired 2>/dev/null",
            shell=True, capture_output=True, text=True, timeout=5
        )
        for line in r.stdout.splitlines():
            parts = line.strip().split(" ", 2)
            if len(parts) >= 2:
                mac = parts[1]
                name = parts[2] if len(parts) > 2 else mac
                log.info(f"AVRCP: versuche Verbindung zu {name} ({mac})")
                subprocess.Popen(
                    f"bluetoothctl connect {mac}",
                    shell=True, stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                time.sleep(2)
    except Exception as e:
        log.error(f"auto_connect: {e}")


def main():
    log.setup("core")  # nutzt Core-Log
    log.info("=" * 50)
    log.info("PiDrive AVRCP-Trigger v0.7.10 gestartet")
    log.info("  BMW iDrive NBT EVO → AVRCP → /tmp/pidrive_cmd")
    log.info("=" * 50)

    signal.signal(signal.SIGHUP, signal.SIG_IGN)
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))

    # BMW automatisch verbinden
    auto_connect_bmw()

    # Beide Monitor-Methoden parallel starten (Fallback)
    t1 = threading.Thread(target=monitor_bluetoothctl, daemon=True)
    t2 = threading.Thread(target=monitor_dbus, daemon=True)
    t1.start()
    t2.start()

    log.info("AVRCP: Warte auf BMW iDrive Verbindung ...")
    log.info("  Mapping:")
    log.info("    Drehsteller rechts (NEXT)    → down")
    log.info("    Drehsteller links  (PREV)    → up")
    log.info("    Drücken (PLAY/PAUSE)         → enter")
    log.info("    Zurück  (STOP)               → back")
    log.info("    2x Drücken                   → Jetzt läuft")

    # Hauptschleife: halten bis Service gestoppt wird
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
