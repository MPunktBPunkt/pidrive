"""web/shared/constants.py — IPC-Pfade und globale Konstanten
Single Source of Truth für alle /tmp/pidrive_*.json Pfade.
Wird von web/shared/__init__.py re-exportiert.
"""
import os as _os
from pathlib import Path as _Path

# ── Base-Directory ──────────────────────────────────────────────────────
# web/shared/constants.py liegt unter pidrive/web/shared/ → 3 Ebenen hoch
BASE_DIR = _Path(__file__).resolve().parent.parent.parent  # → pidrive/

# ── IPC-Dateipfade ──────────────────────────────────────────────────────
CMD_FILE      = "/tmp/pidrive_cmd"
STATUS_FILE   = "/tmp/pidrive_status.json"
MENU_FILE     = "/tmp/pidrive_menu.json"
PROGRESS_FILE = "/tmp/pidrive_progress.json"
RTLSDR_FILE   = "/tmp/pidrive_rtlsdr.json"
AVRCP_FILE    = "/tmp/pidrive_avrcp.json"
LIST_FILE     = "/tmp/pidrive_list.json"
LOG_FILE      = "/var/log/pidrive/pidrive.log"
READY_FILE    = "/tmp/pidrive_ready"
KNOWN_BT_FILE = "/tmp/pidrive_bt_known_devices.json"
DISC_BT_FILE  = "/tmp/pidrive_bt_devices.json"
BT_AGENT_FILE = "/tmp/pidrive_bt_agent.json"
WATCHER_STATE_FILE = "/tmp/pidrive_bt_watcher.json"
DAB_DEBUG_FILE= "/tmp/pidrive_dab_play_debug.json"

# STATIONS_FILE verwendet BASE_DIR (config liegt unter pidrive/config/)
STATIONS_FILE = _os.path.join(BASE_DIR, "config", "stations.json")

# ── PulseAudio ──────────────────────────────────────────────────────────
PA_ENV = "PULSE_SERVER=unix:" + __import__("os").environ.get("PULSE_SOCKET", "/var/run/pulse/native")

# ── Erlaubte Trigger-Kommandos ──────────────────────────────────────────
ALLOWED_COMMANDS = {
    "up", "down", "left", "right", "enter", "back",
    "wifi_on", "wifi_off", "wifi_toggle", "wifi_scan",
    "bt_on", "bt_off", "bt_toggle", "bt_scan",
    "bt_disconnect", "bt_reconnect_last",
    "spotify_on", "spotify_off", "spotify_toggle", "play_spotify",
    "radio_stop", "library_stop",
    "stop",  # Alias → radio_stop (Web/CLI Kompatibilität)
    "audio_klinke", "audio_hdmi", "audio_bt", "audio_all", "audio_usb_gadget",
    "vol_up", "vol_set", "vol_down",
    "gain_fm_auto", "gain_dab_auto",
    "dab_scan", "dab_scan_replace", "fm_scan",
    "fm_next", "fm_prev", "dab_next", "dab_prev",
    "web_next", "web_prev",
    "lib_browse",
    "reboot", "shutdown", "sys_info", "sys_version", "update",
    "rtlsdr_reset",
    "bt_backup", "bt_restore",
    "scanner_stop",
    "pmr_monitor_start", "pmr_monitor_stop",
    "airband_monitor_start", "airband_monitor_stop",
    "airband_tune_save",
    "fm_tune_save",
    "favorites_add_current", "favorites_add", "favorites_remove",
}

# Präfixe für /api/cmd — Single Source of Truth (auch webui_check / app.py)
ALLOWED_COMMAND_PREFIXES = (
    "cat:", "reload_stations:",
    "scan_up:", "scan_down:", "scan_next:", "scan_prev:",
    "scan_jump:", "scan_step:", "scan_setfreq:", "scan_setch:", "scan_inputfreq:",
    "dab_scan_channels:", "bt_connect:", "bt_forget:", "wifi_connect:", "bt_repair:",
    "fm_gain:", "dab_gain:", "ppm:", "squelch:", "scanner_gain:",
    "set_scanner_squelch:", "set_ppm:",
    "airband_gain_step:", "airband_sr_step:", "airband_gain:", "airband_sr:",
    "airband_hp_step:", "airband_lp_step:",
    "fm_hp_step:", "fm_lp_step:",
    "webradio_play:",
    "local_play:",
    "play_dab:", "play_fm:", "play_web:",
    "favorites_play:",
    "vol_set:",
)
