"""web/shared/ — Aufgeteilte Shared-Layer für PiDrive WebUI
Untermodule:
  files.py      — JSON lesen/schreiben, IPC-Datei-Zugriff
  system.py     — Shell-Calls, Version, IP, safe_run
  audio.py      — Audio-Debug, Volume, Source-State
  view_model.py — build_view_model(), DLS, DAB-Status, Spectrum
Für Rückwärtskompatibilität re-exportiert web/shared.py alles aus web/shared/*.
"""
# Alle Symbole für "from web.shared import *" verfügbar machen:
from web.shared.files import read_json, write_cmd, file_age  # noqa: F401
from web.shared.system import get_ip, safe_run, get_version  # noqa: F401
from web.shared.audio import (  # noqa: F401
    get_volume_data, get_audio_debug, get_source_state_debug
)
from web.shared.view_model import (  # noqa: F401
    build_view_model, get_dab_status_debug, get_dab_scan_debug,
    get_spectrum_debug, _load_stations_file
)
