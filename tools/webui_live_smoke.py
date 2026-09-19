#!/usr/bin/env python3
"""
webui_live_smoke.py — Simuliert WebUI-Buttons/Felder gegen laufenden Pi.

Scannt aktive Templates auf sendCmd()/fetch(), ruft die HTTP-APIs auf und
prüft kritische Flows (FM-Wechsel, Stop, Audio, Listen, Lists).

Usage:
  python3 tools/webui_live_smoke.py --base http://192.168.178.105:8080
  python3 tools/webui_live_smoke.py --base http://127.0.0.1:8080 --quick
  python3 tools/webui_live_smoke.py --base http://127.0.0.1:8080 --full

Exit: 0 = alles ok / nur WARN; 1 = FAIL vorhanden
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

def _resolve_web_dir() -> Path:
    here = Path(__file__).resolve()
    for c in (
        here.parents[1] / "pidrive" / "web",
        here.parents[2] / "pidrive" / "web" if len(here.parents) > 2 else here.parents[1] / "web",
        here.parents[1] / "web",
    ):
        if (c / "templates").is_dir():
            return c
    return here.parents[1] / "pidrive" / "web"


WEB = _resolve_web_dir()
TEMPLATES = WEB / "templates"
STATIC_JS = WEB / "static" / "js"
REPO = WEB.parent.parent if WEB.parent.name == "pidrive" else WEB.parent

# Gefährlich / langsam — nur mit --full
SKIP_CMDS_DEFAULT = {
    "reboot", "shutdown", "update",
    "bt_forget", "bt_restore",  # pairing-risk
    "dab_scan", "dab_scan_replace", "fm_scan",  # lange RF-Scans
    "rtlsdr_reset",  # stört laufende Wiedergabe stark
}
SKIP_CMD_PREFIXES = (
    "bt_forget:", "bt_repair:", "wifi_connect:",
    "dab_scan_channels:",
)

SENDCMD_RE = re.compile(
    r"""sendCmd\(\s*(?:['\"]([^'\"]+)['\"]|`([^`$]*)`)""",
    re.M,
)
# sendCmd('play_fm:' + f) / sendCmd("vol_set:"+v)
SENDCMD_DYN_RE = re.compile(
    r"""sendCmd\(\s*['\"]([a-z0-9_]+:)['\"]\s*\+""",
    re.I,
)
FETCH_RE = re.compile(
    r"""fetch\(\s*[`'\"](/[^`'\"?]*)""",
    re.M,
)


@dataclass
class Result:
    name: str
    status: str  # PASS WARN FAIL SKIP
    detail: str = ""
    ms: float = 0.0
    before: Optional[dict] = None
    after: Optional[dict] = None


@dataclass
class Report:
    results: List[Result] = field(default_factory=list)
    timeline: List[dict] = field(default_factory=list)

    def add(self, r: Result):
        self.results.append(r)
        mark = {"PASS": "✓", "WARN": "!", "FAIL": "✗", "SKIP": "·"}.get(r.status, "?")
        line = f"  {mark} [{r.status}] {r.name}"
        if r.detail:
            line += f" — {r.detail}"
        print(line, flush=True)

    def note_state(self, label: str, snap: dict, ms: float = 0.0):
        row = {"t": time.strftime("%H:%M:%S"), "label": label, "ms": round(ms, 1), **snap}
        self.timeline.append(row)
        tr = " TRANS" if snap.get("transition") else ""
        own = f" owner={snap.get('owner')}" if snap.get("owner") else ""
        print(
            f"    ◆ {label}: src={snap.get('source')!r} type={snap.get('type')!r} "
            f"name={str(snap.get('name') or '')[:40]!r} playing={snap.get('playing')!r} "
            f"dab={snap.get('dab_state')!r} audio={snap.get('audio')!r}{tr}{own}"
            + (f"  [{ms:.0f}ms]" if ms else ""),
            flush=True,
        )

    def summary(self) -> Dict[str, int]:
        c: Dict[str, int] = {}
        for r in self.results:
            c[r.status] = c.get(r.status, 0) + 1
        return c


def http_json(
    base: str,
    path: str,
    method: str = "GET",
    body: Optional[dict] = None,
    timeout: float = 12.0,
) -> Tuple[int, Any, float]:
    url = base.rstrip("/") + path
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            code = resp.getcode()
            try:
                return code, json.loads(raw.decode("utf-8", errors="replace")), (time.time() - t0) * 1000
            except Exception:
                return code, raw[:200], (time.time() - t0) * 1000
    except urllib.error.HTTPError as e:
        raw = e.read() if hasattr(e, "read") else b""
        try:
            j = json.loads(raw.decode("utf-8", errors="replace"))
        except Exception:
            j = {"error": str(e), "body": raw[:200].decode("utf-8", errors="replace")}
        return e.code, j, (time.time() - t0) * 1000
    except Exception as e:
        return 0, {"error": str(e)}, (time.time() - t0) * 1000


def iter_template_sources() -> List[Tuple[Path, str]]:
    out = []
    for root in (TEMPLATES, STATIC_JS):
        if not root.exists():
            continue
        for p in root.rglob("*"):
            if p.suffix.lower() not in (".html", ".js"):
                continue
            if "legacy" in p.parts or "legacy" in p.name or p.name == "index_full.html":
                continue
            out.append((p, p.read_text(encoding="utf-8", errors="replace")))
    return out


def discover() -> Tuple[Set[str], Set[str], Set[str], Set[str]]:
    """Literale cmds, dynamische Prefixes, fetch paths, HTML pages."""
    cmds: Set[str] = set()
    dyn: Set[str] = set()
    fetches: Set[str] = set()
    pages: Set[str] = set()
    for path, text in iter_template_sources():
        if path.suffix == ".html" and path.parent == TEMPLATES:
            # route guess: index.html → /
            name = path.stem
            if name == "index":
                pages.add("/")
            elif name == "base":
                pass
            else:
                pages.add("/" + name.replace("_", "-"))
                pages.add("/" + name)
        for m in SENDCMD_RE.finditer(text):
            cmd = (m.group(1) or m.group(2) or "").strip()
            if cmd and "${" not in cmd and "+" not in cmd:
                cmds.add(cmd)
        for m in SENDCMD_DYN_RE.finditer(text):
            dyn.add(m.group(1))
        for m in FETCH_RE.finditer(text):
            url = m.group(1)
            if not url.startswith("/static/"):
                fetches.add(url.split("?", 1)[0])
    return cmds, dyn, fetches, pages


def cmd_should_skip(cmd: str, full: bool) -> bool:
    if full:
        return cmd in ("reboot", "shutdown")  # immer skip hard kill
    if cmd in SKIP_CMDS_DEFAULT:
        return True
    return any(cmd.startswith(p) for p in SKIP_CMD_PREFIXES)


def get_core(base: str) -> dict:
    code, j, _ = http_json(base, "/api/core")
    if code != 200 or not isinstance(j, dict):
        return {}
    return j


def radio_snapshot(base: str) -> dict:
    j = get_core(base)
    st = j.get("status") or {}
    ss = j.get("source_state") or {}
    return {
        "source": ss.get("source_current") or st.get("radio_type") or "",
        "name": st.get("radio_name") or "",
        "station": st.get("radio_station") or "",
        "playing": st.get("radio_playing"),
        "type": st.get("radio_type") or "",
        "dab_state": st.get("dab_playback_state") or ss.get("dab_playback_state") or "",
        "audio": st.get("audio_effective") or "",
        "transition": bool(ss.get("transition")),
        "owner": ss.get("owner") or "",
    }


def wait_source(base: str, want: str, timeout: float = 8.0,
                name_substr: str = "") -> dict:
    t0 = time.time()
    last = {}
    want_l = (want or "").lower()
    needle = (name_substr or "").lower()
    while time.time() - t0 < timeout:
        last = radio_snapshot(base)
        src = (last.get("source") or "").lower()
        typ = (last.get("type") or "").lower()
        name = str(last.get("station") or last.get("name") or "").lower()
        if want_l == "idle" and src in ("idle", "") and not last.get("playing") and not last.get("transition"):
            return last
        src_ok = want_l in src or want_l in typ or (want_l == "fm" and ("fm" in src or typ == "fm"))
        src_ok = src_ok or (want_l in ("web", "webradio") and ("web" in src or "webradio" in src))
        if src_ok:
            if not needle or needle in name:
                return last
        time.sleep(0.2)
    return last


def wait_idle(base: str, timeout: float = 10.0) -> dict:
    """radio_stop + poll until idle (kein Transition-Hang)."""
    post_cmd(base, "radio_stop")
    return wait_source(base, "idle", timeout)


def post_cmd(base: str, cmd: str) -> Tuple[bool, Any, float]:
    code, j, ms = http_json(base, "/api/cmd", method="POST", body={"cmd": cmd})
    ok = code == 200 and isinstance(j, dict) and j.get("ok") is True
    return ok, j, ms


# onclick="fn(${JSON.stringify(...)})" zerbricht HTML-Attribute (Attr endet bei erstem ")
BROKEN_ONCLICK_RE = re.compile(
    r"""onclick\s*=\s*"([^"]*\$\{JSON\.stringify|[^"]*[a-zA-Z]+\(\s*")""",
    re.I,
)
DEAD_HANDLER_RE = re.compile(
    r"""(?:onclick|oninput|onchange)\s*=\s*["']([^"']+)["']""",
    re.I,
)


def main() -> int:
    ap = argparse.ArgumentParser(description="PiDrive WebUI Live Smoke")
    ap.add_argument("--base", default=os.environ.get("PIDRIVE_WEB", "http://127.0.0.1:8080"))
    ap.add_argument("--quick", action="store_true", help="Nur Seiten+Lists+FM-Kern")
    ap.add_argument("--full", action="store_true", help="Auch lange/riskante Cmds (ohne reboot)")
    ap.add_argument("--json-out", default="", help="Report als JSON schreiben")
    args = ap.parse_args()
    base = args.base.rstrip("/")
    rep = Report()

    print(f"\n=== WebUI Live Smoke → {base} ===\n")

    # ── 0) Erreichbarkeit ────────────────────────────────────────────────
    code, j, ms = http_json(base, "/api/core", timeout=5)
    if code != 200:
        rep.add(Result("api/core reachable", "FAIL", f"HTTP {code} {j}", ms))
        _finish(rep, args.json_out)
        return 1
    rep.add(Result("api/core reachable", "PASS", f"{ms:.0f}ms", ms))

    cmds, dyn, fetches, pages = discover()
    print(f"Discovered: {len(cmds)} literal cmds, {len(dyn)} dyn prefixes, "
          f"{len(fetches)} fetches, ~{len(pages)} pages\n")

    # ── 0b) Tote/kaputte onclick-Handler in Templates ─────────────────────
    print("-- Dead / broken UI handlers --")
    broken = []
    known_globals = {
        "sendCmd", "showToast", "switchTab", "playFM", "playFMStation", "playDAB",
        "playDABStation", "playWeb", "playFav", "playFavByIdx", "prevStation",
        "nextStation", "activateSource", "showFMInput", "hideStations", "scanFm",
        "loadFavorites", "loadPlaylist", "toggleMute", "onVolSliderInput",
        "onVolSliderCommit", "PiDriveAPI",
    }
    for path, text in iter_template_sources():
        if path.suffix not in (".html", ".js"):
            continue
        for m in re.finditer(
            r"""onclick\s*=\s*"([^"]*\$\{JSON\.stringify[^"]*)""" , text
        ):
            broken.append(f"{path.name}: broken JSON.stringify in double-quoted onclick")
        # Doppelte Quotes in onclick="fn("...")"
        for m in re.finditer(r'''onclick\s*=\s*"([A-Za-z_]\w*)\(\s*"''', text):
            broken.append(f"{path.name}: onclick quotes break attr ({m.group(1)})")
        # Merken/loadFavs Tippfehler etc.
        if "loadFavs" in text and "function loadFavs" not in text and "loadFavs =" not in text:
            if "setTimeout(loadFavs" in text or "onclick=\"loadFavs" in text:
                broken.append(f"{path.name}: loadFavs() referenced but undefined")
    if broken:
        for b in broken[:12]:
            rep.add(Result("ui handler", "FAIL", b))
    else:
        rep.add(Result("ui handlers onclick", "PASS", "no broken JSON.stringify/onclick quotes"))

    # ── 1) HTML-Seiten laden ─────────────────────────────────────────────
    print("-- Pages --")
    page_list = sorted(pages | {"/", "/audio", "/rf-tools", "/diagnostics", "/avrcp",
                                 "/webradio-admin", "/music-admin"})
    if args.quick:
        page_list = ["/", "/audio", "/rf-tools"]
    for pg in page_list:
        code, body, ms = http_json(base, pg, timeout=8)
        # HTML oft kein JSON
        if code == 0:
            rep.add(Result(f"GET {pg}", "FAIL", str(body), ms))
        elif code >= 400:
            # Versuch ohne json
            try:
                req = urllib.request.Request(base + pg)
                with urllib.request.urlopen(req, timeout=8) as resp:
                    raw = resp.read(200)
                    rep.add(Result(f"GET {pg}", "PASS" if resp.getcode() < 400 else "FAIL",
                                   f"HTTP {resp.getcode()} {raw[:40]!r}", ms))
            except urllib.error.HTTPError as e:
                rep.add(Result(f"GET {pg}", "FAIL", f"HTTP {e.code}", ms))
            except Exception as e:
                rep.add(Result(f"GET {pg}", "FAIL", str(e), ms))
        else:
            rep.add(Result(f"GET {pg}", "PASS", f"HTTP {code}", ms))

    # ── 2) GET APIs aus Templates ────────────────────────────────────────
    print("\n-- GET APIs --")
    get_paths = sorted(fetches | {
        "/api/core", "/api/lists", "/api/audio", "/api/audio/listen/status",
        "/api/gain", "/api/volume", "/api/rtlsdr", "/api/dab/status",
        "/api/playlist", "/api/runtime",
    })
    if args.quick:
        get_paths = [p for p in get_paths if p in (
            "/api/core", "/api/lists", "/api/audio", "/api/audio/listen/status",
            "/api/gain", "/api/rtlsdr",
        )]
    for path in get_paths:
        if path.startswith("/api/cmd"):
            continue
        # Endpoints die Pflicht-Query brauchen — nicht blind GETten
        if path.rstrip("/").endswith(("/tags", "/download", "/validate")) or \
           path in ("/api/music/tags", "/api/spectrum/capture"):
            rep.add(Result(f"GET {path}", "SKIP", "needs params"))
            continue
        code, j, ms = http_json(base, path, timeout=12)
        if code == 200:
            rep.add(Result(f"GET {path}", "PASS", f"{ms:.0f}ms", ms))
        elif code in (400, 404, 405):
            rep.add(Result(f"GET {path}", "WARN", f"HTTP {code}", ms))
        elif code == 503 and "listen" in path:
            rep.add(Result(f"GET {path}", "WARN", f"HTTP 503 {j}", ms))
        else:
            rep.add(Result(f"GET {path}", "FAIL", f"HTTP {code} {j}", ms))

    # ── 3) Literal sendCmd (Allowlist / akzeptiert) ──────────────────────
    print("\n-- sendCmd literals (accept) --")
    # Sichere Read-only / togglige
    safe_first = [
        "vol_up", "vol_down", "audio_klinke",
    ]
    tested_cmds: Set[str] = set()
    for cmd in safe_first:
        if cmd in cmds or True:
            ok, j, ms = post_cmd(base, cmd)
            tested_cmds.add(cmd)
            rep.add(Result(f"CMD {cmd}", "PASS" if ok else "FAIL",
                           "" if ok else str(j), ms))

    for cmd in sorted(cmds):
        if cmd in tested_cmds:
            continue
        if cmd_should_skip(cmd, args.full):
            rep.add(Result(f"CMD {cmd}", "SKIP", "risky/slow"))
            continue
        # Nur Prefix ohne Wert (z.B. play_fm:) — echte Werte kommen aus dyn/flows
        if cmd.endswith(":"):
            rep.add(Result(f"CMD {cmd}", "SKIP", "prefix only"))
            continue
        if args.quick and cmd not in ("radio_stop", "vol_up", "vol_down", "audio_klinke",
                                       "fm_next", "fm_prev", "spotify_toggle"):
            continue
        # Vor Flows keine Play/Spotify-Starts (Race mit SM-Checks)
        if not args.quick and (
            cmd.startswith(("play_", "favorites_play")) or cmd in ("spotify_toggle", "play_spotify")
        ):
            rep.add(Result(f"CMD {cmd}", "SKIP", "covered by flows"))
            continue
        ok, j, ms = post_cmd(base, cmd)
        tested_cmds.add(cmd)
        if ok:
            rep.add(Result(f"CMD {cmd}", "PASS", f"{ms:.0f}ms", ms))
        else:
            err = (j or {}).get("error", j) if isinstance(j, dict) else j
            # „nicht erlaubt“ = echte Lücke
            if isinstance(err, str) and "nicht erlaubt" in err:
                rep.add(Result(f"CMD {cmd}", "FAIL", err, ms))
            else:
                rep.add(Result(f"CMD {cmd}", "WARN", str(err), ms))
        time.sleep(0.15)

    # Dynamische Prefixes: mit Beispielwert
    print("\n-- sendCmd dynamic prefixes --")
    dyn_examples = {
        "play_fm:": None,  # from lists
        "play_dab:": None,
        "play_web:": None,
        "vol_set:": "50",
        "ppm:": "49",
        "fm_gain:": "30",
        "set_scanner_squelch:": "25",
        "scan_setfreq:": "fm:98.5",
        "scan_setch:": "pmr446:1",
        "favorites_play:": "1",
    }
    code, lists, _ = http_json(base, "/api/lists")
    if code == 200 and isinstance(lists, dict):
        fm = (lists.get("fm_stations") or [])
        dab = (lists.get("dab_stations") or [])
        web = (lists.get("web_stations") or [])
        if fm:
            freq = fm[0].get("freq_mhz") or fm[0].get("freq")
            dyn_examples["play_fm:"] = str(freq)
        if dab:
            dyn_examples["play_dab:"] = str(dab[0].get("service_id") or dab[0].get("name"))
        if web:
            dyn_examples["play_web:"] = str(web[0].get("name") or web[0].get("id"))
        rep.add(Result("api/lists content", "PASS",
                       f"fm={len(fm)} dab={len(dab)} web={len(web)} fav={len(lists.get('favorites') or [])}"))
    else:
        rep.add(Result("api/lists content", "FAIL", str(lists)))

    # Play-Cmds: Accept nur prüfen wenn --quick; sonst Flows (kein Race)
    PLAY_PREFIXES = ("play_fm:", "play_dab:", "play_web:", "favorites_play:")
    for prefix in sorted(dyn | set(dyn_examples)):
        if args.quick and prefix not in ("play_fm:", "vol_set:", "play_dab:"):
            continue
        ex = dyn_examples.get(prefix)
        if ex is None:
            rep.add(Result(f"CMD {prefix}*", "SKIP", "kein Beispiel"))
            continue
        cmd = prefix + str(ex)
        if cmd_should_skip(cmd, args.full):
            rep.add(Result(f"CMD {cmd}", "SKIP", "risky"))
            continue
        if any(cmd.startswith(p) for p in PLAY_PREFIXES) and not args.quick:
            rep.add(Result(f"CMD {cmd}", "SKIP", "covered by flows"))
            continue
        ok, j, ms = post_cmd(base, cmd)
        if ok:
            rep.add(Result(f"CMD {cmd}", "PASS", f"{ms:.0f}ms", ms))
        else:
            err = (j or {}).get("error", j) if isinstance(j, dict) else j
            st = "FAIL" if (isinstance(err, str) and "nicht erlaubt" in err) else "WARN"
            rep.add(Result(f"CMD {cmd}", st, str(err), ms))
        time.sleep(0.15)

    # Vor Flows: hart idle (auch nach spotify_toggle etc.)
    if not args.quick:
        print("\n-- settle idle before flows --", flush=True)
        post_cmd(base, "radio_stop")
        time.sleep(0.8)
        snap = wait_idle(base, 12)
        idle_ok = (snap.get("source") or "idle").lower() in ("idle", "") and not snap.get("transition")
        rep.add(Result("settle idle", "PASS" if idle_ok else "WARN", str(snap)))
        time.sleep(0.3)

    if args.quick:
        _finish(rep, args.json_out)
        return 0 if rep.summary().get("FAIL", 0) == 0 else 1

    # ── 4) Kritische Flows (+ State-Machine Timeline) ────────────────────
    print("\n-- Flows (state machine + timings) --", flush=True)

    def flow_cmd(label: str, cmd: str, settle: float = 0.0) -> Tuple[bool, dict, float]:
        before = radio_snapshot(base)
        rep.note_state(f"{label} BEFORE", before)
        t0 = time.time()
        ok, j, http_ms = post_cmd(base, cmd)
        if settle:
            time.sleep(settle)
        after = radio_snapshot(base)
        elapsed_ms = (time.time() - t0) * 1000
        rep.note_state(f"{label} AFTER", after, elapsed_ms)
        return ok, after, elapsed_ms

    # 4a Audio klinke
    ok, snap, ms = flow_cmd("audio_klinke", "audio_klinke", 0.8)
    if (snap.get("audio") or "").lower() in ("klinke", "auto", ""):
        rep.add(Result("flow audio_klinke", "PASS", f"audio={snap.get('audio')!r}", ms))
    else:
        rep.add(Result("flow audio_klinke", "WARN", f"audio={snap.get('audio')!r}", ms))

    # 4b FM play + switch (wie Listen-Klick)
    freqs = []
    if isinstance(lists, dict):
        for s in (lists.get("fm_stations") or [])[:4]:
            f = s.get("freq_mhz") or s.get("freq")
            if f is not None:
                freqs.append((str(f), s.get("name") or str(f)))
    if len(freqs) < 2:
        freqs = [("98.5", "FM 98.5"), ("104.4", "Antenne"), ("101.8", "Radio 7")]

    wait_idle(base, 8)
    f0, n0 = freqs[0]
    t0 = time.time()
    ok, _, http_ms = post_cmd(base, f"play_fm:{f0}")
    snap = wait_source(base, "fm", 8, name_substr=f0.split(".")[0])
    ms = (time.time() - t0) * 1000
    rep.note_state(f"play_fm:{f0}", snap, ms)
    freq_ok = f0.split(".")[0] in str(snap.get("station") or snap.get("name") or "")
    if ok and ("fm" in (snap.get("source") or "").lower() or (snap.get("type") or "").upper() == "FM"):
        rep.add(Result("flow play_fm first", "PASS" if freq_ok else "WARN",
                       f"{snap.get('station') or snap.get('name')} src={snap.get('source')} {ms:.0f}ms", ms))
    else:
        rep.add(Result("flow play_fm first", "FAIL", f"ok={ok} snap={snap}", ms))

    # Switch to second
    f1, n1 = freqs[1]
    t0 = time.time()
    ok, _, _ = post_cmd(base, f"play_fm:{f1}")
    snap = wait_source(base, "fm", 6, name_substr=f1.split(".")[0])
    ms = (time.time() - t0) * 1000
    rep.note_state(f"play_fm:{f1} switch", snap, ms)
    st = str(snap.get("station") or snap.get("name") or "")
    switched = f1.split(".")[0] in st or (n1 and n1[:6].lower() in st.lower())
    if ok and switched:
        rep.add(Result("flow play_fm switch", "PASS", f"{st} in {ms:.0f}ms", ms))
    else:
        rep.add(Result("flow play_fm switch", "FAIL", f"want {f1}/{n1} got {st!r}", ms))

    # fm_next
    t0 = time.time()
    ok, _, _ = post_cmd(base, "fm_next")
    time.sleep(1.2)
    snap2 = radio_snapshot(base)
    ms = (time.time() - t0) * 1000
    rep.note_state("fm_next", snap2, ms)
    if ok and (snap2.get("station") or snap2.get("name")):
        rep.add(Result("flow fm_next", "PASS", str(snap2.get("station") or snap2.get("name")), ms))
    else:
        rep.add(Result("flow fm_next", "WARN", f"ok={ok} {snap2}", ms))

    # 4c Stop
    t0 = time.time()
    ok, _, _ = post_cmd(base, "radio_stop")
    snap = wait_source(base, "idle", 6)
    ms = (time.time() - t0) * 1000
    rep.note_state("radio_stop", snap, ms)
    idle = (snap.get("source") or "idle").lower() in ("idle", "")
    if ok and idle and not snap.get("transition"):
        rep.add(Result("flow radio_stop", "PASS", f"{ms:.0f}ms", ms))
    else:
        rep.add(Result("flow radio_stop", "FAIL", f"ok={ok} snap={snap}", ms))

    # 4d DAB start + stop (kurz, kein Sync erwartet indoor)
    dab_q = dyn_examples.get("play_dab:")
    if dab_q:
        t0 = time.time()
        ok, _, _ = post_cmd(base, f"play_dab:{dab_q}")
        snap = wait_source(base, "dab", 5)
        ms = (time.time() - t0) * 1000
        rep.note_state(f"play_dab:{dab_q}", snap, ms)
        if ok and "dab" in (snap.get("source") or "").lower():
            rep.add(Result("flow play_dab commit", "PASS",
                           f"src={snap.get('source')} dab_state={snap.get('dab_state')} {ms:.0f}ms", ms))
        else:
            rep.add(Result("flow play_dab commit", "FAIL", f"ok={ok} {snap}", ms))
        time.sleep(0.5)
        t0 = time.time()
        post_cmd(base, "radio_stop")
        while time.time() - t0 < 5:
            snap = radio_snapshot(base)
            if not snap.get("transition") and (snap.get("source") or "idle").lower() in ("idle", ""):
                break
            time.sleep(0.2)
        elapsed = time.time() - t0
        snap = radio_snapshot(base)
        rep.note_state("dab→stop", snap, elapsed * 1000)
        if elapsed < 5 and (snap.get("source") or "idle").lower() in ("idle", "") and not snap.get("transition"):
            rep.add(Result("flow dab→stop fast", "PASS", f"{elapsed:.1f}s", elapsed * 1000))
        else:
            rep.add(Result("flow dab→stop fast", "FAIL", f"{elapsed:.1f}s snap={snap}", elapsed * 1000))

        # 4e DAB→FM switch (der frühere Hang)
        post_cmd(base, f"play_dab:{dab_q}")
        snap = wait_source(base, "dab", 4)
        rep.note_state("pre dab→fm", snap)
        t0 = time.time()
        post_cmd(base, f"play_fm:{freqs[0][0]}")
        snap = wait_source(base, "fm", 8)
        elapsed = time.time() - t0
        rep.note_state("dab→fm", snap, elapsed * 1000)
        if "fm" in (snap.get("source") or "").lower() or (snap.get("type") or "").upper() == "FM":
            rep.add(Result("flow dab→fm switch", "PASS",
                           f"{elapsed:.1f}s {snap.get('station')}", elapsed * 1000))
        else:
            rep.add(Result("flow dab→fm switch", "FAIL", f"{elapsed:.1f}s {snap}", elapsed * 1000))
    else:
        rep.add(Result("flow play_dab", "SKIP", "keine DAB-Sender"))

    # 4f Webradio
    web_q = dyn_examples.get("play_web:")
    if web_q:
        wait_idle(base, 6)
        t0 = time.time()
        ok, _, _ = post_cmd(base, f"play_web:{web_q}")
        snap = wait_source(base, "web", 5)
        ms = (time.time() - t0) * 1000
        rep.note_state(f"play_web:{web_q[:30]}", snap, ms)
        src = (snap.get("source") or "").lower()
        if ok and ("web" in src or "webradio" in src):
            rep.add(Result("flow play_web", "PASS",
                           f"{snap.get('name') or snap.get('station')} {ms:.0f}ms", ms))
        else:
            rep.add(Result("flow play_web", "WARN", f"ok={ok} {snap}", ms))
        wait_idle(base, 5)
    else:
        rep.add(Result("flow play_web", "SKIP", "keine Webradio-Sender"))

    # 4g Monitor listen
    post_cmd(base, f"play_fm:{freqs[0][0]}")
    wait_source(base, "fm", 5)
    rep.note_state("pre-listen", radio_snapshot(base))
    code, st, _ = http_json(base, "/api/audio/listen/status")
    if code == 200 and isinstance(st, dict) and st.get("ok"):
        try:
            t0 = time.time()
            req = urllib.request.Request(base + "/api/audio/listen")
            with urllib.request.urlopen(req, timeout=6) as resp:
                chunk = resp.read(16384)
            ms = (time.time() - t0) * 1000
            if len(chunk) > 1000 and (chunk[:3] == b"ID3" or chunk[:2] == b"\xff\xfb" or len(chunk) > 4000):
                rep.add(Result("flow audio/listen stream", "PASS", f"{len(chunk)} bytes", ms))
            else:
                rep.add(Result("flow audio/listen stream", "WARN",
                               f"{len(chunk)} bytes head={chunk[:8]!r}", ms))
        except Exception as e:
            rep.add(Result("flow audio/listen stream", "FAIL", str(e)))
    else:
        rep.add(Result("flow audio/listen status", "WARN", f"{code} {st}"))

    flow_cmd("final stop", "radio_stop", 1.0)

    # 4h Spectrum capture (kurz, kann busy sein)
    if not args.quick:
        code, j, ms = http_json(
            base,
            "/api/spectrum/capture?mode=center&center_mhz=98.5&span_mhz=1&rate=1024000"
            "&samples=8192&avg_frames=1&ppm=49&gain=30",
            method="POST",
            timeout=45,
        )
        if code == 200 and isinstance(j, dict) and (j.get("ok") or j.get("freqs") or j.get("data")):
            rep.add(Result("flow spectrum capture", "PASS", f"{ms:.0f}ms", ms))
        elif code in (409, 503) or (isinstance(j, dict) and "busy" in str(j).lower()):
            rep.add(Result("flow spectrum capture", "WARN", f"{code} {j}", ms))
        else:
            rep.add(Result("flow spectrum capture", "WARN", f"{code} {j}", ms))

    _finish(rep, args.json_out)
    fails = rep.summary().get("FAIL", 0)
    return 1 if fails else 0


def _finish(rep: Report, json_out: str):
    s = rep.summary()
    print("\n=== Summary ===", flush=True)
    print(f"  PASS={s.get('PASS', 0)}  WARN={s.get('WARN', 0)}  "
          f"FAIL={s.get('FAIL', 0)}  SKIP={s.get('SKIP', 0)}", flush=True)
    fails = [r for r in rep.results if r.status == "FAIL"]
    if fails:
        print("\nFailures:", flush=True)
        for r in fails:
            print(f"  ✗ {r.name}: {r.detail}", flush=True)
    if rep.timeline:
        print("\n=== State-Machine Timeline ===", flush=True)
        for row in rep.timeline:
            print(
                f"  {row.get('t')}  {row.get('label'):28}  "
                f"src={row.get('source')} type={row.get('type')} "
                f"playing={row.get('playing')} dab={row.get('dab_state')} "
                f"tr={row.get('transition')}  {row.get('ms')}ms",
                flush=True,
            )
    if json_out:
        Path(json_out).write_text(
            json.dumps(
                {
                    "summary": s,
                    "results": [
                        {"name": r.name, "status": r.status, "detail": r.detail, "ms": r.ms}
                        for r in rep.results
                    ],
                    "timeline": rep.timeline,
                },
                indent=2, ensure_ascii=False,
            ) + "\n",
            encoding="utf-8",
        )
        print(f"\nWrote {json_out}", flush=True)


if __name__ == "__main__":
    sys.exit(main())
