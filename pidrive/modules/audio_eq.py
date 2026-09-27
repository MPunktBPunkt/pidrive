#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""audio_eq.py — Tone-Presets + leichte Rauschunterdrückung für mpv (lavfi).

Stufe 1: Bass/Mitten/Höhen (−6…+6 dB), Presets, NR-Schalter (afftdn).
Wirkt über ``--af=lavfi=[…]`` beim nächsten mpv-Start (FM/DAB/Web/Scanner).
"""

from __future__ import annotations

from typing import Any

# Soft limits — vermeidet Clipping / „Telefon“-Effekt
EQ_MIN = -6
EQ_MAX = 6

PRESETS: dict[str, dict[str, Any]] = {
    "flat": {
        "label": "Flat",
        "bass": 0,
        "mid": 0,
        "treble": 0,
        "nr": False,
    },
    "bass+": {
        "label": "Bass+",
        "bass": 4,
        "mid": 0,
        "treble": -1,
        "nr": False,
    },
    "voice": {
        "label": "Voice",
        "bass": -2,
        "mid": 3,
        "treble": 1,
        "nr": True,
    },
    "airband": {
        "label": "Airband",
        "bass": -3,
        "mid": 2,
        "treble": -1,
        "nr": True,
    },
    "noisy-fm": {
        "label": "Noisy FM",
        "bass": 1,
        "mid": 0,
        "treble": -3,
        "nr": True,
    },
}


def _clamp_db(v: Any, default: int = 0) -> int:
    try:
        n = int(round(float(v)))
    except (TypeError, ValueError):
        n = default
    return max(EQ_MIN, min(EQ_MAX, n))


def get_state(settings: dict | None) -> dict:
    """Aktueller EQ/NR-Zustand aus settings (Defaults gemerged)."""
    s = settings or {}
    preset = str(s.get("audio_eq_preset") or "flat").strip().lower()
    if preset not in PRESETS:
        preset = "flat"
    return {
        "preset": preset,
        "label": PRESETS[preset]["label"],
        "bass": _clamp_db(s.get("audio_eq_bass", PRESETS[preset]["bass"])),
        "mid": _clamp_db(s.get("audio_eq_mid", PRESETS[preset]["mid"])),
        "treble": _clamp_db(s.get("audio_eq_treble", PRESETS[preset]["treble"])),
        "nr": bool(s.get("audio_nr", PRESETS[preset]["nr"])),
        "presets": [
            {"id": k, "label": v["label"], "nr": bool(v["nr"])}
            for k, v in PRESETS.items()
        ],
    }


def apply_preset(settings: dict, name: str) -> dict:
    """Preset in settings schreiben; gibt neuen State zurück."""
    key = str(name or "flat").strip().lower()
    if key not in PRESETS:
        raise ValueError(f"unbekanntes Preset: {name!r} (bekannt: {', '.join(PRESETS)})")
    p = PRESETS[key]
    settings["audio_eq_preset"] = key
    settings["audio_eq_bass"] = int(p["bass"])
    settings["audio_eq_mid"] = int(p["mid"])
    settings["audio_eq_treble"] = int(p["treble"])
    settings["audio_nr"] = bool(p["nr"])
    return get_state(settings)


def set_bands(
    settings: dict,
    *,
    bass: int | None = None,
    mid: int | None = None,
    treble: int | None = None,
    nr: bool | None = None,
    preset: str | None = "custom",
) -> dict:
    """Einzelne Bänder / NR setzen. preset=custom wenn manuell."""
    if bass is not None:
        settings["audio_eq_bass"] = _clamp_db(bass)
    if mid is not None:
        settings["audio_eq_mid"] = _clamp_db(mid)
    if treble is not None:
        settings["audio_eq_treble"] = _clamp_db(treble)
    if nr is not None:
        settings["audio_nr"] = bool(nr)
    if preset is not None:
        settings["audio_eq_preset"] = str(preset)
    return get_state(settings)


def set_nr(settings: dict, enabled: bool) -> dict:
    settings["audio_nr"] = bool(enabled)
    # Preset-Name behalten, aber als „angepasst“ markieren wenn NR vom Preset abweicht
    st = get_state(settings)
    p = PRESETS.get(st["preset"], PRESETS["flat"])
    if bool(p["nr"]) != bool(enabled):
        settings["audio_eq_preset"] = "custom"
    return get_state(settings)


def build_eq_filters(settings: dict | None, *, source: str = "") -> list[str]:
    """Libavfilter-Teile für Tone + optional NR (ohne umschließendes lavfi=)."""
    st = get_state(settings)
    filters: list[str] = []
    if st["bass"]:
        filters.append(f"bass=g={st['bass']}")
    if st["treble"]:
        filters.append(f"treble=g={st['treble']}")
    if st["mid"]:
        # Mitten-Peak ~1 kHz, breit genug für Sprache/Musik
        filters.append(f"equalizer=f=1000:t=h:w=800:g={st['mid']}")
    if st["nr"]:
        # Leichte spektrale Rauschunterdrückung — gut für Sprache/schwaches FM.
        # Bei Musik-Presets ohne NR bleibt die Kette unberührt.
        src = (source or "").lower()
        if "air" in src or "scan" in src or "voice" in st["preset"]:
            filters.append("afftdn=nr=12:nf=-45")
        else:
            filters.append("afftdn=nr=8:nf=-50")
    return filters


def compose_lavfi(*parts: list[str] | str | None) -> str | None:
    """Mehrere Filterlisten zu ``lavfi=[a,b,…]`` zusammenfügen."""
    flat: list[str] = []
    for p in parts:
        if not p:
            continue
        if isinstance(p, str):
            s = p.strip()
            if s.startswith("lavfi=["):
                s = s[len("lavfi=[") :]
                if s.endswith("]"):
                    s = s[:-1]
            if s:
                flat.extend(x.strip() for x in s.split(",") if x.strip())
        else:
            flat.extend(x for x in p if x)
    if not flat:
        return None
    return "lavfi=[" + ",".join(flat) + "]"


def mpv_af_arg(settings: dict | None, *, source: str = "", base: list[str] | str | None = None) -> str | None:
    """Vollständiges ``--af=…``-Argument oder None wenn nichts zu tun."""
    chain = compose_lavfi(base, build_eq_filters(settings, source=source))
    if not chain:
        return None
    return f"--af={chain}"


def ensure_af_on_args(
    args: list,
    settings: dict | None,
    *,
    source: str = "",
    base: list[str] | str | None = None,
) -> list:
    """``--af=`` in mpv-Args setzen/ersetzen (EQ + optional Basisfilter)."""
    out = [a for a in args if not (isinstance(a, str) and a.startswith("--af="))]
    af = mpv_af_arg(settings, source=source, base=base)
    if af:
        out.append(af)
    return out


def restart_current_playback(S: dict, settings: dict | None = None, *, reason: str = "eq") -> str:
    """Aktuelle FM/DAB/Web/Scanner-Quelle neu starten, damit ``--af=`` greift.

    Liest Settings frisch von Disk (API/CLI schreiben oft nur settings.json).
    Erzwingt Neustart auch wenn derselbe Sender schon läuft (Start-Guard umgehen).
    Returns: Kurzstatus für Logs/UI („fm:…“, „idle“, …).
    """
    try:
        from settings import load_settings as _ls
        settings = _ls()
    except Exception:
        settings = settings or {}
    rtype = str((S or {}).get("radio_type") or "").upper()

    # Start-Guards in play_station prüfen radio_playing+gleicher Sender —
    # für EQ/NR müssen wir den Guard knacken.
    def _force_replay():
        try:
            S["radio_playing"] = False
        except Exception:
            pass

    if rtype == "FM":
        st = settings.get("last_fm_station")
        if st and (st.get("freq") or st.get("name")):
            from modules.radio import fm
            try:
                fm.stop(S)
            except Exception:
                pass
            _force_replay()
            fm.play_station(st, S, settings)
            return f"fm:{st.get('name') or st.get('freq')}"
        return "fm:no-station"
    if rtype == "DAB":
        st = settings.get("last_dab_station")
        if st and st.get("name"):
            from modules.radio import dab
            try:
                dab.stop(S)
            except Exception:
                pass
            _force_replay()
            dab.play_station(st, S, settings)
            return f"dab:{st.get('name')}"
        return "dab:no-station"
    if rtype in ("WEB", "WEBRADIO"):
        st = settings.get("last_web_station")
        if st:
            from modules import webradio
            try:
                webradio.stop(S)
            except Exception:
                pass
            _force_replay()
            webradio.play_station(st, S, settings)
            return f"web:{st.get('name') or '?'}"
        return "web:no-station"
    if rtype == "SCANNER":
        try:
            from modules.radio import scanner as sc
            band = str(S.get("scanner_band") or "").lower()
            freq = S.get("scanner_freq") or S.get("radio_freq")
            name = S.get("radio_name") or S.get("scanner_name") or "Scanner"
            bw = int(S.get("scanner_bw") or 12500)
            if freq:
                try:
                    sc.stop(S)
                except Exception:
                    pass
                _force_replay()
                sc.play_freq(float(freq), name, bw, S, settings=settings, band_id=band or None)
                return f"scanner:{freq}"
        except Exception as e:
            return f"scanner:err:{e}"
        return "scanner:no-freq"
    return f"idle:{rtype or 'none'}"
