"""
modules/spectrum.py — scanner-orientierte Spektrumsanalyse

Ziel:
- bekannte Kanalbänder wie PMR446 / Freenet beobachten
- mehrere FFT-Frames über Zeit erfassen
- Kanalenergie integrieren
- kurze Aktivitätstrigger erkennen
- Kandidaten für scanner.py liefern

Hinweis:
- erste Version bewusst auf channelized watch fokussiert
- Peak-Mode / Sweep für VHF/UHF folgt später
- alter FM-Sweep-Prototyp bleibt als Kompatibilitätsbereich unten erhalten
"""

from __future__ import annotations

import os
import json
import time
import math
import subprocess
from dataclasses import dataclass, field
from typing import Optional, Any

try:
    import numpy as np
except ImportError:
    np = None

try:
    from modules import rtlsdr as _rtlsdr
except Exception:
    _rtlsdr = None


SPECTRUM_FILE = "/tmp/pidrive_spectrum.json"


# ============================================================================
# Datenklassen
# ============================================================================

@dataclass
class ChannelDef:
    name: str
    freq_hz: float
    width_hz: float
    label: str = ""
    group: str = ""


@dataclass
class BandProfile:
    name: str
    mode: str                     # "channelized" oder später "peak"
    start_hz: float
    stop_hz: float
    channel_width_hz: float
    channels: list[ChannelDef]

    preferred_sample_rate: int = 256_000
    fft_size: int = 2048
    frame_ms: int = 80
    watch_seconds: float = 2.5

    trigger_on_db: float = 9.0
    trigger_off_db: float = 4.0
    min_active_frames: int = 1
    hold_seconds: float = 3.0

    smoothing_alpha: float = 0.35
    noise_quantile: float = 0.20


@dataclass
class SpectrumConfig:
    center_hz: float
    sample_rate: int
    fft_size: int
    frame_ms: int
    smoothing_alpha: float = 0.35
    noise_quantile: float = 0.20
    debug: bool = False


@dataclass
class SpectrumFrame:
    timestamp: float
    center_hz: float
    sample_rate: int
    freqs_hz: list[float]
    power_db: list[float]
    noise_floor_db: float


@dataclass
class ChannelActivity:
    channel: ChannelDef
    current_power_db: float = -120.0
    relative_power_db: float = 0.0
    max_relative_db: float = 0.0
    avg_relative_db: float = 0.0
    active_frames: int = 0
    total_frames: int = 0
    triggered: bool = False
    hold_until: float = 0.0
    last_seen_ts: float = 0.0
    confidence: float = 0.0


@dataclass
class PeakCandidate:
    freq_hz: float
    score: float
    confidence: float
    power_db: float
    relative_db: float
    timestamp: float
    source: str                   # "channel" oder später "peak"
    channel_name: str = ""
    bandwidth_hz: float = 0.0
    active_frames: int = 0
    note: str = ""


@dataclass
class DetectionResult:
    found: bool
    best_candidate: Optional[PeakCandidate]
    candidates: list[PeakCandidate]
    frames_processed: int
    watch_started_ts: float
    watch_ended_ts: float
    note: str = ""
    debug: dict = field(default_factory=dict)


# ============================================================================
# Bandprofile: PMR446 / Freenet
# scanner.py kennt diese Kanäle bereits [2]
# ============================================================================

PMR446_PROFILE = BandProfile(
    name="PMR446",
    mode="channelized",
    start_hz=446_006_250,
    stop_hz=446_093_750,
    channel_width_hz=12_500,
    channels=[
        ChannelDef("PMR1", 446_006_250, 12_500, label="PMR Kanal 1"),
        ChannelDef("PMR2", 446_018_750, 12_500, label="PMR Kanal 2"),
        ChannelDef("PMR3", 446_031_250, 12_500, label="PMR Kanal 3"),
        ChannelDef("PMR4", 446_043_750, 12_500, label="PMR Kanal 4"),
        ChannelDef("PMR5", 446_056_250, 12_500, label="PMR Kanal 5"),
        ChannelDef("PMR6", 446_068_750, 12_500, label="PMR Kanal 6"),
        ChannelDef("PMR7", 446_081_250, 12_500, label="PMR Kanal 7"),
        ChannelDef("PMR8", 446_093_750, 12_500, label="PMR Kanal 8"),
    ],
    preferred_sample_rate=256_000,
    fft_size=2048,
    frame_ms=80,
    watch_seconds=2.5,
    trigger_on_db=9.0,
    trigger_off_db=4.0,
    min_active_frames=1,
    hold_seconds=3.0,
    smoothing_alpha=0.35,
    noise_quantile=0.20,
)

FREENET_PROFILE = BandProfile(
    name="FREENET",
    mode="channelized",
    start_hz=149_025_000,
    stop_hz=149_087_500,
    channel_width_hz=12_500,
    channels=[
        ChannelDef("FREENET1", 149_025_000, 12_500, label="Freenet K1"),
        ChannelDef("FREENET2", 149_037_500, 12_500, label="Freenet K2"),
        ChannelDef("FREENET3", 149_050_000, 12_500, label="Freenet K3"),
        ChannelDef("FREENET4", 149_087_500, 12_500, label="Freenet K4"),
    ],
    preferred_sample_rate=256_000,
    fft_size=2048,
    frame_ms=80,
    watch_seconds=2.5,
    trigger_on_db=9.0,
    trigger_off_db=4.0,
    min_active_frames=1,
    hold_seconds=3.0,
    smoothing_alpha=0.35,
    noise_quantile=0.20,
)


# ============================================================================
# Helper
# ============================================================================

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


def compute_center_for_channels(channels: list[ChannelDef]) -> float:
    lo = min(ch.freq_hz for ch in channels)
    hi = max(ch.freq_hz for ch in channels)
    return (lo + hi) / 2.0


def compute_span_for_channels(channels: list[ChannelDef]) -> float:
    lo = min(ch.freq_hz - (ch.width_hz / 2.0) for ch in channels)
    hi = max(ch.freq_hz + (ch.width_hz / 2.0) for ch in channels)
    return hi - lo


def relative_db(power_db: float, noise_floor_db: float) -> float:
    return power_db - noise_floor_db


def confidence_from_activity(relative_db_val: float, active_frames: int, total_frames: int) -> float:
    if total_frames <= 0:
        return 0.0
    ratio = active_frames / total_frames
    rel_part = max(0.0, min(relative_db_val / 20.0, 1.0))
    return max(0.0, min(0.65 * rel_part + 0.35 * ratio, 1.0))


# ============================================================================
# Backend
# ============================================================================

class SampleBackend:
    def capture_iq(self, center_hz: float, sample_rate: int, sample_count: int) -> bytes:
        raise NotImplementedError


class RTLSDRBackend(SampleBackend):
    """
    Einfache IQ-Erfassung via rtl_sdr.
    Erste Version: pro Frame ein kurzer Snapshot.
    """

    def __init__(self, ppm: int = 0, gain: int = -1, timeout_s: float = 6.0):
        self.ppm = int(ppm)
        self.gain = int(gain)
        self.timeout_s = float(timeout_s)

    def capture_iq(self, center_hz: float, sample_rate: int, sample_count: int) -> bytes:
        if _rtlsdr:
            usb = _rtlsdr.detect_usb()
            if not usb.get("present"):
                raise RuntimeError("RTL-SDR nicht erkannt")
            if _rtlsdr.is_busy():
                raise RuntimeError("RTL-SDR belegt")

        cmd = [
            "rtl_sdr",
            "-f", str(int(center_hz)),
            "-s", str(int(sample_rate)),
            "-n", str(int(sample_count)),
        ]

        if self.ppm:
            cmd += ["-p", str(self.ppm)]
        if self.gain >= 0:
            cmd += ["-g", str(self.gain)]

        cp = subprocess.run(cmd, capture_output=True, timeout=self.timeout_s)

        raw = cp.stdout or b""
        if not raw:
            err = (cp.stderr or b"").decode("utf-8", "ignore")[:240]
            raise RuntimeError(f"keine IQ-Daten ({err})")

        return raw


# ============================================================================
# DSP
# ============================================================================

class FFTProcessor:
    def __init__(self, fft_size: int, smoothing_alpha: float = 0.35):
        if np is None:
            raise RuntimeError("numpy fehlt — bitte installieren")
        self.fft_size = int(fft_size)
        self.smoothing_alpha = float(smoothing_alpha)
        self._prev_power: Optional[np.ndarray] = None

    @staticmethod
    def _u8_iq_to_complex(raw: bytes) -> np.ndarray:
        arr = np.frombuffer(raw, dtype=np.uint8).astype(np.float32)
        if len(arr) < 2:
            return np.array([], dtype=np.complex64)
        i = (arr[0::2] - 128.0) / 128.0
        q = (arr[1::2] - 128.0) / 128.0
        return (i + 1j * q).astype(np.complex64)

    def compute_frame(self, raw_iq: bytes, center_hz: float, sample_rate: int) -> SpectrumFrame:
        samples = self._u8_iq_to_complex(raw_iq)
        if samples.size == 0:
            raise RuntimeError("leere IQ-Samples")

        if samples.size < self.fft_size:
            raise RuntimeError("zu wenige Samples für FFT")

        samples = samples[:self.fft_size]
        window = np.hanning(self.fft_size).astype(np.float32)
        windowed = samples * window

        fft = np.fft.fftshift(np.fft.fft(windowed))
        power = np.maximum(np.abs(fft) ** 2, 1e-12)
        power_db = 10.0 * np.log10(power)

        if self._prev_power is not None:
            a = self.smoothing_alpha
            power_db = a * power_db + (1.0 - a) * self._prev_power
        self._prev_power = power_db.copy()

        freqs = np.linspace(
            center_hz - sample_rate / 2.0,
            center_hz + sample_rate / 2.0,
            self.fft_size,
            endpoint=False
        )

        return SpectrumFrame(
            timestamp=time.time(),
            center_hz=float(center_hz),
            sample_rate=int(sample_rate),
            freqs_hz=freqs.tolist(),
            power_db=power_db.tolist(),
            noise_floor_db=0.0,
        )


class NoiseEstimator:
    def __init__(self, quantile: float = 0.20):
        if np is None:
            raise RuntimeError("numpy fehlt — bitte installieren")
        self.quantile = float(quantile)

    def estimate(self, power_db: list[float]) -> float:
        if not power_db:
            return -120.0
        arr = np.array(power_db, dtype=np.float32)
        return float(np.quantile(arr, self.quantile))


# ============================================================================
# Kanalanalyse
# ============================================================================

class ChannelAnalyzer:
    def __init__(self, channels: list[ChannelDef]):
        if np is None:
            raise RuntimeError("numpy fehlt — bitte installieren")
        self.channels = channels

    def map_channel_bins(self, frame: SpectrumFrame) -> dict[str, tuple[int, int]]:
        freqs = np.array(frame.freqs_hz, dtype=np.float64)
        out: dict[str, tuple[int, int]] = {}

        for ch in self.channels:
            lo = ch.freq_hz - (ch.width_hz / 2.0)
            hi = ch.freq_hz + (ch.width_hz / 2.0)

            idx = np.where((freqs >= lo) & (freqs <= hi))[0]
            if idx.size == 0:
                continue

            out[ch.name] = (int(idx[0]), int(idx[-1]))

        return out

    def integrate_channel_power(
        self,
        frame: SpectrumFrame,
        bin_map: dict[str, tuple[int, int]]
    ) -> dict[str, float]:
        power_db = np.array(frame.power_db, dtype=np.float32)
        result: dict[str, float] = {}

        for ch in self.channels:
            rng = bin_map.get(ch.name)
            if not rng:
                continue
            a, b = rng
            if b < a:
                continue

            seg_db = power_db[a:b+1]
            if seg_db.size == 0:
                continue

            # lineare Leistung mitteln, dann zurück nach dB
            seg_lin = np.power(10.0, seg_db / 10.0)
            mean_lin = max(float(np.mean(seg_lin)), 1e-12)
            result[ch.name] = 10.0 * math.log10(mean_lin)

        return result

    def score_channels(self, channel_powers: dict[str, float], noise_floor_db: float) -> dict[str, float]:
        return {name: (pwr - noise_floor_db) for name, pwr in channel_powers.items()}


# ============================================================================
# Aktivitätslogik
# ============================================================================

class ActivityTracker:
    def __init__(self, profile: BandProfile):
        self.profile = profile
        self.channels: dict[str, ChannelActivity] = {
            ch.name: ChannelActivity(channel=ch)
            for ch in profile.channels
        }

    def reset(self):
        for name, state in list(self.channels.items()):
            self.channels[name] = ChannelActivity(channel=state.channel)

    def update_channel(self, ts: float, channel: ChannelDef, absolute_power_db: float, relative_db_val: float):
        st = self.channels[channel.name]
        st.total_frames += 1
        st.current_power_db = absolute_power_db
        st.relative_power_db = relative_db_val
        st.max_relative_db = max(st.max_relative_db, relative_db_val)

        n = st.total_frames
        st.avg_relative_db = ((st.avg_relative_db * (n - 1)) + relative_db_val) / max(n, 1)

        if relative_db_val >= self.profile.trigger_on_db:
            st.triggered = True
            st.active_frames += 1
            st.last_seen_ts = ts
            st.hold_until = max(st.hold_until, ts + self.profile.hold_seconds)

        elif st.triggered:
            if ts <= st.hold_until or relative_db_val >= self.profile.trigger_off_db:
                st.triggered = True
            else:
                st.triggered = False

        st.confidence = confidence_from_activity(
            st.max_relative_db,
            st.active_frames,
            st.total_frames
        )

    def build_candidates(self, now_ts: float) -> list[PeakCandidate]:
        out: list[PeakCandidate] = []

        for st in self.channels.values():
            if st.active_frames < self.profile.min_active_frames:
                continue

            if (not st.triggered) and now_ts > st.hold_until:
                if st.max_relative_db < self.profile.trigger_on_db:
                    continue

            score = (
                (0.60 * st.max_relative_db) +
                (0.25 * st.avg_relative_db) +
                (0.15 * st.active_frames)
            )

            out.append(PeakCandidate(
                freq_hz=float(st.channel.freq_hz),
                score=float(score),
                confidence=float(st.confidence),
                power_db=float(st.current_power_db),
                relative_db=float(st.max_relative_db),
                timestamp=float(now_ts),
                source="channel",
                channel_name=st.channel.name,
                bandwidth_hz=float(st.channel.width_hz),
                active_frames=int(st.active_frames),
                note=st.channel.label or st.channel.name,
            ))

        out.sort(key=lambda x: (x.score, x.confidence), reverse=True)
        return out

    def best_candidate(self, now_ts: float) -> Optional[PeakCandidate]:
        cands = self.build_candidates(now_ts)
        return cands[0] if cands else None


# ============================================================================
# Hauptklasse
# ============================================================================

class SpectrumWatcher:
    def __init__(
        self,
        backend: SampleBackend,
        fft_processor: FFTProcessor,
        noise_estimator: NoiseEstimator,
    ):
        self.backend = backend
        self.fft_processor = fft_processor
        self.noise_estimator = noise_estimator

    def watch_channels(self, profile: BandProfile, debug: bool = False) -> DetectionResult:
        if profile.mode != "channelized":
            raise ValueError(f"BandProfile {profile.name}: mode muss 'channelized' sein")

        center_hz = compute_center_for_channels(profile.channels)
        config = SpectrumConfig(
            center_hz=center_hz,
            sample_rate=profile.preferred_sample_rate,
            fft_size=profile.fft_size,
            frame_ms=profile.frame_ms,
            smoothing_alpha=profile.smoothing_alpha,
            noise_quantile=profile.noise_quantile,
            debug=debug,
        )

        sample_count = int(config.sample_rate * (config.frame_ms / 1000.0))
        sample_count = max(sample_count, config.fft_size * 2)

        analyzer = ChannelAnalyzer(profile.channels)
        tracker = ActivityTracker(profile)

        started = time.time()
        ended_target = started + profile.watch_seconds
        frames_processed = 0

        debug_frames: list[dict[str, Any]] = []
        debug_scores: list[dict[str, Any]] = []
        bin_map_cached: Optional[dict[str, tuple[int, int]]] = None

        while time.time() < ended_target:
            raw = self.backend.capture_iq(
                center_hz=config.center_hz,
                sample_rate=config.sample_rate,
                sample_count=sample_count,
            )

            frame = self.fft_processor.compute_frame(
                raw_iq=raw,
                center_hz=config.center_hz,
                sample_rate=config.sample_rate,
            )

            noise_floor = self.noise_estimator.estimate(frame.power_db)
            frame.noise_floor_db = noise_floor

            if bin_map_cached is None:
                bin_map_cached = analyzer.map_channel_bins(frame)

            channel_powers = analyzer.integrate_channel_power(frame, bin_map_cached)
            scores = analyzer.score_channels(channel_powers, noise_floor)

            ts = frame.timestamp
            for ch in profile.channels:
                if ch.name not in channel_powers:
                    continue
                tracker.update_channel(
                    ts=ts,
                    channel=ch,
                    absolute_power_db=channel_powers[ch.name],
                    relative_db_val=scores[ch.name],
                )

            frames_processed += 1

            if debug:
                debug_frames.append({
                    "ts": round(frame.timestamp, 3),
                    "noise_floor_db": round(noise_floor, 2),
                })
                debug_scores.append({
                    "ts": round(frame.timestamp, 3),
                    "channels": {k: round(v, 2) for k, v in scores.items()}
                })

        ended = time.time()
        candidates = tracker.build_candidates(ended)
        best = candidates[0] if candidates else None

        result = DetectionResult(
            found=best is not None,
            best_candidate=best,
            candidates=candidates,
            frames_processed=frames_processed,
            watch_started_ts=started,
            watch_ended_ts=ended,
            note=f"{profile.name}: {frames_processed} Frames verarbeitet",
            debug={
                "center_hz": int(center_hz),
                "sample_rate": int(config.sample_rate),
                "fft_size": int(config.fft_size),
                "frame_ms": int(config.frame_ms),
                "span_hz": int(compute_span_for_channels(profile.channels)),
                "frames": debug_frames if debug else [],
                "scores": debug_scores if debug else [],
            }
        )

        save_last_spectrum({
            "ok": True,
            "mode": "channel_watch",
            "profile": profile.name,
            "center_hz": int(center_hz),
            "sample_rate": int(config.sample_rate),
            "fft_size": int(config.fft_size),
            "frame_ms": int(config.frame_ms),
            "frames_processed": int(frames_processed),
            "found": bool(result.found),
            "best_candidate": _candidate_to_dict(best) if best else None,
            "candidates": [_candidate_to_dict(c) for c in candidates],
            "debug": result.debug,
            "ts": int(time.time()),
        })

        return result


def _candidate_to_dict(c: Optional[PeakCandidate]) -> Optional[dict]:
    if c is None:
        return None
    return {
        "freq_hz": c.freq_hz,
        "freq_mhz": round(c.freq_hz / 1e6, 6),
        "score": round(c.score, 3),
        "confidence": round(c.confidence, 3),
        "power_db": round(c.power_db, 2),
        "relative_db": round(c.relative_db, 2),
        "timestamp": round(c.timestamp, 3),
        "source": c.source,
        "channel_name": c.channel_name,
        "bandwidth_hz": c.bandwidth_hz,
        "active_frames": c.active_frames,
        "note": c.note,
    }


# ============================================================================
# Einfache Convenience-API für scanner.py / Tests
# ============================================================================

def build_default_watcher(ppm: int = 0, gain: int = -1) -> SpectrumWatcher:
    backend = RTLSDRBackend(ppm=ppm, gain=gain)
    fft = FFTProcessor(fft_size=PMR446_PROFILE.fft_size, smoothing_alpha=0.35)
    noise = NoiseEstimator(quantile=0.20)
    return SpectrumWatcher(backend, fft, noise)


def watch_pmr446(ppm: int = 0, gain: int = -1, debug: bool = False) -> DetectionResult:
    watcher = build_default_watcher(ppm=ppm, gain=gain)
    return watcher.watch_channels(PMR446_PROFILE, debug=debug)


def watch_freenet(ppm: int = 0, gain: int = -1, debug: bool = False) -> DetectionResult:
    watcher = build_default_watcher(ppm=ppm, gain=gain)
    return watcher.watch_channels(FREENET_PROFILE, debug=debug)


# ============================================================================
# Kompatibilitätsbereich: alter FM-Sweep-Prototyp aus bisherigem spectrum.py [3]
# leicht bereinigt, damit WebUI/APIs nicht sofort brechen
# ============================================================================

def _u8_iq_to_complex_legacy(raw: bytes):
    if not raw:
        return []
    n = len(raw) // 2
    out = [0j] * n
    for i in range(n):
        ii = (raw[2 * i] - 128) / 128.0
        qq = (raw[2 * i + 1] - 128) / 128.0
        out[i] = complex(ii, qq)
    return out


def _fft_power_db_legacy(samples):
    if np is None:
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


def _find_peaks(spectrum_db, center_mhz, sample_rate_hz, min_db=None, max_peaks=20, min_distance_bins=8):
    peaks = []
    if not spectrum_db:
        return peaks

    n = len(spectrum_db)
    bin_hz = sample_rate_hz / n

    if min_db is None:
        avg = sum(spectrum_db) / n
        min_db = avg + 8.0

    for i in range(1, n - 1):
        v = spectrum_db[i]
        if v < min_db:
            continue
        if v >= spectrum_db[i - 1] and v >= spectrum_db[i + 1]:
            offset_hz = (i - n / 2) * bin_hz
            freq_mhz = center_mhz + (offset_hz / 1e6)
            peaks.append({"bin": i, "freq_mhz": round(freq_mhz, 6), "db": round(v, 2)})

    peaks.sort(key=lambda x: x["db"], reverse=True)
    selected = []
    for p in peaks:
        if all(abs(p["bin"] - q["bin"]) >= min_distance_bins for q in selected):
            selected.append(p)
        if len(selected) >= max_peaks:
            break
    return selected


def get_confirmed_stations(min_hits: int = 2) -> list:
    data = load_last_spectrum()
    if not data or data.get("mode") != "fm_sweep":
        return []
    confirmed = data.get("candidates", [])
    return [c for c in confirmed if c.get("hits", 1) >= min_hits]


def capture_spectrum(center_mhz, sample_rate_hz=2048000, sample_count=262144,
                     ppm=0, gain=-1, peak_threshold_db=None):
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

    samples = _u8_iq_to_complex_legacy(raw)

    try:
        spectrum_db, n_bins = _fft_power_db_legacy(samples)
    except RuntimeError as e:
        return {"ok": False, "error": str(e)}

    peaks = _find_peaks(spectrum_db, float(center_mhz),
                        int(sample_rate_hz), peak_threshold_db)

    result = {
        "ok": True,
        "mode": "single",
        "center_mhz": float(center_mhz),
        "sample_rate_hz": int(sample_rate_hz),
        "sample_count_iq": len(samples),
        "ppm": int(ppm),
        "gain": int(gain),
        "bin_hz": (sample_rate_hz / n_bins) if n_bins else 0,
        "peaks": peaks,
        "spectrum_db": spectrum_db,
        "ts": int(time.time()),
    }
    save_last_spectrum(result)
    return result


def sweep_fm_band(start_mhz=87.5, stop_mhz=108.0, step_mhz=1.0,
                  sample_rate_hz=2048000, sample_count=131072,
                  ppm=0, gain=-1, peak_threshold_db=None):
    centers = []
    cur = float(start_mhz)
    while cur <= float(stop_mhz):
        centers.append(round(cur, 3))
        cur += float(step_mhz)

    sweep = []
    all_peaks = []

    for c in centers:
        one = capture_spectrum(c, sample_rate_hz=sample_rate_hz,
                               sample_count=sample_count, ppm=ppm,
                               gain=gain, peak_threshold_db=peak_threshold_db)
        if not one.get("ok"):
            sweep.append({"center_mhz": c, "ok": False, "error": one.get("error", "?")})
            continue
        peaks = one.get("peaks", [])
        sweep.append({"center_mhz": c, "ok": True,
                      "peak_count": len(peaks), "top_peaks": peaks[:8]})
        all_peaks.extend(peaks)

    all_deduped = _dedupe_peaks(all_peaks, resolution_mhz=0.1)

    fm_candidates = [c for c in all_deduped if 87.4 <= c["freq_mhz"] <= 108.1]

    min_hits = max(1, int(len(centers) * 0.3))
    confirmed = [c for c in fm_candidates if c.get("hits", 1) >= min_hits]
    unconfirmed = [c for c in fm_candidates if c.get("hits", 1) < min_hits]

    result = {
        "ok": True,
        "mode": "fm_sweep",
        "start_mhz": float(start_mhz),
        "stop_mhz": float(stop_mhz),
        "step_mhz": float(step_mhz),
        "sample_rate_hz": int(sample_rate_hz),
        "sample_count": int(sample_count),
        "ppm": int(ppm),
        "gain": int(gain),
        "min_hits": min_hits,
        "windows_total": len(centers),
        "windows_ok": sum(1 for w in sweep if w.get("ok")),
        "windows": sweep,
        "candidates": confirmed[:40],
        "candidates_weak": unconfirmed[:20],
        "candidates_all_count": len(fm_candidates),
        "ts": int(time.time()),
    }
    save_last_spectrum(result)
    return result