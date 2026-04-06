"""
log.py - Logging fuer PiDrive
PiDrive - GPL-v3

Features:
  - Rotierende Logdatei (max 512 KB, 2 Backups)
  - Konsole: journalctl -u pidrive -f
  - Logfile: tail -f /var/log/pidrive/pidrive.log
  - Level: DEBUG, INFO, WARN, ERROR
"""

import logging
import logging.handlers
import os
import sys
import subprocess

LOG_DIR      = "/var/log/pidrive"
LOG_FILE     = os.path.join(LOG_DIR, "pidrive.log")
MAX_BYTES    = 512 * 1024
BACKUP_COUNT = 2

_logger = None

def setup(level=logging.DEBUG):
    global _logger
    if _logger:
        return _logger

    _logger = logging.getLogger("pidrive")
    _logger.setLevel(level)

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Logfile (rotierend)
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
        fallback = os.path.expanduser("~/.pidrive.log")
        fh = logging.handlers.RotatingFileHandler(
            fallback, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT
        )
        fh.setFormatter(fmt)
        _logger.addHandler(fh)

    # Konsole / journald
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    sh.setLevel(logging.INFO)
    _logger.addHandler(sh)

    # TTY ermitteln
    try:
        tty = subprocess.run("tty", capture_output=True,
                             text=True, timeout=2).stdout.strip()
    except Exception:
        tty = "unbekannt"

    _logger.info("=" * 50)
    _logger.info("PiDrive gestartet")
    _logger.info(f"  TTY:     {tty}")
    _logger.info(f"  FB:      {os.environ.get('SDL_FBDEV', '-')}")
    _logger.info(f"  Driver:  {os.environ.get('SDL_VIDEODRIVER', '-')}")
    _logger.info(f"  User:    {os.environ.get('USER', os.environ.get('LOGNAME', '?'))}")
    _logger.info("=" * 50)

    return _logger

def get():
    global _logger
    if _logger is None:
        return setup()
    return _logger

# Shortcuts
def debug(msg):  get().debug(msg)
def info(msg):   get().info(msg)
def warn(msg):   get().warning(msg)
def error(msg):  get().error(msg)

# Spezielle Log-Funktionen
def menu_change(from_cat, to_cat, item=None):
    if item:
        get().info(f"MENU  {from_cat} -> {to_cat} | {item}")
    else:
        get().info(f"MENU  -> {to_cat}")

def trigger_received(cmd):
    get().info(f"TRIGGER  {cmd}")

def action(name, result=""):
    if result:
        get().info(f"ACTION  {name}: {result}")
    else:
        get().info(f"ACTION  {name}")

def key_event(key):
    get().debug(f"KEY  {key}")

def status_update(wifi, bt, spotify, audio):
    get().debug(
        f"STATUS  wifi={wifi} bt={bt} "
        f"spotify={spotify} audio={audio}"
    )
