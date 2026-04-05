"""
log.py - Logging fuer PiDrive
Fake iPod Project - GPL-v3

Features:
  - Rotierende Logdatei (max 512 KB, 2 Backups)
  - Konsole: journalctl -u pidrive -f
  - Logfile: tail -f /var/log/pidrive/pidrive.log
  - Level: DEBUG, INFO, WARN, ERROR
  - Menü-Wechsel, Trigger, Fehler
"""

import logging
import logging.handlers
import os
import sys

LOG_DIR  = "/var/log/pidrive"
LOG_FILE = os.path.join(LOG_DIR, "pidrive.log")
MAX_BYTES   = 512 * 1024   # 512 KB
BACKUP_COUNT = 2            # 2 Backups -> max 1.5 MB gesamt

_logger = None

def setup(level=logging.DEBUG):
    """Logger einmalig initialisieren."""
    global _logger
    if _logger:
        return _logger

    _logger = logging.getLogger("pidrive")
    _logger.setLevel(level)

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # ── Logfile (rotierend) ───────────────────────────────────
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        fh = logging.handlers.RotatingFileHandler(
            LOG_FILE,
            maxBytes=MAX_BYTES,
            backupCount=BACKUP_COUNT,
            encoding="utf-8"
        )
        fh.setFormatter(fmt)
        _logger.addHandler(fh)
    except PermissionError:
        # Fallback: ~/.pidrive.log
        fallback = os.path.expanduser("~/.pidrive.log")
        fh = logging.handlers.RotatingFileHandler(
            fallback, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT
        )
        fh.setFormatter(fmt)
        _logger.addHandler(fh)

    # ── Konsole / journald (stdout) ───────────────────────────
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    sh.setLevel(logging.INFO)   # Konsole: nur INFO+
    _logger.addHandler(sh)

    _logger.info("=" * 50)
    _logger.info("PiDrive gestartet")
    _logger.info("=" * 50)

    return _logger

def get():
    """Logger holen (nach setup())."""
    global _logger
    if _logger is None:
        return setup()
    return _logger

# ── Shortcuts ─────────────────────────────────────────────────
def debug(msg):   get().debug(msg)
def info(msg):    get().info(msg)
def warn(msg):    get().warning(msg)
def error(msg):   get().error(msg)

# ── Spezielle Log-Funktionen ──────────────────────────────────
def menu_change(from_cat, to_cat, item=None):
    """Menü-Navigation loggen."""
    if item:
        get().info(f"MENU  {from_cat} -> {to_cat} | {item}")
    else:
        get().info(f"MENU  -> Kategorie: {to_cat}")

def trigger_received(cmd):
    """File-Trigger loggen."""
    get().info(f"TRIGGER  {cmd}")

def action(name, result=""):
    """Aktion loggen."""
    if result:
        get().info(f"ACTION  {name}: {result}")
    else:
        get().info(f"ACTION  {name}")

def key_event(key):
    """Tastatur-Event loggen (nur DEBUG)."""
    get().debug(f"KEY  {key}")

def status_update(wifi, bt, spotify, audio):
    """Statusänderung loggen."""
    get().debug(
        f"STATUS  wifi={wifi} bt={bt} "
        f"spotify={spotify} audio={audio}"
    )
