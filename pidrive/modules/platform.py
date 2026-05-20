"""
modules/platform.py — Hardware-Capability-Detection  v0.11.30
==============================================================
Einmalig beim Start ausgewertet. Alle Subsysteme prüfen
nur noch CAPS statt /proc/cpuinfo oder importierte Hardware.

Verwendung:
    from modules.platform import CAPS
    if CAPS["rtlsdr"]:
        ...
    if CAPS["dab"]:
        ...
"""
import os
import shutil
import subprocess

# ─────────────────────────────────────────────────────────────────────────────
# Hilfsfunktionen
# ─────────────────────────────────────────────────────────────────────────────

def _cmd_exists(name: str) -> bool:
    return shutil.which(name) is not None

def _path_exists(path: str) -> bool:
    return os.path.exists(path)

def _is_pi() -> bool:
    try:
        return "raspberry pi" in open("/proc/cpuinfo").read().lower()
    except Exception:
        return False

def _is_container() -> bool:
    if _path_exists("/.dockerenv") or _path_exists("/run/.containerenv"):
        return True
    try:
        r = subprocess.run(
            ["systemd-detect-virt", "--container", "-q"],
            capture_output=True, timeout=2
        )
        return r.returncode == 0
    except Exception:
        return False

def _is_arm() -> bool:
    import platform
    m = platform.machine()
    return m.startswith("arm") or m == "aarch64"

def _headphone_card() -> int | None:
    """ALSA-Karte mit 'Headphones' oder 'Analog' — None wenn keine gefunden."""
    try:
        r = subprocess.run("aplay -l 2>/dev/null", shell=True,
                           capture_output=True, text=True, timeout=5)
        for line in r.stdout.splitlines():
            low = line.lower()
            if "headphone" in low or "analog" in low:
                import re as _re
                m = _re.search(r"card (\d+)", line, _re.I)
                if m:
                    return int(m.group(1))
    except Exception:
        pass
    return 1 if _is_pi() else None  # Pi-Fallback

def _pa_running() -> bool:
    return _path_exists("/var/run/pulse/native")

def _bt_available() -> bool:
    """Bluetooth-Adapter vorhanden (mit Socket-Zugriff-Test fuer LXC)."""
    # Schritt 1: Adapter im sys-Filesystem vorhanden?
    has_adapter = False
    if os.path.isdir("/sys/class/bluetooth"):
        try:
            entries = [e for e in os.listdir("/sys/class/bluetooth")
                       if e.startswith("hci")]
            has_adapter = bool(entries)
        except Exception:
            pass
    if not has_adapter:
        return False

    # Schritt 2: Tatsaechlichen Socket-Zugriff pruefen (LXC kann Adapter sehen
    # aber AF_BLUETOOTH Socket sperren)
    try:
        import socket
        s = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_RAW,
                          socket.BTPROTO_HCI)
        s.close()
        return True  # Socket-Zugriff OK
    except (OSError, AttributeError):
        # Socket gesperrt (LXC-Restriktion) — Adapter vorhanden aber nicht nutzbar
        return False

# ─────────────────────────────────────────────────────────────────────────────
# CAPS — einmalig beim Import ausgewertet
# ─────────────────────────────────────────────────────────────────────────────

def bt_socket_restricted() -> bool:
    """True wenn BT-Adapter sichtbar aber Socket-Zugriff gesperrt (typisch LXC)."""
    if not os.path.isdir("/sys/class/bluetooth"):
        return False
    try:
        entries = [e for e in os.listdir("/sys/class/bluetooth") if e.startswith("hci")]
        if not entries:
            return False
    except Exception:
        return False
    # Adapter da, aber Socket-Check
    try:
        import socket
        s = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_RAW, socket.BTPROTO_HCI)
        s.close()
        return False  # Kein Problem
    except (OSError, AttributeError):
        return True  # Adapter da, Socket gesperrt → LXC-Restriktion


CAPS: dict = {
    # Plattform
    "is_pi":           _is_pi(),
    "is_container":    _is_container(),
    "is_arm":          _is_arm(),
    # Audio
    "pulseaudio":      _pa_running(),
    "alsa_card":       _headphone_card(),    # int oder None
    "alsa_device":     None,                 # gesetzt nach alsa_card Auswertung
    # RTL-SDR
    "rtlsdr":          _cmd_exists("rtl_fm") or _cmd_exists("rtl_sdr"),
    "rtl_fm":          _cmd_exists("rtl_fm"),
    "rtl_sdr":         _cmd_exists("rtl_sdr"),
    "dab":             _cmd_exists("welle-cli"),
    # Bluetooth
    "bluetooth":       _bt_available(),
    "bt_lxc_restricted": bt_socket_restricted(),  # hci sichtbar aber Socket gesperrt
    "bluetoothctl":    _cmd_exists("bluetoothctl"),
    # Spotify
    "spotify":         _cmd_exists("librespot") or _cmd_exists("raspotify"),
    # Webradio
    "mpv":             _cmd_exists("mpv"),
    # Display — bewusst immer False (Display-Unterstützung entfernt)
    "display":         False,
    "gpio":            False,
}

# alsa_device aus alsa_card ableiten
_card = CAPS["alsa_card"]
CAPS["alsa_device"] = f"hw:{_card},0" if _card is not None else None


def describe() -> str:
    """Gibt eine einzeilige Plattform-Beschreibung zurück."""
    platform_parts = []
    if CAPS["is_pi"]:       platform_parts.append("Raspberry Pi")
    if CAPS["is_container"]:platform_parts.append("Container")
    if CAPS["is_arm"]:      platform_parts.append("ARM")
    else:                   platform_parts.append("x86")

    hw_parts = []
    if CAPS["rtlsdr"]:   hw_parts.append("RTL-SDR")
    if CAPS["dab"]:      hw_parts.append("DAB+")
    if CAPS["bluetooth"]:hw_parts.append("BT")
    if CAPS["pulseaudio"]:hw_parts.append("PA")
    if CAPS["spotify"]:  hw_parts.append("Spotify")

    return " | ".join(platform_parts) + "  [" + ", ".join(hw_parts or ["minimal"]) + "]"
