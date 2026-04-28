"""
modules/spectrum.py — FM FastScan / FFT-Spektrum (experimentell)
Aufrufer: webui.py (/api/spectrum/capture), main_core.py (optional)
Abhängig von: numpy, subprocess (rtl_sdr)
Schreibt: /tmp/pidrive_spectrum.json
Hinweis: Prototyp — kein Einfluss auf normalen FM-Betrieb
"""


import os
import json
import time
import subprocess

try:
    from modules import rtlsdr as _rtlsdr
except Exception:
    _rtlsdr = None

SPECTRUM_FILE = "/tmp/pidrive_spectrum.json"


def _u8_iq_to_complex(raw: bytes):
    """
    rtl_sdr liefert unsigned 8-bit IQ: I0 Q0 I1 Q1 ...
    Mapping: 0..255 → -1.0..+1.0
    """
    if not raw:
        return []
    n = len(raw) // 2
    out = [0j] * n
    for i in range(n):
        ii = (raw[2 * i]     - 128) / 128.0
        qq = (raw[2 * i + 1] - 128) / 128.0
        out[i] = complex(ii, qq)
    return out


def _fft_power_db(samples):
    """FFT mit Hanning-Fenster, Ausgabe in dB."""
    try:
        import numpy as np
    except ImportError:
        raise RuntimeError("numpy fehlt — bitte installieren: apt install python3-numpy")

    if not samples:
        return [], 0

    arr = np.array(samples, dtype=np.complex64)
    arr = arr * np.hanning(len(arr))
    fft = np.fft.fftshift(np.fft.fft(arr))
    power = np.maximum(np.abs(fft) ** 2, 1e-12)
    db = 10.0 * np.log10(power)
    return db.tolist(), len(db)


def _dedupe_peaks(peaks, resolution_mhz=0.1):
    """Peaks auf Raster zusammenführen, stärksten dB behalten, Trefferzahl mitzählen."""
    buckets = {}
    for p in peaks:
        key = round(round(float(p["freq_mhz"]) / resolution_mhz) * resolution_mhz, 3)
        if key not in buckets:
            buckets[key] = {"freq_mhz": key, "db": p["db"], "hits": 1}
        else:
            buckets[key]["hits"] += 1
            if p["db"] > buckets[key]["db"]:
                buckets[key]["db"] = p["db"]
    result = list(buckets.values())
    result.sort(key=lambda x: x["db"], reverse=True)
    return result


def _find_peaks(spectrum_db, center_mhz, sample_rate_hz,
                min_db=None, max_peaks=20):
    """Lokale Maxima im Spektrum finden."""
    peaks = []
    if not spectrum_db:
        return peaks

    n      = len(spectrum_db)
    bin_hz = sample_rate_hz / n

    if min_db is None:
        avg    = sum(spectrum_db) / n
        min_db = avg + 8.0

    for i in range(1, n - 1):
        v = spectrum_db[i]
        if v < min_db:
            continue
        if v >= spectrum_db[i - 1] and v >= spectrum_db[i + 1]:
            offset_hz = (i - n / 2) * bin_hz
            freq_mhz  = center_mhz + (offset_hz / 1e6)
            peaks.append({"bin": i, "freq_mhz": round(freq_mhz, 6), "db": round(v, 2)})

    peaks.sort(key=lambda x: x["db"], reverse=True)
    selected = []
    for p in peaks:
        if all(abs(p["bin"] - q["bin"]) >= min_distance_bins for q in selected):
            selected.append(p)
        if len(selected) >= max_peaks:
            break
    return selected


def save_last_spectrum(data: dict):
    try:
        tmp = SPECTRUM_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, SPECTRUM_FILE)
    except Exception:
        pass


def load_last_spectrum() -> dict:
    try:
        with open(SPECTRUM_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def get_confirmed_stations(min_hits: int = 2) -> list:
    """
    v0.9.29: Stabile FM-Stationen aus letztem Sweep laden.
    Gibt bereinigte Liste mit freq_mhz, db, hits zurück.
    Nur für Testanzeige — nicht automatisch in fm_stations.json übernehmen.
    """
    data = load_last_spectrum()
    if not data or data.get("mode") != "fm_sweep":
        return []
    confirmed = data.get("candidates", [])
    return [c for c in confirmed if c.get("hits", 1) >= min_hits]


def capture_spectrum(center_mhz, sample_rate_hz=2048000, sample_count=262144,
                     ppm=0, gain=-1, peak_threshold_db=None):
    """
    IQ-Snapshot holen und Spektrum berechnen.
    Nutzt RTL-SDR-Locking aus rtlsdr.py wenn vorhanden.
    """
    if _rtlsdr:
        usb = _rtlsdr.detect_usb()
        if not usb.get("present"):
            return {"ok": False, "error": "RTL-SDR nicht erkannt"}
        if _rtlsdr.is_busy():
            return {"ok": False, "error": "RTL-SDR belegt"}

    center_hz = int(float(center_mhz) * 1e6)
    cmd = ["rtl_sdr", "-f", str(center_hz),
           "-s", str(int(sample_rate_hz)),
           "-n", str(int(sample_count))]

    if int(ppm) != 0:
        cmd += ["-p", str(int(ppm))]
    if int(gain) >= 0:
        cmd += ["-g", str(int(gain))]

    try:
        cp = subprocess.run(cmd, capture_output=True, timeout=25)
    except Exception as e:
        return {"ok": False, "error": str(e)}

    raw = cp.stdout
    if not raw:
        err = (cp.stderr or b"").decode("utf-8", "ignore")[:300]
        return {"ok": False, "error": "keine IQ-Daten", "stderr": err}

    samples = _u8_iq_to_complex(raw)

    try:
        spectrum_db, n_bins = _fft_power_db(samples)
    except RuntimeError as e:
        return {"ok": False, "error": str(e)}

    peaks = _find_peaks(spectrum_db, float(center_mhz),
                        int(sample_rate_hz), peak_threshold_db)

    result = {
        "ok":             True,
        "mode":           "single",
        "center_mhz":     float(center_mhz),
        "sample_rate_hz": int(sample_rate_hz),
        "sample_count_iq":len(samples),
        "ppm":            int(ppm),
        "gain":           int(gain),
        "bin_hz":         (sample_rate_hz / n_bins) if n_bins else 0,
        "peaks":          peaks,
        "spectrum_db":    spectrum_db,
        "ts":             int(time.time()),
    }
    save_last_spectrum(result)
    return result


def sweep_fm_band(start_mhz=87.5, stop_mhz=108.0, step_mhz=1.0,
                  sample_rate_hz=2048000, sample_count=131072,
                  ppm=0, gain=-1, peak_threshold_db=None):
    """
    FM-Band-Sweep: mehrere Center-Frequenzen, Kandidatenliste.
    Peaks aus allen Fenstern werden zusammengeführt (0.1 MHz Auflösung).
    """
    centers = []
    cur = float(start_mhz)
    while cur <= float(stop_mhz):
        centers.append(round(cur, 3))
        cur += float(step_mhz)

    sweep      = []
    all_peaks  = []

    for c in centers:
        one = capture_spectrum(c, sample_rate_hz=sample_rate_hz,
                               sample_count=sample_count, ppm=ppm,
                               gain=gain, peak_threshold_db=peak_threshold_db)
        if not one.get("ok"):
            sweep.append({"center_mhz": c, "ok": False, "error": one.get("error","?")})
            continue
        peaks = one.get("peaks", [])
        sweep.append({"center_mhz": c, "ok": True,
                      "peak_count": len(peaks), "top_peaks": peaks[:8]})
        all_peaks.extend(peaks)

    # v0.9.29: Deduplizierung via _dedupe_peaks (0.1 MHz Raster) + Mehrfachbestätigung
    # Kandidat gilt als stabil wenn hits >= min_hits (Standard: 2 Fenster)
    all_deduped = _dedupe_peaks(all_peaks, resolution_mhz=0.1)

    # FM-Band-Filter: nur 87.5–108.0 MHz
    fm_candidates = [c for c in all_deduped
                     if 87.4 <= c["freq_mhz"] <= 108.1]

    # Stabile Kandidaten: in ≥ min_hits Sweep-Fenstern gesehen
    min_hits = max(1, int(len(centers) * 0.3))  # 30% der Fenster = bestätigt
    confirmed  = [c for c in fm_candidates if c.get("hits", 1) >= min_hits]
    unconfirmed = [c for c in fm_candidates if c.get("hits", 1) < min_hits]

    result = {
        "ok":             True,
        "mode":           "fm_sweep",
        "start_mhz":      float(start_mhz),
        "stop_mhz":       float(stop_mhz),
        "step_mhz":       float(step_mhz),
        "sample_rate_hz": int(sample_rate_hz),
        "sample_count":   int(sample_count),
        "ppm":            int(ppm),
        "gain":           int(gain),
        "min_hits":       min_hits,
        "windows_total":  len(centers),
        "windows_ok":     sum(1 for w in sweep if w.get("ok")),
        "windows":        sweep,
        "candidates":          confirmed[:40],      # stabile Kandidaten
        "candidates_weak":     unconfirmed[:20],    # einmalige Kandidaten
        "candidates_all_count": len(fm_candidates),
        "ts":             int(time.time()),
    }
    save_last_spectrum(result)
    return result
