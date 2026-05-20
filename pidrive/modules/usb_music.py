"""
usb_music.py — USB-Stick Erkennung für PiDrive v0.11.38

Scannt /media/ und /mnt/ nach gemounteten USB-Sticks mit Audiodateien.
Wird vom Menü, CLI und local_player verwendet.
"""

import os
import subprocess

AUDIO_EXT = {".mp3", ".flac", ".ogg", ".m4a", ".aac", ".wav", ".opus", ".m3u", ".m3u8"}

# Typische USB-Mount-Pfade auf Debian/Pi
_USB_ROOTS = [
    "/media",
    "/media/root",
    "/media/pidrive",
    "/mnt",
    "/run/media",
]


def _count_audio(path, max_scan=200):
    """Zählt Audiodateien im Pfad (begrenzt auf max_scan für Performance)."""
    count = 0
    try:
        for root, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for f in files:
                if os.path.splitext(f)[1].lower() in AUDIO_EXT:
                    count += 1
                    if count >= max_scan:
                        return count
    except Exception:
        pass
    return count


def _is_usb_mount(path):
    """Prüft ob ein Pfad ein USB-Gerät ist (via /proc/mounts)."""
    try:
        with open("/proc/mounts") as f:
            mounts = f.read()
        for line in mounts.splitlines():
            parts = line.split()
            if len(parts) >= 2 and parts[1] == path:
                dev = parts[0]
                # USB-Geräte: /dev/sd*, /dev/mmcblk* (nicht root), /dev/disk/...
                if (dev.startswith("/dev/sd") or
                        (dev.startswith("/dev/mmcblk") and "p" in dev and not dev.endswith("p1") is False)):
                    return True
                # Alle nicht-System-Devices akzeptieren (vfat/exfat = fast immer USB)
                fs = parts[2] if len(parts) > 2 else ""
                if fs in ("vfat", "exfat", "ntfs", "ntfs3", "fuseblk", "udf"):
                    return True
    except Exception:
        pass
    return False


def find_usb_sticks():
    """
    Gibt Liste von USB-Sticks mit Audiodateien zurück.
    Rückgabe: [{"name": str, "path": str, "files": int}]
    """
    found = []
    seen_paths = set()

    for root in _USB_ROOTS:
        if not os.path.isdir(root):
            continue
        try:
            for entry in os.scandir(root):
                if not entry.is_dir():
                    continue
                path = entry.path
                if path in seen_paths:
                    continue
                seen_paths.add(path)

                # Nur echte Mounts (nicht leere Verzeichnisse)
                if not os.path.ismount(path):
                    continue

                count = _count_audio(path)
                if count == 0:
                    continue

                name = entry.name
                found.append({
                    "name":  name,
                    "path":  path,
                    "files": count,
                    "label": f"USB: {name}",
                })
        except Exception:
            continue

    return found


def get_music_dir(settings: dict) -> str:
    """Gibt den konfigurierten Musikordner zurück."""
    return (settings.get("music_dir") or
            settings.get("music_path") or
            "/home/pidrive/Musik")
