"""
modules/audio.py - Audioausgang Modul
PiDrive v0.6.1 - pygame-frei
"""
import subprocess, time, ipc
from ui import Item

def _bg(cmd):
    try: subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except: pass

def set_output(mode, S, settings):
    if mode == "Klinke":
        _bg("amixer -c 0 cset numid=3 1 2>/dev/null"); settings["audio_output"] = "Klinke"
    elif mode == "HDMI":
        _bg("amixer -c 0 cset numid=3 2 2>/dev/null"); settings["audio_output"] = "HDMI"
    elif mode == "Bluetooth":
        sink = S.get("bt_sink", "")
        if sink: _bg(f"pactl set-default-sink {sink} 2>/dev/null"); settings["audio_output"] = "BT"
    elif mode == "Alle":
        _bg("pactl load-module module-combine-sink sink_name=combined 2>/dev/null; pactl set-default-sink combined 2>/dev/null")
        settings["audio_output"] = "Alle"

def build_items(screen, S, settings):
    def select_output():
        options = ["Klinke (3.5mm)", "HDMI", "Bluetooth", "Alle kombiniert"]
        chosen = ipc.headless_pick("Audioausgang", options)
        if not chosen: return
        mode = chosen.split(" ")[0]
        if mode == "Alle": mode = "Alle"
        if mode == "Bluetooth" and not S.get("bt_sink"):
            ipc.write_progress("Audio", "Kein BT verbunden!", color="orange"); time.sleep(2); ipc.clear_progress(); return
        set_output(mode, S, settings)
        ipc.write_progress("Audio", f"{mode} aktiv", color="green"); time.sleep(1); ipc.clear_progress()

    return [
        Item("Ausgang", sub=lambda: settings.get("audio_output", "auto"), action=select_output),
        Item("Lauter",  action=lambda: _bg("amixer -q sset Master 5%+")),
        Item("Leiser",  action=lambda: _bg("amixer -q sset Master 5%-")),
    ]


def volume_up(settings):
    """Lautstärke erhöhen."""
    import subprocess, ipc, time
    try:
        subprocess.run(["amixer","sset","PCM","5%+"],
                       capture_output=True, timeout=3)
        ipc.write_progress("Lautstärke", "Erhöht ↑", color="green")
        time.sleep(1); ipc.clear_progress()
    except Exception as e:
        import log; log.error(f"volume_up: {e}")

def volume_down(settings):
    """Lautstärke verringern."""
    import subprocess, ipc, time
    try:
        subprocess.run(["amixer","sset","PCM","5%-"],
                       capture_output=True, timeout=3)
        ipc.write_progress("Lautstärke", "Verringert ↓", color="orange")
        time.sleep(1); ipc.clear_progress()
    except Exception as e:
        import log; log.error(f"volume_down: {e}")

def select_output_interactive(S, settings):
    """Audioausgang via headless_pick auswählen."""
    import ipc
    options = ["Klinke (AUX)", "HDMI", "Bluetooth", "Alle"]
    chosen  = ipc.headless_pick("Audioausgang", options)
    if chosen:
        mapping = {"Klinke (AUX)":"klinke","HDMI":"hdmi","Bluetooth":"bt","Alle":"all"}
        set_output(mapping.get(chosen,"klinke"), settings)
