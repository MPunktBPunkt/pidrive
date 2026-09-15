"""
modules/update.py — OTA Update via GitHub
Prüft origin/main, zeigt Diff, spielt nach Bestätigung ein.
"""

from __future__ import annotations

import os
import subprocess
import time
from typing import Callable, Optional

import log
import ipc

REPO_URL = "https://github.com/MPunktBPunkt/pidrive"
REMOTE_VERSION_URL = (
    "https://raw.githubusercontent.com/MPunktBPunkt/pidrive/main/VERSION"
)
BRANCH = "main"


def get_install_dir() -> str:
    """Repo-Wurzel: git-toplevel bevorzugt, sonst ~/pidrive."""
    here = os.path.dirname(os.path.abspath(__file__))  # …/pidrive/modules
    for cand in (
        os.path.abspath(os.path.join(here, "..", "..")),  # repo root
        os.path.abspath(os.path.join(here, "..")),
        os.path.expanduser("~/pidrive"),
    ):
        if os.path.isdir(os.path.join(cand, ".git")):
            return cand
    return os.path.expanduser("~/pidrive")


def _version_file() -> str:
    return os.path.join(get_install_dir(), "VERSION")


def _run(cmd, capture=False, timeout=60, cwd=None):
    try:
        r = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd or get_install_dir(),
        )
        if capture:
            return (r.stdout or "").strip(), r.returncode
        return r.returncode == 0
    except Exception as e:
        log.error(f"Update _run Fehler: {e}")
        return ("", 1) if capture else False


def get_local_version() -> str:
    try:
        return open(_version_file(), encoding="utf-8").read().strip()
    except Exception:
        return "unbekannt"


def get_remote_version() -> Optional[str]:
    """VERSION von GitHub raw (schnell, ohne git)."""
    out, code = _run(
        f"curl -sL --max-time 10 {REMOTE_VERSION_URL}",
        capture=True,
        timeout=15,
    )
    if code != 0 or not out or out.startswith("404"):
        return None
    # raw kann HTML-Fehlerseite sein
    line = out.strip().splitlines()[0].strip()
    if not line or "<" in line or len(line) > 32:
        return None
    return line


def get_local_commit() -> str:
    out, code = _run("git rev-parse --short HEAD", capture=True)
    return out if code == 0 and out else "?"


def check_for_update(fetch: bool = True) -> dict:
    """
    Prüft GitHub (origin/main) auf neuere Commits.

    Returns dict:
      ok, available, local_version, remote_version,
      local_commit, remote_commit, behind, ahead, commits (list of short log lines),
      error (optional)
    """
    root = get_install_dir()
    local_v = get_local_version()
    local_c = get_local_commit()
    result = {
        "ok": True,
        "available": False,
        "local_version": local_v,
        "remote_version": None,
        "local_commit": local_c,
        "remote_commit": None,
        "behind": 0,
        "ahead": 0,
        "commits": [],
        "install_dir": root,
        "branch": BRANCH,
        "error": None,
    }

    if not os.path.isdir(os.path.join(root, ".git")):
        result["ok"] = False
        result["error"] = f"Kein git-Repo unter {root}"
        return result

    if fetch:
        _, fcode = _run(
            f"git fetch --quiet origin {BRANCH}",
            capture=True,
            timeout=90,
        )
        if fcode != 0:
            # Fallback: nur raw VERSION
            remote_v = get_remote_version()
            result["remote_version"] = remote_v
            if remote_v and remote_v != local_v:
                result["available"] = True
            elif not remote_v:
                result["ok"] = False
                result["error"] = "git fetch fehlgeschlagen, GitHub nicht erreichbar"
            return result

    remote_c, rcode = _run(
        f"git rev-parse --short origin/{BRANCH}",
        capture=True,
    )
    if rcode != 0 or not remote_c:
        result["ok"] = False
        result["error"] = f"origin/{BRANCH} nicht gefunden — remote prüfen"
        return result
    result["remote_commit"] = remote_c

    behind_s, _ = _run(
        f"git rev-list --count HEAD..origin/{BRANCH}",
        capture=True,
    )
    ahead_s, _ = _run(
        f"git rev-list --count origin/{BRANCH}..HEAD",
        capture=True,
    )
    try:
        result["behind"] = int(behind_s or "0")
    except ValueError:
        result["behind"] = 0
    try:
        result["ahead"] = int(ahead_s or "0")
    except ValueError:
        result["ahead"] = 0

    if result["behind"] > 0:
        result["available"] = True
        log_out, _ = _run(
            f"git log --oneline HEAD..origin/{BRANCH} | head -15",
            capture=True,
        )
        result["commits"] = [ln for ln in log_out.splitlines() if ln.strip()]

    # Remote-VERSION aus dem fetched Tree (ohne Checkout)
    ver_out, vcode = _run(
        f"git show origin/{BRANCH}:VERSION",
        capture=True,
    )
    if vcode == 0 and ver_out.strip():
        result["remote_version"] = ver_out.strip().splitlines()[0].strip()
    else:
        result["remote_version"] = get_remote_version()

    return result


def apply_update(restart: bool = True) -> dict:
    """
    origin/main einspielen (reset --hard) und optional Services neu starten.
    Runtime-Config unter pidrive/config/ wird gestasht falls dirty.
    """
    root = get_install_dir()
    before = get_local_version()
    before_c = get_local_commit()
    out = {
        "ok": False,
        "before_version": before,
        "after_version": before,
        "before_commit": before_c,
        "after_commit": before_c,
        "error": None,
        "log": "",
    }

    # Config sichern falls lokal geändert
    _run(
        'git stash push -m "pidrivectl-update-config" -- pidrive/config/ 2>/dev/null || true',
        capture=True,
    )

    _, fcode = _run(f"git fetch origin {BRANCH}", capture=True, timeout=90)
    if fcode != 0:
        out["error"] = "git fetch fehlgeschlagen"
        return out

    pull_out, pcode = _run(
        f"git reset --hard origin/{BRANCH}",
        capture=True,
        timeout=60,
    )
    out["log"] = pull_out
    if pcode != 0:
        out["error"] = f"git reset fehlgeschlagen: {pull_out[:200]}"
        return out

    out["after_version"] = get_local_version()
    out["after_commit"] = get_local_commit()
    out["ok"] = True
    log.info(
        f"OTA Update: {before}@{before_c} → {out['after_version']}@{out['after_commit']}"
    )

    if restart:
        _restart_services()
    return out


def _restart_services():
    """Services neu starten — NOPASSWD-Pfade auf dem Pi bevorzugen."""
    for cmd in (
        "sudo -n /bin/systemctl restart pidrive_core",
        "sudo -n /bin/systemctl restart pidrive_web",
        "sudo -n /usr/bin/systemctl restart pidrive_core",
        "sudo -n /usr/bin/systemctl restart pidrive_web",
    ):
        _run(cmd, capture=True, timeout=30)


def do_update():
    """Menü/Trigger-Pfad: prüft und spielt ohne CLI-Prompt ein (Menü hat Confirm)."""
    log.action("OTA Update", "gestartet")
    local_v = get_local_version()
    ipc.write_progress("Update prüfen", f"Lokale Version: {local_v}", color="blue")
    time.sleep(0.8)

    info = check_for_update(fetch=True)
    if not info.get("ok"):
        ipc.write_progress("Fehler", info.get("error") or "Prüfung fehlgeschlagen", color="red")
        log.error(f"OTA Update: {info.get('error')}")
        time.sleep(3)
        ipc.clear_progress()
        return False

    remote_v = info.get("remote_version") or "?"
    ipc.write_progress(
        "Versionen",
        lines=[
            f"Lokal:  {info['local_version']} ({info['local_commit']})",
            f"GitHub: {remote_v} ({info.get('remote_commit') or '?'})",
        ],
    )
    time.sleep(1.2)

    if not info.get("available"):
        ipc.write_progress("Bereits aktuell", f"Version {local_v}", color="green")
        log.info(f"OTA Update: bereits aktuell ({local_v})")
        time.sleep(2.5)
        ipc.clear_progress()
        return False

    ipc.write_progress(
        "Update verfügbar",
        lines=[
            f"{info['local_version']} → {remote_v}",
            f"{info.get('behind', '?')} Commit(s)",
            "Starte Update…",
        ],
        color="orange",
    )
    time.sleep(1.5)

    ipc.write_progress("Update laden", "git fetch + reset origin/main…", color="blue")
    res = apply_update(restart=True)
    if not res.get("ok"):
        ipc.write_progress("Fehlgeschlagen", (res.get("error") or "")[:48], color="red")
        log.error(f"OTA Update: {res.get('error')}")
        time.sleep(4)
        ipc.clear_progress()
        return False

    ipc.write_progress(
        "Update erfolgreich!",
        lines=[
            f"Version {res['after_version']} ({res['after_commit']})",
            "Services neu gestartet",
        ],
        color="green",
    )
    time.sleep(3)
    ipc.clear_progress()
    return True


def check_update_available():
    """Kompatibilität: gibt Remote-VERSION zurück wenn Update da, sonst None."""
    info = check_for_update(fetch=True)
    if info.get("available"):
        return info.get("remote_version") or info.get("remote_commit")
    return None


def run_update(S):
    """Trigger aus dem Menü (nach Confirm-Dialog) — git-basiert, kein Reboot."""
    do_update()


def spotify_toggle(S: dict) -> None:
    """Spotify Connect ein-/ausschalten via systemctl."""
    import subprocess as _sp

    active = bool(S.get("spotify"))

    if active:
        for svc in ("raspotify", "librespot"):
            try:
                _sp.run(["systemctl", "stop", svc], capture_output=True, timeout=5)
            except Exception:
                pass
        S["spotify"] = False
        log.info("[UPDATE] Spotify: gestoppt")
    else:
        started = False
        for svc in ("raspotify", "librespot"):
            try:
                r = _sp.run(["systemctl", "start", svc], capture_output=True, timeout=8)
                if r.returncode == 0:
                    S["spotify"] = True
                    started = True
                    log.info(f"[UPDATE] Spotify: {svc} gestartet")
                    break
            except Exception:
                pass
        if not started:
            log.warn("[UPDATE] Spotify: kein Dienst startbar (raspotify/librespot)")
