"""freq_plan.py — Bandgrenzen, PMR446-Kanäle, Oberwellen-/RTL-Konflikte, freie Frequenz.

Reine Funktionen ohne Hardware-Zugriff (testbar ohne Pi).
Siehe docs/planung/KONZEPT-FM-TX.md Abschnitt 3.
"""
from __future__ import annotations

import math

UKW_MIN_MHZ = 87.5
UKW_MAX_MHZ = 108.0
UKW_STEP_MHZ = 0.05
PI4_RECOMMENDED_MAX_MHZ = 93.0

PMR_BASE_MHZ = 446.00625
PMR_SPACING_MHZ = 0.0125
PMR_CHANNELS = 16

BANDS = ("ukw", "pmr446")

DAB_BLOCK_HALF_MHZ = 0.768
RTL_CONFLICT_MHZ = 1.0
FREE_MIN_SPACING_MHZ = 0.4

# DAB Band III (ETSI EN 300 401), Mittenfrequenzen in MHz
DAB_BAND3 = {
    "5A": 174.928, "5B": 176.640, "5C": 178.352, "5D": 180.064,
    "6A": 181.936, "6B": 183.648, "6C": 185.360, "6D": 187.072,
    "7A": 188.928, "7B": 190.640, "7C": 192.352, "7D": 194.064,
    "8A": 195.936, "8B": 197.648, "8C": 199.360, "8D": 201.072,
    "9A": 202.928, "9B": 204.640, "9C": 206.352, "9D": 208.064,
    "10A": 209.936, "10N": 210.096, "10B": 211.648, "10C": 213.360, "10D": 215.072,
    "11A": 216.928, "11N": 217.088, "11B": 218.640, "11C": 220.352, "11D": 222.064,
    "12A": 223.936, "12N": 224.096, "12B": 225.648, "12C": 227.360, "12D": 229.072,
    "13A": 230.784, "13B": 232.496, "13C": 234.208, "13D": 235.776,
    "13E": 237.488, "13F": 239.200,
}


def snap_ukw(freq_mhz: float) -> float:
    """Auf das 50-kHz-Raster runden."""
    return round(round(float(freq_mhz) / UKW_STEP_MHZ) * UKW_STEP_MHZ, 2)


def validate_ukw(freq_mhz) -> tuple[bool, str, float | None]:
    """(ok, fehler, frequenz_auf_raster)."""
    try:
        f = float(freq_mhz)
    except (TypeError, ValueError):
        return False, f"Frequenz ungültig: {freq_mhz!r}", None
    if math.isnan(f) or math.isinf(f):
        return False, "Frequenz ungültig", None
    if f < UKW_MIN_MHZ - 1e-9 or f > UKW_MAX_MHZ + 1e-9:
        return False, f"UKW nur {UKW_MIN_MHZ:.2f}–{UKW_MAX_MHZ:.2f} MHz (war {f:.3f})", None
    s = snap_ukw(f)
    if abs(s - f) > 1e-6:
        return False, f"UKW-Raster 50 kHz: {f:.3f} → {s:.2f} MHz verwenden", s
    return True, "", s


def pmr_channel_mhz(n) -> float:
    """PMR446-Kanal n (1–16) → MHz. ValueError außerhalb."""
    try:
        n = int(n)
    except (TypeError, ValueError):
        raise ValueError(f"PMR-Kanal ungültig: {n!r}")
    if not 1 <= n <= PMR_CHANNELS:
        raise ValueError(f"PMR-Kanal nur 1–{PMR_CHANNELS} (war {n})")
    return round(PMR_BASE_MHZ + (n - 1) * PMR_SPACING_MHZ, 5)


def pmr_channels() -> list[dict]:
    return [{"channel": n, "freq_mhz": pmr_channel_mhz(n)} for n in range(1, PMR_CHANNELS + 1)]


def tx_freq_mhz(band: str, freq_mhz=None, pmr_channel=None) -> float:
    """Effektive Sendefrequenz für Band + Frequenz/Kanal (ValueError bei Fehler)."""
    band = (band or "ukw").lower()
    if band == "pmr446":
        return pmr_channel_mhz(pmr_channel)
    if band == "ukw":
        ok, err, f = validate_ukw(freq_mhz)
        if not ok:
            raise ValueError(err)
        return f
    raise ValueError(f"Band unbekannt: {band!r}")


def harmonics(freq_mhz: float, orders=(2, 3)) -> list[dict]:
    return [{"order": n, "freq_mhz": round(float(freq_mhz) * n, 3)} for n in orders]


def harmonics_conflicts(freq_mhz: float, orders=(2, 3), active_dab_channel: str = "") -> list[dict]:
    """DAB-Blöcke, die von der n-ten Harmonischen getroffen werden.

    Die FM-Hub (±75 kHz) wächst mit der Ordnung; Toleranz = Blockhälfte + n·0,1 MHz.
    """
    out = []
    active = (active_dab_channel or "").upper().strip()
    for h in harmonics(freq_mhz, orders):
        tol = DAB_BLOCK_HALF_MHZ + h["order"] * 0.1
        for ch, fc in DAB_BAND3.items():
            if abs(h["freq_mhz"] - fc) <= tol:
                out.append({
                    "order": h["order"],
                    "harmonic_mhz": h["freq_mhz"],
                    "dab_channel": ch,
                    "dab_center_mhz": fc,
                    "active": ch == active,
                })
    return out


def rtl_conflict(tx_mhz: float, rx_mhz) -> dict | None:
    """Konflikt, wenn der RTL-SDR ±1 MHz um die Sendefrequenz empfängt."""
    if rx_mhz in (None, "", 0):
        return None
    try:
        rx = float(rx_mhz)
    except (TypeError, ValueError):
        return None
    d = abs(float(tx_mhz) - rx)
    if d <= RTL_CONFLICT_MHZ:
        return {"rx_mhz": rx, "delta_mhz": round(d, 3)}
    return None


def pi_model_supported(model: str) -> tuple[bool, str]:
    """GPCLK-Backends laufen auf BCM2835/6/7/2711, nicht auf Pi 5 (RP1)."""
    m = (model or "").strip()
    if "Raspberry Pi 5" in m or "Compute Module 5" in m:
        return False, "Pi 5 (RP1) wird von PiFmRds/rpitx nicht unterstützt"
    return True, ""


def read_pi_model() -> str:
    try:
        with open("/proc/device-tree/model", "rb") as f:
            return f.read().decode("utf-8", "replace").strip("\x00\n ")
    except Exception:
        return ""


def plan(band: str, freq_mhz=None, pmr_channel=None, pi_model: str = "",
         active_dab_channel: str = "", rtl_rx_mhz=None, block_on_dab: bool = True) -> dict:
    """Konflikt-/Hinweisbericht für eine Sendefrequenz.

    Rückgabe: {"ok", "freq_mhz", "errors":[...], "warnings":[...], "harmonics":[...], "dab":[...]}
    """
    errors: list[str] = []
    warnings: list[str] = []
    try:
        f = tx_freq_mhz(band, freq_mhz, pmr_channel)
    except ValueError as e:
        return {"ok": False, "freq_mhz": None, "errors": [str(e)], "warnings": [],
                "harmonics": [], "dab": []}

    ok_pi, why_pi = pi_model_supported(pi_model)
    if not ok_pi:
        errors.append(why_pi)

    dab = []
    if band == "ukw":
        if "Raspberry Pi 4" in (pi_model or "") and f >= PI4_RECOMMENDED_MAX_MHZ:
            warnings.append(f"Pi 4: unter {PI4_RECOMMENDED_MAX_MHZ:.0f} MHz empfohlen (markondej, Lab prüfen)")
        dab = harmonics_conflicts(f, active_dab_channel=active_dab_channel)
        hit_active = [d for d in dab if d["active"]]
        if hit_active:
            msg = (f"{hit_active[0]['order']}. Harmonische {hit_active[0]['harmonic_mhz']:.3f} MHz "
                   f"trifft aktiven DAB-Block {hit_active[0]['dab_channel']}")
            (errors if block_on_dab else warnings).append(msg)
        elif dab:
            chans = ", ".join(sorted({d["dab_channel"] for d in dab}))
            warnings.append(f"2. Harmonische im DAB-Band III ({chans}) — Tiefpass nötig")
    else:
        warnings.append("PMR446 aus GPIO ist nicht zulässig — nur geschirmt mit Dummy-Load")

    rc = rtl_conflict(f, rtl_rx_mhz)
    if rc:
        errors.append(f"RTL-SDR empfängt {rc['rx_mhz']:.3f} MHz (Δ {rc['delta_mhz']:.3f} MHz ≤ 1 MHz)")

    return {
        "ok": not errors,
        "freq_mhz": f,
        "errors": errors,
        "warnings": warnings,
        "harmonics": harmonics(f),
        "dab": dab,
    }


def suggest_free(peaks, start_mhz: float = UKW_MIN_MHZ, stop_mhz: float = UKW_MAX_MHZ,
                 top_n: int = 5, active_dab_channel: str = "", grid_mhz: float = 0.1,
                 min_spacing_mhz: float = FREE_MIN_SPACING_MHZ, prefer_below_mhz=None) -> list[dict]:
    """Freie UKW-Frequenzen aus Scan-Peaks.

    peaks: [{"freq_mhz", "mean_db"|"db"}] aus spectrum.scan_fm_channels() bzw. capture_range().

    Bewertung: Abstand zum nächsten belegten Kanal (größer = besser), stärkere Nachbarn
    zählen mehr. Treffer auf den aktiven DAB-Block werden verworfen.
    """
    start = max(UKW_MIN_MHZ, float(start_mhz))
    stop = min(UKW_MAX_MHZ, float(stop_mhz))
    if stop <= start:
        return []
    occ = []
    for p in peaks or []:
        try:
            occ.append((float(p.get("freq_mhz")), float(p.get("mean_db", p.get("db", 0.0)))))
        except (TypeError, ValueError, AttributeError):
            continue
    db_vals = [d for _, d in occ]
    db_ref = min(db_vals) if db_vals else 0.0

    out = []
    f = math.ceil(start / grid_mhz - 1e-9) * grid_mhz
    while f <= stop + 1e-9:
        fr = round(f, 2)
        nearest = None
        penalty = 0.0
        for fo, db in occ:
            d = abs(fr - fo)
            if nearest is None or d < nearest:
                nearest = d
            if d < 2.0:
                penalty += max(0.0, db - db_ref + 3.0) * (2.0 - d) / 2.0
        if nearest is None or nearest >= min_spacing_mhz:
            conflicts = harmonics_conflicts(fr, active_dab_channel=active_dab_channel)
            if not any(c["active"] for c in conflicts):
                score = (nearest if nearest is not None else 5.0) * 10.0 - penalty
                if prefer_below_mhz and fr >= float(prefer_below_mhz):
                    score -= 5.0
                out.append({
                    "freq_mhz": fr,
                    "nearest_occupied_mhz": round(nearest, 2) if nearest is not None else None,
                    "score": round(score, 2),
                    "dab_hits": sorted({c["dab_channel"] for c in conflicts}),
                })
        f += grid_mhz
    out.sort(key=lambda x: (-x["score"], x["freq_mhz"]))
    return out[:max(1, int(top_n))]
