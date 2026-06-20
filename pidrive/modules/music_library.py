#!/usr/bin/env python3
"""music_library.py — Lokale Medienbibliothek (WebUI + Pfad-Sandbox)  v0.11.127

Alle Pfade müssen unter settings.music_dir liegen.
"""

import os
from typing import Optional

from modules.local_player import AUDIO_EXTS

AUDIO_EXT_LIST = sorted(AUDIO_EXTS)


def get_music_root(settings: Optional[dict] = None) -> str:
    if settings is None:
        try:
            from settings import load_settings
            settings = load_settings()
        except Exception:
            settings = {}
    root = (
        settings.get("music_dir")
        or settings.get("music_path")
        or "/home/pidrive/Musik"
    )
    root = os.path.expanduser(root)
    os.makedirs(root, exist_ok=True)
    return os.path.realpath(root)


def _safe_rel(rel: str) -> str:
    rel = (rel or "").replace("\\", "/").strip("/")
    parts = []
    for part in rel.split("/"):
        if not part or part in (".", ".."):
            continue
        parts.append(part)
    return "/".join(parts)


def resolve_in_library(rel_path: str = "", settings: Optional[dict] = None) -> str:
    """Relativen Pfad (unter music_dir) → absoluter, validierter Pfad."""
    root = get_music_root(settings)
    rel = _safe_rel(rel_path)
    candidate = os.path.join(root, rel) if rel else root
    real_root = os.path.realpath(root)
    real_path = os.path.realpath(os.path.normpath(candidate))
    if real_path != real_root and not real_path.startswith(real_root + os.sep):
        raise ValueError("Pfad liegt ausserhalb der Medienbibliothek")
    return real_path


def rel_from_abs(abs_path: str, settings: Optional[dict] = None) -> str:
    root = get_music_root(settings)
    real_root = os.path.realpath(root)
    real_path = os.path.realpath(abs_path)
    if real_path == real_root:
        return ""
    if not real_path.startswith(real_root + os.sep):
        raise ValueError("Pfad liegt ausserhalb der Medienbibliothek")
    return real_path[len(real_root) + 1:].replace("\\", "/")


def list_dir(rel_path: str = "", settings: Optional[dict] = None) -> dict:
    path = resolve_in_library(rel_path, settings)
    root = get_music_root(settings)
    if not os.path.isdir(path):
        raise FileNotFoundError(rel_path or "/")

    dirs, files = [], []
    for name in sorted(os.listdir(path), key=str.lower):
        if name.startswith("."):
            continue
        full = os.path.join(path, name)
        rel = rel_from_abs(full, settings)
        if os.path.isdir(full):
            n_audio = sum(
                1 for r, _, fs in os.walk(full)
                for f in fs
                if os.path.splitext(f)[1].lower() in AUDIO_EXTS
            )
            dirs.append({"name": name, "path": rel, "files": n_audio})
        else:
            ext = os.path.splitext(name)[1].lower()
            if ext in AUDIO_EXTS or ext == ".m3u":
                st = os.stat(full)
                files.append({
                    "name": name,
                    "path": rel,
                    "size": st.st_size,
                    "ext": ext.lstrip("."),
                })

    total_bytes = sum(
        os.path.getsize(os.path.join(r, f))
        for r, _, fs in os.walk(root)
        for f in fs
        if os.path.splitext(f)[1].lower() in AUDIO_EXTS
    )
    return {
        "root": root,
        "path": _safe_rel(rel_path),
        "dirs": dirs,
        "files": files,
        "total_bytes": total_bytes,
    }


def mkdir(rel_path: str, name: str, settings: Optional[dict] = None) -> str:
    name = _safe_rel(name)
    if not name or "/" in name:
        raise ValueError("Ungültiger Ordnername")
    parent = resolve_in_library(rel_path, settings)
    target = os.path.join(parent, name)
    real_parent = resolve_in_library(rel_path, settings)
    real_target = os.path.realpath(target)
    if not real_target.startswith(real_parent + os.sep) and real_target != real_parent:
        raise ValueError("Ungültiger Zielpfad")
    os.makedirs(target, exist_ok=False)
    return rel_from_abs(target, settings)


def delete_path(rel_path: str, settings: Optional[dict] = None) -> None:
    if not _safe_rel(rel_path):
        raise ValueError("Bibliotheks-Root kann nicht gelöscht werden")
    path = resolve_in_library(rel_path, settings)
    if os.path.isdir(path):
        if os.listdir(path):
            raise ValueError("Ordner ist nicht leer")
        os.rmdir(path)
    elif os.path.isfile(path):
        os.remove(path)
    else:
        raise FileNotFoundError(rel_path)


def rename_entry(rel_path: str, new_name: str, settings: Optional[dict] = None) -> str:
    if not _safe_rel(rel_path):
        raise ValueError("Root kann nicht umbenannt werden")
    new_name = _safe_rel(new_name)
    if not new_name or "/" in new_name:
        raise ValueError("Ungültiger Name")
    src = resolve_in_library(rel_path, settings)
    dst = os.path.join(os.path.dirname(src), new_name)
    resolve_in_library(rel_from_abs(dst, settings), settings)
    os.rename(src, dst)
    return rel_from_abs(dst, settings)


def save_upload(rel_dir: str, filename: str, data: bytes,
                settings: Optional[dict] = None) -> str:
    from werkzeug.utils import secure_filename
    name = secure_filename(filename or "upload.mp3")
    if not name:
        raise ValueError("Ungültiger Dateiname")
    ext = os.path.splitext(name)[1].lower()
    if ext not in AUDIO_EXTS and ext != ".m3u":
        raise ValueError(f"Dateityp nicht erlaubt: {ext or '?'}")
    parent = resolve_in_library(rel_dir, settings)
    target = os.path.join(parent, name)
    if os.path.exists(target):
        base, ext2 = os.path.splitext(name)
        n = 2
        while os.path.exists(target):
            target = os.path.join(parent, f"{base}_{n}{ext2}")
            n += 1
    with open(target, "wb") as f:
        f.write(data)
    return rel_from_abs(target, settings)


def read_tags(rel_path: str, settings: Optional[dict] = None) -> dict:
    path = resolve_in_library(rel_path, settings)
    if not os.path.isfile(path):
        raise FileNotFoundError(rel_path)
    ext = os.path.splitext(path)[1].lower()
    if ext not in AUDIO_EXTS:
        return {"path": rel_path, "editable": False}

    tags = {
        "path": rel_path,
        "editable": True,
        "title": "",
        "artist": "",
        "album": "",
        "genre": "",
        "tracknumber": "",
        "date": "",
    }
    try:
        from mutagen import File as MutagenFile

        audio = MutagenFile(path, easy=True)
        if audio is None:
            return tags
        if audio.tags is None and ext == ".mp3":
            try:
                audio.add_tags()
            except Exception:
                pass
        for key in ("title", "artist", "album", "genre", "tracknumber", "date"):
            val = audio.get(key)
            if val:
                tags[key] = str(val[0] if isinstance(val, list) else val)
    except Exception:
        pass
    if not tags["title"]:
        tags["title"] = os.path.splitext(os.path.basename(path))[0]
    return tags


def write_tags(rel_path: str, updates: dict, settings: Optional[dict] = None) -> dict:
    path = resolve_in_library(rel_path, settings)
    ext = os.path.splitext(path)[1].lower()
    if ext not in AUDIO_EXTS:
        raise ValueError("Keine Audio-Datei")

    from mutagen import File as MutagenFile

    audio = MutagenFile(path, easy=True)
    if audio is None:
        raise ValueError("Tags nicht unterstützt für dieses Format")
    if audio.tags is None:
        audio.add_tags()

    allowed = ("title", "artist", "album", "genre", "tracknumber", "date")
    for key in allowed:
        if key not in updates:
            continue
        val = (updates.get(key) or "").strip()
        if val:
            audio[key] = val
        else:
            try:
                del audio[key]
            except Exception:
                pass
    audio.save()
    return read_tags(rel_path, settings)


def list_subfolders_for_menu(settings: Optional[dict] = None, limit: int = 12) -> list:
    """Unterordner für iDrive-Menü (nur Abspielen, kein Löschen)."""
    root = get_music_root(settings)
    out = []
    try:
        for name in sorted(os.listdir(root), key=str.lower):
            if len(out) >= limit:
                break
            full = os.path.join(root, name)
            if os.path.isdir(full) and not name.startswith("."):
                n = sum(
                    1 for r, _, fs in os.walk(full)
                    for f in fs
                    if os.path.splitext(f)[1].lower() in AUDIO_EXTS
                )
                if n > 0:
                    out.append({"name": name, "path": full, "files": n})
    except Exception:
        pass
    return out
