"""
trigger.py - File-Trigger Handler (/tmp/pidrive_cmd)
PiDrive - GPL-v3

Alle Trigger werden geloggt.
Befehle:
  up, down, left, right, enter, back
  cat:0..3  (oder cat:Musik etc.)
  wifi_on, wifi_off
  bt_on, bt_off
  audio_klinke, audio_hdmi, audio_bt, audio_all
  spotify_on, spotify_off
  radio_stop, library_stop
  reboot, shutdown
"""

import os
import subprocess
import log

TRIGGER_FILE = "/tmp/pidrive_cmd"

def _bg(cmd):
    try:
        subprocess.Popen(cmd, shell=True,
                         stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
    except Exception as e:
        log.error(f"bg() Fehler: {e}")

def check(ui, status, settings):
    """Trigger-Datei pruefen und Befehl ausfuehren."""
    if not os.path.exists(TRIGGER_FILE):
        return
    try:
        with open(TRIGGER_FILE, "r") as f:
            cmd = f.read().strip()
        os.remove(TRIGGER_FILE)
        if cmd:
            log.trigger_received(cmd)
            _handle(cmd, ui, status, settings)
    except Exception as e:
        log.error(f"Trigger-Fehler: {e}")

def _handle(cmd, ui, status, settings):
    from status import invalidate

    if cmd == "up":
        ui.key_up()
    elif cmd == "down":
        ui.key_down()
    elif cmd == "right":
        ui.key_right()
    elif cmd == "left":
        ui.key_left()
    elif cmd == "enter":
        ui.key_enter()
    elif cmd == "back":
        ui.key_back()

    elif cmd == "wifi_on":
        log.action("WiFi", "einschalten")
        _bg("rfkill unblock wifi; ip link set wlan0 up; dhcpcd wlan0")
        invalidate()
    elif cmd == "wifi_off":
        log.action("WiFi", "ausschalten")
        _bg("rfkill block wifi")
        invalidate()

    elif cmd == "bt_on":
        log.action("Bluetooth", "einschalten")
        _bg("rfkill unblock bluetooth; hciconfig hci0 up")
        invalidate()
    elif cmd == "bt_off":
        log.action("Bluetooth", "ausschalten")
        _bg("hciconfig hci0 down")
        invalidate()

    elif cmd == "audio_klinke":
        log.action("Audio", "Klinke")
        _bg("amixer -c 0 cset numid=3 1 2>/dev/null")
        settings["audio_output"] = "Klinke"
    elif cmd == "audio_hdmi":
        log.action("Audio", "HDMI")
        _bg("amixer -c 0 cset numid=3 2 2>/dev/null")
        settings["audio_output"] = "HDMI"
    elif cmd == "audio_bt":
        sink = status.S.get("bt_sink", "")
        if sink:
            log.action("Audio", f"Bluetooth Sink: {sink}")
            _bg(f"pactl set-default-sink {sink} 2>/dev/null")
            settings["audio_output"] = "Bluetooth"
        else:
            log.warn("Audio BT: kein Sink gefunden")
    elif cmd == "audio_all":
        log.action("Audio", "Kombiniert")
        _bg("pactl load-module module-combine-sink sink_name=combined 2>/dev/null; "
            "pactl set-default-sink combined 2>/dev/null")
        settings["audio_output"] = "Alle"

    elif cmd == "spotify_on":
        log.action("Spotify", "starten")
        _bg("systemctl start raspotify")
        invalidate()
    elif cmd == "spotify_off":
        log.action("Spotify", "stoppen")
        _bg("systemctl stop raspotify")
        invalidate()

    elif cmd == "radio_stop":
        log.action("Webradio", "stoppen")
        _bg("pkill -f fakeipod_radio 2>/dev/null; pkill -f pidrive_radio 2>/dev/null")
        status.S["radio_playing"] = False

    elif cmd == "library_stop":
        log.action("Bibliothek", "stoppen")
        _bg("pkill -f pidrive_library 2>/dev/null")
        status.S["library_playing"] = False

    elif cmd == "reboot":
        log.action("System", "Neustart")
        _bg("reboot")
    elif cmd == "shutdown":
        log.action("System", "Ausschalten")
        _bg("poweroff")

    elif cmd.startswith("cat:"):
        val = cmd[4:]
        old_cat = ui.cat_sel
        try:
            ui.cat_sel = int(val)
        except ValueError:
            for i, c in enumerate(ui.categories):
                if c.label.lower() == val.lower():
                    ui.cat_sel = i
                    break
        ui.item_sel = ui.item_scroll = 0
        ui.focus = "right"
        ui.stack.clear()
        log.menu_change(
            ui.categories[old_cat].label,
            ui.categories[ui.cat_sel].label
        )

    else:
        log.warn(f"Unbekannter Trigger-Befehl: '{cmd}'")
