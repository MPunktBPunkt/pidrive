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
import select
import signal
import subprocess
from dataclasses import dataclass, field
from typing import Optional, Any

try:
    import numpy as np
except ImportError:
    np = None

try:
    from modules.radio import rtlsdr as _rtlsdr
except Exception as _e:
    _rtlsdr = None
    try:
        from modules import degraded_imports as _deg
        _deg.report("modules.radio.rtlsdr", str(_e))
    except Exception:
        pass


SPECTRUM_FILE = "/tmp/pidrive_spectrum.json"


# ============================================================================
# v0.10.0: Pi 3B Ressourcen-Guards
# ============================================================================

_SPECTRUM_MIN_CALL_INTERVAL = 5.0  # Min. Sekunden zwischen watch_*()-Aufrufen
_spectrum_last_call_ts: float = 0.0


def _check_rate_limit() -> bool:
    """True = Capture erlaubt. Aktualisiert Timestamp. Thread-safe fuer single-core Pi."""
    global _spectrum_last_call_ts
    import time as _t
    now = _t.time()
    if now - _spectrum_last_call_ts >= _SPECTRUM_MIN_CALL_INTERVAL:
        _spectrum_last_call_ts = now
        return True
    return False


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
    stop_hz=446_193_750,  # 16 Kanäle (PMR446d); K1–K8 = klassisch
    channel_width_hz=12_500,
    channels=[
        ChannelDef(
            f"PMR{i+1}",
            int(round((446.00625 + i * 0.01250) * 1e6)),
            12_500,
            label=f"PMR Kanal {i+1}",
        )
        for i in range(16)
    ],
    preferred_sample_rate=256_000,  # deckt ~200 kHz Band + Rand
    fft_size=2048,
    frame_ms=80,
    watch_seconds=2.5,
    # Nahfeld-Walkie: 9 dB war zu niedrig → viele Nachbarkanäle
    trigger_on_db=14.0,
    trigger_off_db=8.0,
    min_active_frames=2,
    hold_seconds=1.5,
    smoothing_alpha=0.35,
    noise_quantile=0.20,
)

FREENET_PROFILE = BandProfile(
    name="FREENET",
    mode="channelized",
    start_hz=149_025_000,
    stop_hz=149_112_500,
    channel_width_hz=12_500,
    channels=[
        ChannelDef("FREENET1", 149_025_000, 12_500, label="Freenet K1"),
        ChannelDef("FREENET2", 149_037_500, 12_500, label="Freenet K2"),
        ChannelDef("FREENET3", 149_050_000, 12_500, label="Freenet K3"),
        ChannelDef("FREENET4", 149_087_500, 12_500, label="Freenet K4"),
        ChannelDef("FREENET5", 149_100_000, 12_500, label="Freenet K5"),
        ChannelDef("FREENET6", 149_112_500, 12_500, label="Freenet K6"),
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
    """Speichert letztes Spektrum für CLI/WebUI — ohne Riesen-FFT-Arrays (hängen sonst die WebUI)."""
    try:
        slim = _spectrum_for_persist(data)
        if _rtlsdr and hasattr(_rtlsdr, "_atomic_json"):
            _rtlsdr._atomic_json(SPECTRUM_FILE, slim)
            return
        tmp = SPECTRUM_FILE + ".tmp"
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        except OSError:
            pass
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(slim, f, ensure_ascii=False, separators=(",", ":"))
                f.flush()
            os.replace(tmp, SPECTRUM_FILE)
        except OSError:
            with open(SPECTRUM_FILE, "w", encoding="utf-8") as f:
                json.dump(slim, f, ensure_ascii=False, separators=(",", ":"))
                f.flush()
        try:
            os.chmod(SPECTRUM_FILE, 0o666)
        except OSError:
            pass
    except Exception:
        pass


_MAX_SPECTRUM_LIST = 128
_MAX_SPECTRUM_FILE_BYTES = 512_000


def _spectrum_for_persist(data: dict) -> dict:
    """Kürzt power/spectrum-Arrays — volle Kurven gehören in Export-Dateien, nicht in /tmp last."""
    if not isinstance(data, dict):
        return {"ok": False, "error": "invalid_spectrum_payload"}

    def _trim(obj, depth=0):
        if depth > 8:
            return None
        if isinstance(obj, dict):
            out = {}
            for k, v in obj.items():
                if k in ("spectrum_db", "power_db", "frames", "scores") and isinstance(v, list) and len(v) > _MAX_SPECTRUM_LIST:
                    out[k] = {"_omitted": True, "len": len(v)}
                else:
                    out[k] = _trim(v, depth + 1)
            return out
        if isinstance(obj, list):
            if len(obj) > _MAX_SPECTRUM_LIST:
                return {"_omitted": True, "len": len(obj), "head": obj[:8]}
            return [_trim(x, depth + 1) for x in obj]
        return obj

    slim = _trim(data)
    if isinstance(slim, dict):
        slim["_persisted_slim"] = True
    return slim if isinstance(slim, dict) else {"ok": False, "error": "trim_failed"}


def load_last_spectrum() -> dict:
    try:
        if not os.path.exists(SPECTRUM_FILE):
            return {}
        size = os.path.getsize(SPECTRUM_FILE)
        if size > _MAX_SPECTRUM_FILE_BYTES:
            # Alte Riesen-Snapshots nicht in den View-Model-Pfad laden (OOM / UI-Hang)
            return {
                "ok": False,
                "error": "spectrum_file_too_large",
                "size_bytes": size,
                "limit_bytes": _MAX_SPECTRUM_FILE_BYTES,
                "hint": "Datei löschen oder neuen Scan speichern (slim)",
            }
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
        lease_owner = f"spectrum:{id(self)}:{int(center_hz)}"
        last_err: Optional[Exception] = None
        for attempt in range(2):
            try:
                return self._capture_iq_once(
                    center_hz, sample_rate, sample_count, lease_owner
                )
            except Exception as e:
                last_err = e
                msg = str(e).lower()
                busyish = any(
                    x in msg
                    for x in ("busy", "timeout", "claim", "hängt", "failed to open")
                )
                if attempt == 0 and busyish and _rtlsdr and hasattr(
                    _rtlsdr, "recover_busy_device"
                ):
                    try:
                        _rtlsdr.recover_busy_device(
                            reason="spectrum_capture_retry", level="hard"
                        )
                        time.sleep(0.4)
                    except Exception:
                        pass
                    continue
                raise
        if last_err:
            raise last_err
        raise RuntimeError("capture_iq failed")

    def _capture_iq_once(
        self,
        center_hz: float,
        sample_rate: int,
        sample_count: int,
        lease_owner: str,
    ) -> bytes:
        if _rtlsdr:
            usb = _rtlsdr.detect_usb()
            if not usb.get("present"):
                raise RuntimeError("RTL-SDR nicht erkannt (USB)")
            # Robustes Warten auf Freigabe statt nur is_busy()-Check
            if _rtlsdr.is_busy():
                freed = _rtlsdr.wait_until_free(timeout=4.0, interval=0.2)
                if not freed:
                    raise RuntimeError("RTL-SDR belegt (Timeout 4s)")
            if hasattr(_rtlsdr, "claim_capture"):
                if not _rtlsdr.claim_capture(lease_owner, timeout_s=4.0):
                    raise RuntimeError("RTL-SDR belegt (capture lease)")

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

        cmd += ["-"]  # Output auf stdout (rtl_sdr braucht Dateiname, "-" = stdout)

        # Längere Captures (Pro-Watch-Block) brauchen mehr Zeit als Default 6s
        try:
            need_s = float(sample_count) / max(float(sample_rate), 1.0) + 5.0
        except Exception:
            need_s = self.timeout_s
        run_timeout = max(float(self.timeout_s), need_s, 8.0)

        try:
            try:
                cp = subprocess.run(cmd, capture_output=True, timeout=run_timeout)
            except FileNotFoundError:
                raise RuntimeError("rtl_sdr Binary nicht gefunden — bitte: sudo apt install rtl-sdr")
            except subprocess.TimeoutExpired:
                raise RuntimeError(f"rtl_sdr Timeout ({run_timeout:.1f}s) — Device hängt?")

            raw = cp.stdout or b""
            if not raw:
                err = (cp.stderr or b"").decode("utf-8", "ignore")[:240]
                if cp.returncode == 1 and ("busy" in err.lower() or "failed to open" in err.lower()):
                    raise RuntimeError(f"RTL-SDR Device busy: {err[:120]}")
                elif cp.returncode == 127 or not raw:
                    raise RuntimeError(f"rtl_sdr keine Daten (rc={cp.returncode}): {err[:120]}")
                raise RuntimeError(f"keine IQ-Daten ({err[:120]})")

            return raw
        finally:
            if _rtlsdr and hasattr(_rtlsdr, "release_capture"):
                try:
                    _rtlsdr.release_capture(lease_owner)
                except Exception:
                    pass


class StreamingRtlReader:
    """
    Ein rtl_sdr-Prozess für die Dauer eines Watch — Samples von stdout.
    Ermöglicht echte Early-Exits ohne erst den ganzen Block zu puffern.
    """

    def __init__(
        self,
        center_hz: float,
        sample_rate: int,
        ppm: int = 0,
        gain: int = -1,
        owner: str = "spectrum:stream",
        read_timeout_s: float = 3.0,
    ):
        self.center_hz = float(center_hz)
        self.sample_rate = int(sample_rate)
        self.ppm = int(ppm)
        self.gain = int(gain)
        self.owner = str(owner)
        self.read_timeout_s = float(read_timeout_s)
        self._proc: Optional[subprocess.Popen] = None

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False

    def open(self) -> None:
        if _rtlsdr:
            if hasattr(_rtlsdr, "detect_usb") and not _rtlsdr.detect_usb().get("present"):
                raise RuntimeError("RTL-SDR nicht erkannt (USB)")
            if hasattr(_rtlsdr, "is_busy") and _rtlsdr.is_busy():
                if not _rtlsdr.wait_until_free(timeout=4.0, interval=0.2):
                    raise RuntimeError("RTL-SDR belegt (Timeout 4s)")
            if hasattr(_rtlsdr, "claim_capture"):
                if not _rtlsdr.claim_capture(self.owner, timeout_s=4.0,
                                             mode="spectrum_capture"):
                    raise RuntimeError("RTL-SDR belegt (capture lease)")
        cmd = [
            "rtl_sdr",
            "-f", str(int(self.center_hz)),
            "-s", str(int(self.sample_rate)),
        ]
        if self.ppm:
            cmd += ["-p", str(self.ppm)]
        if self.gain >= 0:
            cmd += ["-g", str(self.gain)]
        cmd += ["-"]
        try:
            self._proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                bufsize=0,
                start_new_session=True,
            )
        except FileNotFoundError:
            self.close()
            raise RuntimeError("rtl_sdr Binary nicht gefunden")
        except Exception:
            self.close()
            raise

    def read_u8_iq(self, sample_count: int) -> bytes:
        if not self._proc or not self._proc.stdout:
            raise RuntimeError("stream nicht offen")
        need = max(1, int(sample_count)) * 2
        buf = bytearray()
        deadline = time.time() + self.read_timeout_s
        fd = self._proc.stdout.fileno()
        while len(buf) < need and time.time() < deadline:
            remaining = deadline - time.time()
            if remaining <= 0:
                break
            try:
                ready, _, _ = select.select([fd], [], [], min(0.25, remaining))
            except (ValueError, OSError):
                break
            if not ready:
                if self._proc.poll() is not None:
                    break
                continue
            try:
                chunk = os.read(fd, need - len(buf))
            except OSError:
                break
            if not chunk:
                if self._proc.poll() is not None:
                    break
                continue
            buf.extend(chunk)
        if len(buf) < need:
            raise RuntimeError(
                f"stream short read ({len(buf)}/{need} bytes) — Device hängt?"
            )
        return bytes(buf)

    def close(self) -> None:
        proc = self._proc
        self._proc = None
        if proc is not None:
            pid = getattr(proc, "pid", None)
            try:
                if proc.stdout:
                    try:
                        proc.stdout.close()
                    except Exception:
                        pass
                try:
                    proc.terminate()
                except Exception:
                    pass
                try:
                    proc.wait(timeout=0.8)
                except Exception:
                    try:
                        proc.kill()
                    except Exception:
                        pass
                    try:
                        proc.wait(timeout=0.5)
                    except Exception:
                        pass
                # Prozessgruppe (start_new_session) — Orphans sicher killen
                if pid:
                    try:
                        os.killpg(pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    except Exception:
                        try:
                            os.kill(pid, signal.SIGKILL)
                        except Exception:
                            pass
            except Exception:
                pass
        if _rtlsdr and hasattr(_rtlsdr, "release_capture"):
            try:
                _rtlsdr.release_capture(self.owner)
            except Exception:
                pass


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
        # Best-Channel: schwächere direkte Nachbarn unterdrücken (Bleed)
        if len(out) >= 2:
            best = out[0]
            kept = [best]
            for c in out[1:]:
                sep = abs(float(c.freq_hz) - float(best.freq_hz))
                neigh_lim = max(float(best.bandwidth_hz), float(c.bandwidth_hz)) * 1.6
                if sep <= neigh_lim and float(c.relative_db) < float(best.relative_db):
                    continue
                kept.append(c)
            out = kept
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

        # Ein IQ-Block pro Watch (statt rtl_sdr pro Frame) — weniger USB-Stress.
        # Max. 2.5s Rohdaten (~1.3 MB bei 256 kHz), intern in FFT-Frames schneiden.
        watch_s = max(0.15, float(profile.watch_seconds))
        block_s = min(watch_s, 2.5)
        block_samples = int(config.sample_rate * block_s)
        hop_samples = int(config.sample_rate * (config.frame_ms / 1000.0))
        hop_samples = max(hop_samples, config.fft_size)
        block_samples = max(block_samples, hop_samples + config.fft_size)

        # Profil-FFT muss dem Processor entsprechen (Bug: build_default_watcher
        # nutzte 512, PMR446_PROFILE 2048 — compute_frame schnitt auf 512).
        fft_processor = self.fft_processor
        if (int(getattr(fft_processor, "fft_size", 0) or 0) != int(config.fft_size)
                or abs(float(getattr(fft_processor, "smoothing_alpha", 0.35))
                       - float(config.smoothing_alpha)) > 1e-6):
            fft_processor = FFTProcessor(
                fft_size=config.fft_size,
                smoothing_alpha=config.smoothing_alpha,
            )

        analyzer = ChannelAnalyzer(profile.channels)
        tracker = ActivityTracker(profile)

        started = time.time()
        frames_processed = 0
        early_exit = False
        capture_mode = "block"
        stream_error = ""

        debug_frames: list[dict[str, Any]] = []
        debug_scores: list[dict[str, Any]] = []
        bin_map_cached: Optional[dict[str, tuple[int, int]]] = None

        def _ingest_frame(chunk: bytes, ts: float) -> bool:
            """FFT + Tracker; True bei Early-Exit."""
            nonlocal frames_processed, early_exit, bin_map_cached
            frame = fft_processor.compute_frame(
                raw_iq=chunk,
                center_hz=config.center_hz,
                sample_rate=config.sample_rate,
            )
            frame.timestamp = float(ts)

            noise_floor = self.noise_estimator.estimate(frame.power_db)
            frame.noise_floor_db = noise_floor

            if bin_map_cached is None:
                bin_map_cached = analyzer.map_channel_bins(frame)

            channel_powers = analyzer.integrate_channel_power(frame, bin_map_cached)
            scores = analyzer.score_channels(channel_powers, noise_floor)

            for ch in profile.channels:
                if ch.name not in channel_powers:
                    continue
                tracker.update_channel(
                    ts=frame.timestamp,
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

            elapsed_ms = (frame.timestamp - started) * 1000.0
            if elapsed_ms >= 300.0 and frames_processed >= max(1, int(profile.min_active_frames)):
                cands_now = tracker.build_candidates(frame.timestamp)
                if cands_now:
                    best_now = cands_now[0]
                    margin = 8.0
                    second_rel = (
                        float(cands_now[1].relative_db) if len(cands_now) > 1 else -999.0
                    )
                    if (float(best_now.relative_db) >= float(profile.trigger_on_db) + margin
                            and float(best_now.relative_db) - second_rel >= 3.0
                            and int(best_now.active_frames) >= int(profile.min_active_frames)):
                        early_exit = True
            return early_exit

        # Streaming nur mit echtem RTL-Backend (Tests/Fake → Block).
        # Abschaltbar: PIDRIVE_SPECTRUM_STREAM=0
        want_stream = (
            isinstance(self.backend, RTLSDRBackend)
            and os.environ.get("PIDRIVE_SPECTRUM_STREAM", "1").strip() != "0"
        )
        if want_stream:
            skip_samples = max(0, int(hop_samples) - int(config.fft_size))
            try:
                with StreamingRtlReader(
                    center_hz=config.center_hz,
                    sample_rate=config.sample_rate,
                    ppm=int(getattr(self.backend, "ppm", 0) or 0),
                    gain=int(getattr(self.backend, "gain", -1)),
                    owner=f"spectrum:stream:{int(config.center_hz)}",
                    read_timeout_s=max(3.0, float(watch_s) + 2.0),
                ) as reader:
                    capture_mode = "stream"
                    # Watch-Fenster erst nach erstem Frame (rtl_sdr-Startup zählt nicht)
                    armed = False
                    deadline = 0.0
                    while not early_exit:
                        chunk = reader.read_u8_iq(config.fft_size)
                        now = time.time()
                        if not armed:
                            started = now
                            deadline = started + watch_s
                            armed = True
                        if _ingest_frame(chunk, now):
                            break
                        if skip_samples > 0 and time.time() < deadline and not early_exit:
                            try:
                                reader.read_u8_iq(skip_samples)
                            except Exception:
                                break
                        if time.time() >= deadline:
                            break
                if frames_processed < 1:
                    raise RuntimeError("stream: keine Frames")
            except Exception as e:
                stream_error = str(e)[:160]
                capture_mode = "block"
                frames_processed = 0
                early_exit = False
                debug_frames.clear()
                debug_scores.clear()
                bin_map_cached = None
                tracker = ActivityTracker(profile)
                started = time.time()
                # Stream-Fehler oft = verwaister/hängender Stick → vor Block freigeben
                if _rtlsdr and hasattr(_rtlsdr, "recover_busy_device"):
                    try:
                        _rtlsdr.recover_busy_device(
                            reason="stream_fallback", level="hard"
                        )
                        time.sleep(0.3)
                    except Exception:
                        pass

        if capture_mode == "block":
            raw = self.backend.capture_iq(
                center_hz=config.center_hz,
                sample_rate=config.sample_rate,
                sample_count=block_samples,
            )
            bytes_per_sample = 2
            fft_bytes = int(config.fft_size) * bytes_per_sample
            hop_bytes = int(hop_samples) * bytes_per_sample
            raw_len = len(raw)
            offset = 0
            frame_idx = 0

            while offset + fft_bytes <= raw_len:
                chunk = raw[offset:offset + fft_bytes]
                offset += hop_bytes
                ts = started + (frame_idx * hop_samples / float(config.sample_rate))
                frame_idx += 1
                if _ingest_frame(chunk, ts):
                    break

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
                "effective_fft_size": int(fft_processor.fft_size),
                "frame_ms": int(config.frame_ms),
                "span_hz": int(compute_span_for_channels(profile.channels)),
                "early_exit": bool(early_exit),
                "capture_mode": capture_mode,
                "stream_error": stream_error or None,
                "block_samples": int(block_samples),
                "hop_samples": int(hop_samples),
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

# v0.10.0: Standard-FFT-Groesse, nicht an PMR-Profil gebunden
_DEFAULT_FFT_SIZE = 512  # Pi 3B: Kompromiss Aufloesung/CPU


def build_default_watcher(ppm: int = 0, gain: int = -1) -> SpectrumWatcher:
    """Watcher mit neutralen Defaults. Profil-FFT aus BandProfile via watch_channels()."""
    backend = RTLSDRBackend(ppm=ppm, gain=gain)
    fft = FFTProcessor(fft_size=_DEFAULT_FFT_SIZE, smoothing_alpha=0.35)
    noise = NoiseEstimator(quantile=0.20)
    return SpectrumWatcher(backend, fft, noise)


def watch_pmr446(ppm: int = 0, gain: int = -1, debug: bool = False,
                 settings: dict = None) -> DetectionResult:
    """v0.10.0: Rate-Limit Guard fuer Pi 3B. settings['spectrum_watch_seconds'] konfigurierbar."""
    if not _check_rate_limit():
        return DetectionResult(
                found=False, best_candidate=None, candidates=[],
                frames_processed=0, watch_started_ts=0.0, watch_ended_ts=0.0,
                note="rate_limited", debug={"band": PMR446_PROFILE.name})
    watcher = build_default_watcher(ppm=ppm, gain=gain)
    profile = PMR446_PROFILE
    if settings is not None:
        ws = settings.get("spectrum_watch_seconds")
        if ws and float(ws) > 0:
            import copy
            profile = copy.replace(profile, watch_seconds=float(ws))
    return watcher.watch_channels(profile, debug=debug)


def watch_freenet(ppm: int = 0, gain: int = -1, debug: bool = False,
                  settings: dict = None) -> DetectionResult:
    """v0.10.0: Rate-Limit Guard fuer Pi 3B. settings['spectrum_watch_seconds'] konfigurierbar."""
    if not _check_rate_limit():
        return DetectionResult(
                found=False, best_candidate=None, candidates=[],
                frames_processed=0, watch_started_ts=0.0, watch_ended_ts=0.0,
                note="rate_limited", debug={"band": FREENET_PROFILE.name})
    watcher = build_default_watcher(ppm=ppm, gain=gain)
    profile = FREENET_PROFILE
    if settings is not None:
        ws = settings.get("spectrum_watch_seconds")
        if ws and float(ws) > 0:
            import copy
            profile = copy.replace(profile, watch_seconds=float(ws))
    return watcher.watch_channels(profile, debug=debug)


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


def _fft_power_db_averaged(samples, frame_len: int, avg_frames: int):
    """
    Mehrere FFT-Frames gleicher Länge → Mittelung der linearen Leistung (VBW-ähnlich).
    RBW bleibt = sample_rate / frame_len (nicht gröber durch Splitten).
    """
    if np is None:
        raise RuntimeError("numpy fehlt — bitte installieren: apt install python3-numpy")
    if not samples:
        return [], 0, 0

    frame_len = int(frame_len)
    avg_frames = max(1, int(avg_frames))
    if frame_len < 64:
        db, n = _fft_power_db_legacy(samples)
        return db, n, 1

    arr = np.asarray(samples, dtype=np.complex64)
    if arr.size < frame_len:
        db, n = _fft_power_db_legacy(samples)
        return db, n, 1

    window = np.hanning(frame_len).astype(np.float32)
    acc = None
    used = 0
    max_frames = min(avg_frames, arr.size // frame_len)
    for i in range(max_frames):
        chunk = arr[i * frame_len:(i + 1) * frame_len]
        if chunk.size < frame_len:
            break
        fft = np.fft.fftshift(np.fft.fft(chunk * window))
        power = np.maximum(np.abs(fft) ** 2, 1e-12).astype(np.float64)
        if acc is None:
            acc = power
        else:
            acc += power
        used += 1

    if acc is None or used < 1:
        db, n = _fft_power_db_legacy(samples)
        return db, n, 1

    acc /= float(used)
    db = (10.0 * np.log10(acc)).tolist()
    return db, len(db), used


def _parabolic_delta(y1: float, y2: float, y3: float) -> float:
    """Sub-Bin-Offset ∈ [-0.5, 0.5] aus drei benachbarten Bin-Werten (dB ok)."""
    denom = (y1 - 2.0 * y2 + y3)
    if abs(denom) < 1e-12:
        return 0.0
    delta = 0.5 * (y1 - y3) / denom
    if delta > 0.5:
        return 0.5
    if delta < -0.5:
        return -0.5
    return float(delta)


def _dedupe_peaks(peaks, resolution_mhz=0.1):
    buckets = {}
    for p in peaks:
        key = round(round(float(p["freq_mhz"]) / resolution_mhz) * resolution_mhz, 6)
        if key not in buckets:
            buckets[key] = {
                "freq_mhz": float(p["freq_mhz"]),
                "db": p["db"],
                "hits": 1,
                "interpolated": bool(p.get("interpolated")),
            }
        else:
            buckets[key]["hits"] += 1
            if p["db"] > buckets[key]["db"]:
                buckets[key]["db"] = p["db"]
                buckets[key]["freq_mhz"] = float(p["freq_mhz"])
                buckets[key]["interpolated"] = bool(p.get("interpolated"))
    result = list(buckets.values())
    result.sort(key=lambda x: x["db"], reverse=True)
    return result


def _find_peaks(spectrum_db, center_mhz, sample_rate_hz, min_db=None, max_peaks=20,
                min_distance_bins=8, interpolate=True):
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
            delta = 0.0
            db_est = float(v)
            if interpolate:
                delta = _parabolic_delta(
                    float(spectrum_db[i - 1]), float(v), float(spectrum_db[i + 1])
                )
                # Peak-Höhe grob interpoliert
                y1, y2, y3 = float(spectrum_db[i - 1]), float(v), float(spectrum_db[i + 1])
                db_est = y2 - 0.25 * (y1 - y3) * delta
            offset_hz = (i + delta - n / 2.0) * bin_hz
            freq_mhz = center_mhz + (offset_hz / 1e6)
            peaks.append({
                "bin": i,
                "delta_bin": round(delta, 4),
                "freq_mhz": round(freq_mhz, 6),
                "db": round(db_est, 2),
                "interpolated": bool(interpolate and abs(delta) > 1e-6),
            })

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


def _kill_rtl_sdr_procs():
    """Nur Prozesse namens rtl_sdr beenden (kein pkill -f — trifft sonst die eigene Shell)."""
    try:
        out = subprocess.check_output(["pgrep", "-x", "rtl_sdr"], text=True, timeout=2)
    except Exception:
        return
    for pid in out.split():
        try:
            os.kill(int(pid), 9)
        except Exception:
            pass


def _run_rtl_sdr_iq(center_hz: int, sample_rate_hz: int, sample_count: int,
                    ppm: int = 0, gain: int = -1, timeout: float = 20.0) -> bytes:
    """Ein rtl_sdr-Capture nach stdout.

    Hard-Cap 65536: auf diesem Stick streamt -n 131072 endlos (Timeout), 65536 ist stabil.
    Feinere RBW → Sample-Rate senken oder Avg erhöhen, nicht mehr Samples.
    """
    n = max(4096, min(int(sample_count), 65536))
    cmd = [
        "rtl_sdr",
        "-f", str(int(center_hz)),
        "-s", str(int(sample_rate_hz)),
        "-n", str(n),
    ]
    if int(ppm) != 0:
        cmd += ["-p", str(int(ppm))]
    if int(gain) >= 0:
        cmd += ["-g", str(int(gain))]
    cmd += ["-"]
    t_cap = n / max(float(sample_rate_hz), 1.0)
    to = max(float(timeout), 8.0 + t_cap * 10.0)
    try:
        cp = subprocess.run(cmd, capture_output=True, timeout=to)
    except subprocess.TimeoutExpired:
        _kill_rtl_sdr_procs()
        raise
    if not cp.stdout:
        err = (cp.stderr or b"").decode("utf-8", "ignore")[:300]
        raise RuntimeError(err or "keine IQ-Daten")
    return cp.stdout


def capture_spectrum(center_mhz, sample_rate_hz=2048000, sample_count=65536,
                     ppm=0, gain=-1, peak_threshold_db=None, avg_frames=1,
                     interpolate_peaks=True):
    if _rtlsdr:
        usb = _rtlsdr.detect_usb()
        if not usb.get("present"):
            return {"ok": False, "error": "RTL-SDR nicht erkannt"}
        # Stale Locks aufräumen; kurz auf Freigabe warten (wie RTLSDRBackend)
        if hasattr(_rtlsdr, "clear_stale_lock"):
            try:
                _rtlsdr.clear_stale_lock()
            except Exception:
                pass
        if _rtlsdr.is_busy():
            freed = False
            if hasattr(_rtlsdr, "wait_until_free"):
                try:
                    freed = bool(_rtlsdr.wait_until_free(timeout=4.0, interval=0.2))
                except Exception:
                    freed = False
            if not freed and _rtlsdr.is_busy():
                return {"ok": False, "error": "RTL-SDR belegt"}

    frame_n = max(4096, min(int(sample_count), 65536))
    avg_frames = max(1, min(int(avg_frames or 1), 16))
    center_hz = int(float(center_mhz) * 1e6)
    sr = int(sample_rate_hz)

    # Averaging: mehrere kurze Captures (nicht ein Riesen--n — hängt auf manchen Sticks)
    power_acc = None
    frames_used = 0
    last_err = None
    iq_total = 0

    for _ in range(avg_frames):
        try:
            raw = _run_rtl_sdr_iq(center_hz, sr, frame_n, ppm=ppm, gain=gain)
        except subprocess.TimeoutExpired:
            last_err = "rtl_sdr Timeout"
            _kill_rtl_sdr_procs()
            break
        except Exception as e:
            last_err = str(e)
            break

        samples = _u8_iq_to_complex_legacy(raw)
        iq_total += len(samples)
        if np is None:
            return {"ok": False, "error": "numpy fehlt — bitte installieren: apt install python3-numpy"}
        if len(samples) < frame_n // 2:
            last_err = "zu wenige IQ-Samples"
            break

        # Frame auf frame_n begrenzen / padden nicht — FFT über verfügbare Länge,
        # aber für Average gleiche Länge erzwingen
        use_n = min(len(samples), frame_n)
        chunk = samples[:use_n]
        if use_n < frame_n:
            # zu kurz: einzelnes Legacy-FFT, kein Average-Mix unterschiedlicher Längen
            try:
                spectrum_db, n_bins = _fft_power_db_legacy(chunk)
            except RuntimeError as e:
                return {"ok": False, "error": str(e)}
            frames_used = 1
            peaks = _find_peaks(
                spectrum_db, float(center_mhz), sr,
                peak_threshold_db, interpolate=bool(interpolate_peaks),
            )
            bin_hz = (sr / n_bins) if n_bins else 0
            result = {
                "ok": True, "mode": "single", "center_mhz": float(center_mhz),
                "sample_rate_hz": sr, "sample_count": use_n, "sample_count_iq": iq_total,
                "avg_frames": 1, "ppm": int(ppm), "gain": int(gain),
                "bin_hz": bin_hz, "rbw_hz": round(bin_hz, 3) if bin_hz else 0,
                "peaks": peaks, "spectrum_db": spectrum_db, "ts": int(time.time()),
                "note": "kurzes Frame — Average abgebrochen",
            }
            save_last_spectrum(result)
            return result

        arr = np.asarray(chunk, dtype=np.complex64)
        window = np.hanning(frame_n).astype(np.float32)
        fft = np.fft.fftshift(np.fft.fft(arr * window))
        power = np.maximum(np.abs(fft) ** 2, 1e-12).astype(np.float64)
        if power_acc is None:
            power_acc = power
        else:
            power_acc += power
        frames_used += 1

    if power_acc is None or frames_used < 1:
        return {"ok": False, "error": last_err or "keine IQ-Daten"}

    power_acc /= float(frames_used)
    spectrum_db = (10.0 * np.log10(power_acc)).tolist()
    n_bins = len(spectrum_db)

    peaks = _find_peaks(
        spectrum_db, float(center_mhz), sr,
        peak_threshold_db, interpolate=bool(interpolate_peaks),
    )

    bin_hz = (sr / n_bins) if n_bins else 0
    result = {
        "ok": True,
        "mode": "single",
        "center_mhz": float(center_mhz),
        "sample_rate_hz": sr,
        "sample_count": int(frame_n),
        "sample_count_iq": iq_total,
        "avg_frames": int(frames_used),
        "ppm": int(ppm),
        "gain": int(gain),
        "bin_hz": bin_hz,
        "rbw_hz": round(bin_hz, 3) if bin_hz else 0,
        "peaks": peaks,
        "spectrum_db": spectrum_db,
        "ts": int(time.time()),
    }
    save_last_spectrum(result)
    return result


# RTL-SDR-übliche Sample-Rates (2.4 Msps weggelassen — auf manchen Sticks problematisch)
_RTL_SAMPLE_RATES = (
    250_000,
    1_024_000,
    1_536_000,
    1_792_000,
    1_920_000,
    2_048_000,
)


def _pick_sample_rate(span_hz: float, preferred: Optional[int] = None) -> int:
    """Wählt eine RTL-Sample-Rate, die span_hz (mit Rand) abdeckt."""
    if preferred and int(preferred) > 0:
        return int(preferred)
    need = max(float(span_hz) * 1.12, 200_000.0)
    for sr in _RTL_SAMPLE_RATES:
        if sr >= need:
            return int(sr)
    return int(_RTL_SAMPLE_RATES[-1])


def _crop_spectrum(spectrum_db, center_mhz, sample_rate_hz, start_mhz, stop_mhz):
    """Schneidet spectrum_db auf [start_mhz, stop_mhz] zu. Gibt (cropped, bin_hz, f0)."""
    if not spectrum_db:
        return [], 0.0, float(start_mhz)
    n = len(spectrum_db)
    bin_hz = float(sample_rate_hz) / n
    f0_full = float(center_mhz) - (float(sample_rate_hz) / 2.0) / 1e6
    i0 = max(0, int(math.floor((float(start_mhz) - f0_full) * 1e6 / bin_hz)))
    i1 = min(n, int(math.ceil((float(stop_mhz) - f0_full) * 1e6 / bin_hz)))
    if i1 <= i0:
        return [], bin_hz, float(start_mhz)
    cropped = spectrum_db[i0:i1]
    f0 = f0_full + i0 * bin_hz / 1e6
    return cropped, bin_hz, f0


def _peaks_in_range(peaks, start_mhz, stop_mhz):
    out = []
    for p in peaks or []:
        f = p.get("freq_mhz")
        if f is None:
            continue
        if float(start_mhz) <= float(f) <= float(stop_mhz):
            out.append(p)
    return out


def capture_range(start_mhz, stop_mhz, sample_rate_hz=None, sample_count=65536,
                  ppm=0, gain=-1, peak_threshold_db=None, step_mhz=None,
                  avg_frames=1, interpolate_peaks=True):
    """
    Spektrum über [start_mhz, stop_mhz].

    Schmal genug für eine RTL-Fensterbreite → ein Capture + Crop (durchgehender Plot).
    Breiter → gestaffelte Fenster, gestitchtes Spektrum.
    step_mhz steuert nur den Multi-Fenster-Fall (Default: ~80 % der Sample-Rate).
    """
    start = float(start_mhz)
    stop = float(stop_mhz)
    if stop <= start:
        return {"ok": False, "error": "stop_mhz muss größer als start_mhz sein"}

    span_hz = (stop - start) * 1e6
    center = (start + stop) / 2.0
    n_samp = int(sample_count) if sample_count else 65536
    n_samp = max(4096, min(n_samp, 65536))
    avg_frames = max(1, min(int(avg_frames or 1), 32))

    preferred = int(sample_rate_hz) if sample_rate_hz else None
    sr = _pick_sample_rate(span_hz, preferred)

    def _peaks_from_crop(cropped, bin_hz, f0):
        if not cropped or bin_hz <= 0:
            return []
        n = len(cropped)
        # Äquivalente Mitte/Rate für Peak-Finder auf dem Crop
        equiv_sr = bin_hz * n
        equiv_center = f0 + (n * bin_hz / 2.0) / 1e6
        return _find_peaks(
            cropped, equiv_center, equiv_sr,
            peak_threshold_db, interpolate=bool(interpolate_peaks),
        )

    # Ein Fenster reicht (mit etwas Rand)
    if span_hz <= sr * 0.98:
        one = capture_spectrum(
            center, sample_rate_hz=sr, sample_count=n_samp,
            ppm=ppm, gain=gain, peak_threshold_db=peak_threshold_db,
            avg_frames=avg_frames, interpolate_peaks=interpolate_peaks,
        )
        if not one.get("ok"):
            return one
        cropped, bin_hz, f0 = _crop_spectrum(
            one.get("spectrum_db") or [], center, sr, start, stop
        )
        peaks = _peaks_from_crop(cropped, bin_hz, f0)
        peaks = _peaks_in_range(peaks, start, stop)
        rbw_hz = bin_hz if bin_hz else (sr / max(len(cropped), 1))
        result = {
            "ok": True,
            "mode": "range",
            "start_mhz": start,
            "stop_mhz": stop,
            "center_mhz": round(center, 6),
            "sample_rate_hz": sr,
            "sample_count": n_samp,
            "avg_frames": one.get("avg_frames", avg_frames),
            "ppm": int(ppm),
            "gain": int(gain),
            "bin_hz": rbw_hz,
            "rbw_hz": round(rbw_hz, 3),
            "f0_mhz": round(f0, 6),
            "span_mhz": round(stop - start, 6),
            "windows_total": 1,
            "windows_ok": 1,
            "peaks": peaks,
            "spectrum_db": cropped,
            "ts": int(time.time()),
        }
        save_last_spectrum(result)
        return result

    # Mehrere Fenster stitchen
    usable = sr * 0.85  # Überlappung gegen Kantenartefakte
    if step_mhz is not None and float(step_mhz) > 0:
        step_hz = float(step_mhz) * 1e6
    else:
        step_hz = usable
    step_hz = max(step_hz, sr * 0.25)

    centers = []
    # Zentren so wählen, dass Start/Stop abgedeckt sind
    first = start + (sr / 2.0) / 1e6 * 0.98
    last = stop - (sr / 2.0) / 1e6 * 0.98
    if last < first:
        first = last = center
    c = first
    while c <= last + 1e-9:
        centers.append(round(c, 6))
        c += step_hz / 1e6
    if not centers or abs(centers[-1] - last) > 1e-4:
        centers.append(round(last, 6))

    # Ziel-Raster über den gewünschten Bereich
    est_bins = max(n_samp, 4096)
    bin_hz = sr / est_bins
    n_out = max(2, int(math.ceil(span_hz / bin_hz)))
    bin_hz = span_hz / n_out
    acc = [0.0] * n_out
    wgt = [0.0] * n_out
    all_peaks = []
    windows = []
    avg_used = 0

    for c_mhz in centers:
        one = capture_spectrum(
            c_mhz, sample_rate_hz=sr, sample_count=n_samp,
            ppm=ppm, gain=gain, peak_threshold_db=peak_threshold_db,
            avg_frames=avg_frames, interpolate_peaks=interpolate_peaks,
        )
        if not one.get("ok"):
            windows.append({"center_mhz": c_mhz, "ok": False, "error": one.get("error", "?")})
            continue
        avg_used = max(avg_used, int(one.get("avg_frames") or 1))
        spec = one.get("spectrum_db") or []
        n = len(spec)
        if n < 2:
            windows.append({"center_mhz": c_mhz, "ok": False, "error": "zu wenig Bins"})
            continue
        win_bin = sr / n
        f0w = c_mhz - (sr / 2.0) / 1e6
        for i, db in enumerate(spec):
            f = f0w + i * win_bin / 1e6
            if f < start or f > stop:
                continue
            j = int((f - start) * 1e6 / bin_hz)
            if j < 0 or j >= n_out:
                continue
            # Soft-Edges: Gewicht nahe Fenstermitte höher
            edge = abs(i - n / 2) / (n / 2)
            w = max(0.15, 1.0 - edge * 0.7)
            acc[j] += float(db) * w
            wgt[j] += w
        peaks = _peaks_in_range(one.get("peaks") or [], start, stop)
        all_peaks.extend(peaks)
        windows.append({
            "center_mhz": c_mhz, "ok": True,
            "peak_count": len(peaks), "top_peaks": peaks[:8],
        })

    spectrum_db = []
    for i in range(n_out):
        if wgt[i] > 0:
            spectrum_db.append(acc[i] / wgt[i])
        else:
            spectrum_db.append(-120.0)

    # Peaks final auf gestitchtem Spektrum (bessere Interpolation)
    peaks = _peaks_from_crop(spectrum_db, bin_hz, start) if spectrum_db else []
    peaks = _peaks_in_range(peaks, start, stop)
    if not peaks and all_peaks:
        peaks = _dedupe_peaks(all_peaks, resolution_mhz=max(0.001, bin_hz / 1e6 * 4))

    windows_ok = sum(1 for w in windows if w.get("ok"))
    result = {
        "ok": windows_ok > 0,
        "mode": "range",
        "start_mhz": start,
        "stop_mhz": stop,
        "center_mhz": round(center, 6),
        "sample_rate_hz": sr,
        "sample_count": n_samp,
        "avg_frames": avg_used or avg_frames,
        "step_mhz": round(step_hz / 1e6, 6),
        "ppm": int(ppm),
        "gain": int(gain),
        "bin_hz": bin_hz,
        "rbw_hz": round(bin_hz, 3),
        "f0_mhz": start,
        "span_mhz": round(stop - start, 6),
        "windows_total": len(centers),
        "windows_ok": windows_ok,
        "windows": windows,
        "peaks": peaks[:40],
        "spectrum_db": spectrum_db if windows_ok else [],
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

    windows_ok = sum(1 for w in sweep if w.get("ok"))
    result = {
        "ok": windows_ok > 0,
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
        "windows_ok": windows_ok,
        "windows": sweep,
        "candidates": confirmed[:40],
        "candidates_weak": unconfirmed[:20],
        "candidates_all_count": len(fm_candidates),
        "ts": int(time.time()),
    }
    save_last_spectrum(result)
    return result


# Bekannte UKW-Labels (Allgäu / Nutzer) — nur Annotation, kein Filter
_FM_KNOWN_LABELS = {
    88.7: "Bayern 2 (Grünten)",
    90.2: "RT1",
    90.7: "Bayern 1 (Grünten)",
    95.8: "Bayern 3 (Grünten)",
    96.0: "Bayern 2? (Hühnerberg ~96.1)",
    96.1: "Bayern 2 (Hühnerberg)",
    98.5: "Bayern 3",
    100.2: "FM4 (ORF)",
    100.7: "FM4?",
    100.8: "FM4?",
    101.0: "BR Klassik (Grünten)",
    103.0: "SWR3",
    104.4: "Antenne Bayern",
    106.9: "BR24 / ex B5 (Grünten)",
    107.6: "BR24 (Hühnerberg)",
}


def _channel_energy(spec_db, start_mhz, bin_hz, f_c, half_khz=75.0):
    if not spec_db or bin_hz <= 0:
        return None
    lo = f_c - half_khz / 1000.0
    hi = f_c + half_khz / 1000.0
    acc = 0.0
    n = 0
    peak = -1e9
    peak_f = None
    for i, db in enumerate(spec_db):
        f = start_mhz + i * bin_hz / 1e6
        if lo <= f <= hi:
            acc += 10.0 ** (float(db) / 10.0)
            n += 1
            if db > peak:
                peak = float(db)
                peak_f = f
    if n == 0:
        return None
    return {
        "mean_db": 10.0 * math.log10(acc / n),
        "peak_db": peak,
        "peak_f": peak_f,
    }


def _merge_channel_hits(hits, merge_mhz=0.18):
    if not hits:
        return []
    hits = sorted(hits, key=lambda h: h["f"])
    groups = [[hits[0]]]
    for h in hits[1:]:
        if h["f"] - groups[-1][-1]["f"] <= merge_mhz:
            groups[-1].append(h)
        else:
            groups.append([h])
    out = []
    for g in groups:
        wsum = 0.0
        fsum = 0.0
        best = g[0]
        for h in g:
            w = 10.0 ** (h["mean_db"] / 10.0)
            wsum += w
            fsum += h["f"] * w
            if h["mean_db"] > best["mean_db"]:
                best = h
        fc = fsum / wsum if wsum else best["f"]
        label = None
        for fk, name in _FM_KNOWN_LABELS.items():
            if abs(fc - fk) <= 0.05 or abs(best["f"] - fk) <= 0.05:
                label = name
                break
        out.append({
            "freq_mhz": round(fc, 3),
            "chan_mhz": best["f"],
            "mean_db": round(best["mean_db"], 2),
            "peak_db": round(best["peak_db"], 2),
            "n_chans": len(g),
            "label": label,
        })
    out.sort(key=lambda x: -x["mean_db"])
    return out


def scan_fm_channels(start_mhz=87.5, stop_mhz=108.0, top_n=10,
                     ppm=0, gain=25, avg_frames=2, sample_count=32768,
                     thresh_db_over_floor=10.0, grid_mhz=0.1,
                     sample_rate_hz=None):
    """
    Praxistauglicher UKW-Scan: Range-Capture → 100-kHz-Kanalenergie → Cluster.
    Liefert Peaks/Cluster (Sender-Kandidaten), nicht jeden FFT-Bin-Spike.
    """
    start = float(start_mhz)
    stop = float(stop_mhz)
    if stop <= start:
        return {"ok": False, "error": "stop_mhz muss größer als start_mhz sein"}

    top_n = max(1, min(int(top_n), 50))
    rng = capture_range(
        start_mhz=start, stop_mhz=stop,
        sample_rate_hz=sample_rate_hz,
        sample_count=sample_count,
        ppm=ppm, gain=gain, avg_frames=avg_frames,
    )
    if not rng.get("ok"):
        return rng

    spec = rng.get("spectrum_db") or []
    f0 = float(rng.get("f0_mhz") or start)
    bin_hz = float(rng.get("bin_hz") or 0)
    if not spec or bin_hz <= 0:
        return {"ok": False, "error": "kein Spektrum für Kanalenergie", "raw": rng}

    srt = sorted(spec)
    floor = srt[max(0, len(srt) // 5)]
    thresh = floor + float(thresh_db_over_floor)

    hits = []
    f = math.floor(start * 10 + 1e-9) / 10.0
    while f <= stop + 1e-9:
        e = _channel_energy(spec, f0, bin_hz, f, half_khz=75.0)
        if e and e["mean_db"] >= thresh:
            hits.append({
                "f": round(f, 1),
                "mean_db": e["mean_db"],
                "peak_db": e["peak_db"],
            })
        f = round(f + float(grid_mhz), 1)

    clusters = _merge_channel_hits(hits, merge_mhz=0.18)
    peaks = clusters[:top_n]

    result = {
        "ok": True,
        "mode": "fm_channels",
        "start_mhz": start,
        "stop_mhz": stop,
        "ppm": int(ppm),
        "gain": int(gain),
        "avg_frames": rng.get("avg_frames", avg_frames),
        "sample_rate_hz": rng.get("sample_rate_hz"),
        "rbw_hz": rng.get("rbw_hz"),
        "floor_db": round(floor, 2),
        "thresh_db": round(thresh, 2),
        "grid_hits": len(hits),
        "peak_count": len(peaks),
        "peaks": peaks,
        "peaks_all_count": len(clusters),
        "windows_ok": rng.get("windows_ok"),
        "windows_total": rng.get("windows_total"),
        "ts": int(time.time()),
    }
    save_last_spectrum({**result, "spectrum_db": spec, "f0_mhz": f0, "bin_hz": bin_hz})
    return result


def peek_fm_channel(freq_mhz, ppm=0, gain=25, avg_frames=2, sample_count=32768):
    """Einzelkanal prüfen (Offset-Fenster, vermeidet DC auf dem Träger)."""
    f = float(freq_mhz)
    start = round(f - 0.2, 3)
    stop = round(f + 0.5, 3)
    rng = capture_range(
        start_mhz=start, stop_mhz=stop,
        sample_rate_hz=1_024_000,
        sample_count=sample_count,
        ppm=ppm, gain=gain, avg_frames=avg_frames,
    )
    if not rng.get("ok"):
        return rng
    spec = rng.get("spectrum_db") or []
    f0 = float(rng.get("f0_mhz") or start)
    bin_hz = float(rng.get("bin_hz") or 0)
    e = _channel_energy(spec, f0, bin_hz, f, half_khz=60.0)
    ctrl = _channel_energy(spec, f0, bin_hz, f + 0.25, half_khz=60.0)
    outs = []
    for i, db in enumerate(spec):
        ff = f0 + i * bin_hz / 1e6
        if abs(ff - f) > 0.2:
            outs.append(float(db))
    outs.sort()
    floor = outs[len(outs) // 5] if outs else 0.0
    snr = (e["peak_db"] - floor) if e else None
    margin = (e["peak_db"] - ctrl["peak_db"]) if (e and ctrl) else None
    label = None
    for fk, name in _FM_KNOWN_LABELS.items():
        if abs(f - fk) <= 0.05:
            label = name
            break
    detected = bool(e and snr is not None and snr >= 10 and (margin is None or margin >= 3))
    result = {
        "ok": True,
        "mode": "fm_peek",
        "freq_mhz": f,
        "label": label,
        "detected": detected,
        "energy": {
            "mean_db": round(e["mean_db"], 2) if e else None,
            "peak_db": round(e["peak_db"], 2) if e else None,
            "peak_f": round(e["peak_f"], 4) if e and e.get("peak_f") else None,
        },
        "control_plus_250k": {
            "peak_db": round(ctrl["peak_db"], 2) if ctrl else None,
        },
        "snr_db": round(snr, 1) if snr is not None else None,
        "margin_db": round(margin, 1) if margin is not None else None,
        "ppm": int(ppm),
        "gain": int(gain),
        "ts": int(time.time()),
    }
    save_last_spectrum(result)
    return result
