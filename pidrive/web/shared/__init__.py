"""web/shared/ — Shared-Layer für PiDrive WebUI
Single-Import-Point: from web.shared import X funktioniert für ALLE Symbole.

Untermodule:
  constants.py  — alle IPC-Pfade, ALLOWED_COMMANDS, PA_ENV
  files.py      — JSON lesen/schreiben, IPC-Datei-Zugriff
  system.py     — Shell-Calls, Version, IP, safe_run
  audio.py      — Audio-Debug, Volume, Source-State
  view_model.py — build_view_model(), DLS, DAB-Status, Spectrum
"""
# ── Konstanten (Single Source of Truth) ────────────────────────────────
from web.shared.constants import (  # noqa: F401
    BASE_DIR,
    CMD_FILE, STATUS_FILE, MENU_FILE, PROGRESS_FILE,
    RTLSDR_FILE, AVRCP_FILE, LIST_FILE, LOG_FILE,
    READY_FILE,     KNOWN_BT_FILE, BT_AGENT_FILE,
    DAB_DEBUG_FILE, STATIONS_FILE, DISC_BT_FILE,
    PA_ENV, ALLOWED_COMMANDS,
)

# ── Datei-/IPC-Helfer ───────────────────────────────────────────────────
from web.shared.files import (  # noqa: F401
    read_json, write_cmd, file_age,
)

# ── System-/Shell-Helfer ────────────────────────────────────────────────
from web.shared.system import (  # noqa: F401
    get_ip, safe_run, get_version,
)

# ── Audio-Debug ─────────────────────────────────────────────────────────
from web.shared.audio import (  # noqa: F401
    get_volume_data, get_audio_debug, get_source_state_debug,
)

# ── ViewModel + DAB/DLS ─────────────────────────────────────────────────
from web.shared.view_model import (  # noqa: F401
    build_view_model, get_dab_status_debug,
    get_dab_scan_debug, get_spectrum_debug,
    _load_stations_file, _compose_dls_text,
)
