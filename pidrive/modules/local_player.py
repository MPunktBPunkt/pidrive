"""
local_player.py — Lokale Musikwiedergabe für PiDrive v0.11.76
Unterstützt: Einzeldateien, Ordner, M3U-Playlisten, Shuffle.
Audio über PipeWire-Compat → BT/Klinke wie alle anderen Quellen.
"""

import os, subprocess, threading, glob, json, time
import log

AUDIO_EXTS = {'.mp3', '.flac', '.ogg', '.m4a', '.aac', '.wav', '.opus', '.wma'}
_proc_lock  = threading.Lock()
_player_proc = None
_current_path = ""
_current_playlist = []
_current_idx = 0


def _is_audio(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in AUDIO_EXTS


def _collect_files(path: str) -> list:
    """Datei, Ordner oder M3U → sortierte Dateiliste."""
    path = os.path.expanduser(path)
    if not os.path.exists(path):
        return []
    if os.path.isfile(path):
        ext = os.path.splitext(path)[1].lower()
        if ext == '.m3u':
            lines = open(path, encoding='utf-8', errors='replace').readlines()
            base = os.path.dirname(path)
            return [os.path.join(base, l.strip()) for l in lines
                    if l.strip() and not l.startswith('#') and
                    os.path.isfile(os.path.join(base, l.strip()))]
        return [path] if _is_audio(path) else []
    if os.path.isdir(path):
        files = sorted([
            os.path.join(r, f)
            for r, _, fs in os.walk(path)
            for f in fs
            if _is_audio(f)
        ])
        return files
    return []


def list_files(path: str) -> list:
    """Gibt Dateiliste für einen Pfad zurück."""
    return _collect_files(path)


def play(path: str, S: dict, settings: dict,
         shuffle: bool = False, idx: int = 0) -> bool:
    """Startet lokale Wiedergabe.
    path: Datei, Ordner oder M3U-Playlist.
    """
    global _player_proc, _current_path, _current_playlist, _current_idx

    files = _collect_files(path)
    if not files:
        log.warn(f"local_player: keine Audio-Dateien in {path!r}")
        return False

    if shuffle:
        import random; files = files[:]
        random.shuffle(files)

    stop(S)

    _current_path     = path
    _current_playlist = files
    _current_idx      = min(idx, len(files) - 1)

    _start_mpv(files[_current_idx:], S, settings)
    # source_current wird durch td_radio.commit_source("local") gesetzt — hier nur Metadaten
    S["radio_type"]    = "LOCAL"
    S["radio_playing"] = True
    S["radio_name"]    = os.path.basename(files[_current_idx])
    S["radio_station"] = path
    S["metadata_unavailable"] = False
    log.info(f"local_player: {len(files)} Dateien ab {files[_current_idx]!r}")
    return True


def _start_mpv(files: list, S: dict, settings: dict):
    """Startet mpv mit der Dateiliste."""
    global _player_proc
    from modules import audio as _audio
    sink = _audio.get_bt_sink() or _audio.get_alsa_sink() or ""
    env = dict(os.environ, PULSE_SERVER="unix:/var/run/pulse/native")
    if sink:
        env["PULSE_SINK"] = sink

    cmd = [
        "mpv", "--no-video", "--really-quiet",
        "--title=pidrive_local",
        f"--audio-device=pulse/{sink}" if sink else "--ao=pulse",
    ] + files

    with _proc_lock:
        _player_proc = subprocess.Popen(
            cmd, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, env=env
        )
    log.info(f"local_player: mpv PID={_player_proc.pid}")


def stop(S: dict):
    global _player_proc, _current_playlist
    with _proc_lock:
        if _player_proc:
            try: _player_proc.terminate()
            except Exception: pass
            _player_proc = None
    _current_playlist = []
    S.pop("radio_playing", None)
    # source_current → td_nav._stop_all_sources oder commit_source("idle")
    S["radio_type"] = ""


def is_playing() -> bool:
    with _proc_lock:
        return _player_proc is not None and _player_proc.poll() is None


def current_info() -> dict:
    return {
        "path":     _current_path,
        "files":    len(_current_playlist),
        "current":  os.path.basename(_current_playlist[_current_idx])
                    if _current_playlist else "",
        "idx":      _current_idx,
        "playing":  is_playing(),
    }
