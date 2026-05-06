"""
log.py - Logging fuer PiDrive v0.7.10
PiDrive - GPL-v3

Features:
  - Getrennte Logs: core.log und display.log (GPT-5.4)
  - Gemeinsames pidrive.log als Fallback
  - Rotierende Logdatei (max 512 KB, 2 Backups)
  - journalctl -u pidrive_core -f  /  journalctl -u pidrive_display -f
"""

import logging
import logging.handlers
import os
import sys
import subprocess

LOG_DIR      = "/var/log/pidrive"
LOG_FILE     = os.path.join(LOG_DIR, "pidrive.log")   # Fallback / legacy
CORE_LOG     = os.path.join(LOG_DIR, "core.log")
DISPLAY_LOG  = os.path.join(LOG_DIR, "display.log")
MAX_BYTES    = 512 * 1024
BACKUP_COUNT = 2

_logger = None

def setup(component="core", level=logging.DEBUG):
    """component: 'core' oder 'display' — bestimmt Log-Datei."""
    global _logger
    if _logger:
        return _logger

    log_file = CORE_LOG if component == "core" else DISPLAY_LOG

    _logger = logging.getLogger(f"pidrive.{component}")
    _logger.setLevel(level)

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        # Komponenten-spezifische Log-Datei
        fh = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT,
            encoding="utf-8"
        )
        fh.setFormatter(fmt)
        _logger.addHandler(fh)
        # Gemeinsames pidrive.log fuer tail -f kompatibilitaet
        fh2 = logging.handlers.RotatingFileHandler(
            LOG_FILE, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT,
            encoding="utf-8"
        )
        fh2.setFormatter(fmt)
        _logger.addHandler(fh2)
    except PermissionError:
        fallback = os.path.expanduser("~/.pidrive.log")
        fh = logging.handlers.RotatingFileHandler(
            fallback, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT)
        fh.setFormatter(fmt)
        _logger.addHandler(fh)

    # v0.10.44: nur WARNING+ auf stderr → journald, INFO geht in Datei-Logs
    # Verhindert Doppel-Persistenz INFO-Zeilen (Datei + Journal)
    sh = logging.StreamHandler(sys.stderr)
    sh.setFormatter(fmt)
    sh.setLevel(logging.WARNING)
    _logger.addHandler(sh)

    try:
        tty = subprocess.run("tty", capture_output=True,
                             text=True, timeout=2).stdout.strip()
    except Exception:
        tty = "kein Terminal"

    _logger.info("=" * 50)
    _logger.info(f"PiDrive {component.upper()} gestartet")
    _logger.info(f"  TTY:     {tty}")
    if component == "display":
        _logger.info(f"  FB:      {os.environ.get('SDL_FBDEV', '-')}")
        _logger.info(f"  Driver:  {os.environ.get('SDL_VIDEODRIVER', '-')}")
    _logger.info(f"  User:    {os.environ.get('USER', os.environ.get('LOGNAME', 'root'))}")
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

def menu_change(from_cat, to_cat, item=None):
    get().info(f"MENU  {from_cat} -> {to_cat}" + (f" | {item}" if item else ""))

def trigger_received(cmd):
    get().info(f"TRIGGER  {cmd}")

def action(name, result=""):
    get().info(f"ACTION  {name}" + (f": {result}" if result else ""))

def key_event(key):
    get().debug(f"KEY  {key}")

def status_update(wifi, bt, spotify, audio):
    get().debug(f"STATUS  wifi={wifi} bt={bt} spotify={spotify} audio={audio}")
