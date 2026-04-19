"""
modules/bt_backup.py — Bluetooth Pairing-Keys Backup/Restore (v0.8.25)

Problem: BlueZ verliert nach Reboot die Pairing-Daten aus /var/lib/bluetooth/
Ursache: bluetoothd-Neustart oder SD-Karten-Schreibfehler

Lösung: Backup der BlueZ-Datenbank nach /home/pi/pidrive/config/bt_pairs/
Restore: vor Connect-Versuch prüfen ob Backup vorhanden und restaurieren

Backup-Verzeichnis: ~/pidrive/pidrive/config/bt_pairs/
Struktur spiegelt /var/lib/bluetooth/ 1:1
"""

import os
import shutil
import subprocess
import time
import log

BT_SRC   = "/var/lib/bluetooth"
BT_DEST  = os.path.join(os.path.dirname(__file__), "..", "config", "bt_pairs")
BT_DEST  = os.path.normpath(BT_DEST)


def backup() -> dict:
    """
    Sichert /var/lib/bluetooth/ nach config/bt_pairs/.
    Gibt {"ok": bool, "count": int, "path": str} zurück.
    """
    result = {"ok": False, "count": 0, "path": BT_DEST}
    try:
        if not os.path.isdir(BT_SRC):
            result["error"] = f"{BT_SRC} nicht gefunden"
            return result

        # Inhalt zählen
        entries = []
        for root, dirs, files in os.walk(BT_SRC):
            entries.extend(files)

        if not entries:
            result["error"] = "Keine Pairing-Daten in /var/lib/bluetooth/"
            return result

        # Backup anlegen
        os.makedirs(BT_DEST, exist_ok=True)
        if os.path.exists(BT_DEST):
            shutil.rmtree(BT_DEST)
        shutil.copytree(BT_SRC, BT_DEST)

        result["ok"]    = True
        result["count"] = len(entries)
        log.info(f"BT-Backup: {len(entries)} Dateien gesichert → {BT_DEST}")
        return result
    except Exception as e:
        result["error"] = str(e)
        log.error(f"BT-Backup: Fehler: {e}")
        return result


def restore() -> dict:
    """
    Stellt /var/lib/bluetooth/ aus config/bt_pairs/ wieder her.
    Startet bluetoothd danach neu damit Änderungen wirksam werden.
    """
    result = {"ok": False, "count": 0}
    try:
        if not os.path.isdir(BT_DEST):
            result["error"] = "Kein Backup vorhanden (noch nie gesichert?)"
            return result

        entries = []
        for root, dirs, files in os.walk(BT_DEST):
            entries.extend(files)

        if not entries:
            result["error"] = "Backup-Verzeichnis leer"
            return result

        # Restore
        if os.path.exists(BT_SRC):
            shutil.rmtree(BT_SRC)
        shutil.copytree(BT_DEST, BT_SRC)

        # Berechtigungen setzen
        subprocess.run(["chown", "-R", "root:bluetooth", BT_SRC],
                       capture_output=True, timeout=5)
        subprocess.run(["chmod", "-R", "700", BT_SRC],
                       capture_output=True, timeout=5)

        # bluetoothd neu starten damit er die restored Daten lädt
        subprocess.run(["systemctl", "restart", "bluetooth"],
                       capture_output=True, timeout=15)
        time.sleep(2)

        result["ok"]    = True
        result["count"] = len(entries)
        log.info(f"BT-Restore: {len(entries)} Dateien wiederhergestellt, bluetoothd neugestartet")
        return result
    except Exception as e:
        result["error"] = str(e)
        log.error(f"BT-Restore: Fehler: {e}")
        return result


def has_backup() -> bool:
    """Gibt True zurück wenn ein Backup vorhanden ist."""
    return os.path.isdir(BT_DEST) and any(
        files for _, _, files in os.walk(BT_DEST)
    )


def backup_info() -> dict:
    """Infos über vorhandenes Backup (Datum, Geräteanzahl)."""
    if not has_backup():
        return {"available": False}
    try:
        devices = []
        # BlueZ speichert: /var/lib/bluetooth/<adapter>/<mac>/info
        for adapter in os.listdir(BT_DEST):
            adapter_path = os.path.join(BT_DEST, adapter)
            if os.path.isdir(adapter_path):
                for mac in os.listdir(adapter_path):
                    mac_path = os.path.join(adapter_path, mac)
                    info_file = os.path.join(mac_path, "info")
                    if os.path.isfile(info_file):
                        # Name aus info-Datei lesen
                        name = mac
                        try:
                            with open(info_file) as f:
                                for line in f:
                                    if line.startswith("Name="):
                                        name = line.strip()[5:]
                                        break
                        except Exception:
                            pass
                        devices.append({"mac": mac, "name": name})
        ts = os.path.getmtime(BT_DEST)
        import datetime
        backup_date = datetime.datetime.fromtimestamp(ts).strftime("%d.%m.%Y %H:%M")
        return {
            "available": True,
            "devices":   devices,
            "date":      backup_date,
            "path":      BT_DEST,
        }
    except Exception as e:
        return {"available": True, "error": str(e)}
