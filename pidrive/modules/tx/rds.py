"""rds.py — RDS PS/RT aus Now-Playing oder fest, mit Rate-Limit.

- PS (8 Zeichen): fest aus fm_tx.rds.ps; optional Rotation durch den
  Sendernamen (ps_rotate, 8er-Blöcke alle PS_ROTATE_S Sekunden).
- RT (64 Zeichen): rt_mode=fixed → fm_tx.rds.rt;
  rt_mode=auto → „Interpret - Titel“ bzw. „Sender - DLS“ aus /tmp/pidrive_status.json.
- RT-Updates höchstens alle RT_MIN_INTERVAL_S Sekunden (Autoradios zeigen
  sonst flackernden Text, RDS-Gruppe 2A braucht ~4 s für 64 Zeichen).
- Umlaute werden transliteriert (RDS-Zeichensatz ≠ Latin-1, PiFmRds kopiert Bytes).
"""
from __future__ import annotations

import json
import re
import time

STATUS_FILE = "/tmp/pidrive_status.json"
RT_MIN_INTERVAL_S = 10.0
PS_ROTATE_S = 4.0

_TRANSLIT = str.maketrans({
    "ä": "ae", "ö": "oe", "ü": "ue", "Ä": "Ae", "Ö": "Oe", "Ü": "Ue", "ß": "ss",
    "é": "e", "è": "e", "ê": "e", "á": "a", "à": "a", "ó": "o", "ò": "o",
    "–": "-", "—": "-", "„": '"', "“": '"', "”": '"', "’": "'", "‘": "'", "…": "...",
})

_FREQ_SUFFIX = re.compile(r"\s*\(\d{2,3}(?:\.\d+)?\s*MHz\)\s*$")


def rds_ascii(text: str, maxlen: int) -> str:
    t = str(text or "").translate(_TRANSLIT)
    t = t.encode("ascii", "replace").decode("ascii")
    t = re.sub(r"[\x00-\x1f\x7f]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t[:maxlen]


def groups_0a(pi: int, ps: str, pty: int = 0, tp: bool = False, ta: bool = False) -> list[tuple]:
    """PS als 4 Gruppen 0A (Blöcke A–D ohne Checkword; CRC rechnet der Chip).

    Block C = 0xE0CD: „keine AF“ (0xE0 = 0 AFs folgen, 0xCD = Filler).
    """
    ps = rds_ascii(ps, 8).ljust(8)
    out = []
    for seg in range(4):
        di = 1 if seg == 3 else 0
        b = (0 << 12) | (0 << 11) | (int(tp) << 10) | ((pty & 0x1F) << 5) | \
            (int(ta) << 4) | (1 << 3) | (di << 2) | seg
        d = (ord(ps[2 * seg]) << 8) | ord(ps[2 * seg + 1])
        out.append((pi & 0xFFFF, b, 0xE0CD, d))
    return out


def groups_2a(pi: int, rt: str, ab: int = 0, pty: int = 0, tp: bool = False) -> list[tuple]:
    """RT (bis 64 Zeichen) als Gruppen 2A; kürzerer Text endet mit '\\r'."""
    rt = rds_ascii(rt, 64)
    if len(rt) < 64:
        rt += "\r"
    rt = rt.ljust(((len(rt) + 3) // 4) * 4)
    out = []
    for seg in range(len(rt) // 4):
        b = (2 << 12) | (0 << 11) | (int(tp) << 10) | ((pty & 0x1F) << 5) | \
            ((ab & 1) << 4) | seg
        c = (ord(rt[4 * seg]) << 8) | ord(rt[4 * seg + 1])
        d = (ord(rt[4 * seg + 2]) << 8) | ord(rt[4 * seg + 3])
        out.append((pi & 0xFFFF, b, c, d))
    return out


def _station_name(st: dict) -> str:
    name = str(st.get("radio_name") or "")
    for pre in ("FM: ", "DAB: ", "Web: "):
        if name.startswith(pre):
            name = name[len(pre):]
    return _FREQ_SUFFIX.sub("", name).strip()


def now_playing_text(st: dict) -> tuple[str, str]:
    """(sendername_fuer_ps, radiotext) aus dem Core-Status."""
    ctx = str(st.get("control_context") or "idle")
    if ctx in ("radio_dab", "radio_fm", "radio_web") or st.get("radio"):
        name = _station_name(st)
        dls = str(st.get("dls_text") or "").strip()
        if not dls and (st.get("artist") or st.get("track")) and ctx == "radio_web":
            dls = " - ".join(x for x in (st.get("artist"), st.get("track")) if x)
        rt = f"{name} - {dls}" if (name and dls) else (name or dls)
        return name, rt
    if ctx == "library" or st.get("library"):
        return "", str(st.get("lib_track") or st.get("track") or "")
    artist = str(st.get("artist") or "").strip()
    track = str(st.get("track") or "").strip()
    if artist or track:
        return "", " - ".join(x for x in (artist, track) if x)
    return "", ""


def _read_status(path: str = STATUS_FILE) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


class RdsAuto:
    def __init__(self, status_reader=None, clock=time.time,
                 rt_min_interval_s: float = RT_MIN_INTERVAL_S):
        self._status = status_reader or _read_status
        self._clock = clock
        self._min_iv = float(rt_min_interval_s)
        self._last_rt = ""
        self._last_rt_ts = 0.0
        self._ps_idx = 0
        self._ps_ts = 0.0

    def compute(self, cfg: dict, force: bool = False) -> tuple[str, str]:
        rds = (cfg or {}).get("rds") or {}
        now = self._clock()
        base_ps = rds_ascii(rds.get("ps") or "PIDRIVE", 8) or "PIDRIVE"

        name, auto_rt = ("", "")
        if rds.get("rt_mode", "auto") == "auto" or rds.get("ps_rotate"):
            name, auto_rt = now_playing_text(self._status())

        ps = base_ps
        if rds.get("ps_rotate") and name:
            chunks = [base_ps] + [rds_ascii(name, 64)[i:i + 8]
                                  for i in range(0, len(rds_ascii(name, 64)), 8)]
            chunks = [c for c in chunks if c.strip()]
            if now - self._ps_ts >= PS_ROTATE_S:
                self._ps_ts = now
                self._ps_idx = (self._ps_idx + 1) % len(chunks)
            ps = chunks[self._ps_idx % len(chunks)]

        if rds.get("rt_mode", "auto") == "fixed":
            want_rt = rds_ascii(rds.get("rt") or "", 64)
        else:
            want_rt = rds_ascii(auto_rt or rds.get("rt") or "PiDrive", 64)

        if force or (want_rt != self._last_rt and now - self._last_rt_ts >= self._min_iv):
            self._last_rt = want_rt
            self._last_rt_ts = now
        return ps, self._last_rt
