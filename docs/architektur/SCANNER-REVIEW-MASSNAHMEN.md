# Scanner / PMR446 — Review-Nachbewertung und Maßnahmen

Stand: 2026-09-21 · Grundlage: GPT-Reviews (7+5+4) gegen Live-Betrieb und Code  
**Abschluss Status:** P0–P3 umsetzbar **erledigt**; optionaler Mehrprozess-IQ-Streamer bewusst offen.

Dieses Dokument filtert die Review-Ergebnisse gegen den tatsächlichen Code und die
beobachteten Live-Symptome (viele `peek` ~18–20 dB, `hits=0`, Capture-/Timeout-Loops,
mehrere Sekunden Audio-Delay).

---

## Kurzfazit

Die Reviews waren **weitgehend treffend**. Die drei Realprobleme

1. keine Hits trotz Nahfeld-Senden,
2. späte Hörbarkeit nach Autotune,
3. RTL-Busy / Recovery-Loops

hingen zusammen und sind im Code adressiert:

| Symptom | Hauptursache(n) | Status |
|---------|-----------------|--------|
| Kein Hit | FFT-Mismatch, Trigger 25 dB, pro-Frame-`rtl_sdr` | FFT/Block/Early-Exit behoben; Trigger konfigurierbar (Feld-Tuning) |
| Audio-Delay | langes Watch ohne Early-Exit, Sleeps, `rtl_fm`/`mpv`-Start | Watch kürzer, Early-Exit, Sleep-Audit |
| Stick-Hänger | viele Opens + verteilte Recovery; später verwaiste `rtl_sdr`-Streams | zentrale Recovery + Busy erkennt `rtl_sdr` + hartes Stream-Close |

---

## Was bestätigt wurde (Code)

| Claim | Status | Ort |
|-------|--------|-----|
| Profil-FFT 2048 vs. Processor 512 | **Bug behoben** | `spectrum.watch_channels` / `build_default_watcher` |
| `scan_next`/`scan_prev` ohne Return | **Bug behoben** | `scanner.py` → `td_scanner` |
| Monitor-Trigger 25 dB | Design/Tuning | Live oft Peeks ~18–20 dB → unter Trigger (absenkbar) |
| Einzelcapture pro Frame | durch Block + Stream ersetzt | `RTLSDRBackend` / `StreamingRtlReader` |
| Hold braucht `refresh_transition` | korrekt | Hold 15 s > Stale 12 s |
| `play_freq` schon low-latency | bestätigt | mpv-Cache/Buffer bereits knapp |
| WebUI Poll verstärkt Delay-Eindruck | UX | `index.html` (Poll 1 s + Peek-Markierung) |
| Preemption / Status „running ≠ produktiv“ | gültig | `monitor_effective_state` |

---

## Priorisierte Maßnahmen — Abschluss

### P0 — Detektion / Korrektheit — erledigt

1. FFT-Size an Profil koppeln  
2. `scan_next` / `scan_prev` Rückgabe  
3. Diagnose-Mindestsatz (peek/activity/error/latenz)  
4. Trigger testweise absenkbar (`scanner_pmr_trigger_on_db`, CLI `--trigger-on`)

### P1 — Latenz + Robustheit — erledigt

5. Early-Exit  
6. Watch-Fenster konfigurierbar (`scanner_pmr_watch_s`)  
7. Pro-Watch-IQ-Block  
8. Sleep-Audit  
9. WebUI Debug / preempt-Schalter  

### P2 — Ownership / Recovery — erledigt

10. Recovery zentral (`rtlsdr.recover_busy_device`)  
11. Reset-Cooldown (60 s)  
12. `scan_next` Audio nach Transition  

### P3 — angelaufen / abgeschlossen wo sinnvoll

13. Soft-Owner + Streaming-Watch — **erledigt als praktikabler Schritt**:
    - `/tmp/pidrive_rtlsdr_owner.json` (`request_owner` / `release_owner` / `announce_owner`)
    - In-Prozess-Lease (`claim_capture`)
    - `StreamingRtlReader` (Prefer-Stream, Fallback Block; `PIDRIVE_SPECTRUM_STREAM=0` schaltet ab)
    - Busy-Erkennung inkl. `rtl_sdr`, hartes Process-Group-Kill, Recover bei Capture-Timeout
    - **bewusst offen:** echter persistenter Mehrprozess-IQ-Streamer (ein Daemon, Clients abonnieren)
14. Nachbarkanal-/Best-Channel-Tuning — erledigt  
15. E2E-Mock-Tests — erledigt (`tests/unit/test_pmr_e2e.py`)

Zusätzlich behoben (nicht in den originalen Review-P0ern, aber Betriebs-kritisch):

- sticky-`/tmp`-Schreibfehler (`source_state.json`, `spectrum.json`)  
- verwaiste `rtl_sdr`-Streams → Spektrum `usb_claim_interface -6`  
- Peek unter Trigger in der WebUI sichtbar markieren  

---

## Checkliste

```
[x] FFT-Mismatch
[x] scan_next/prev Return
[x] Peek/Activity/Error-Metriken + Zeitstempel (Status/API)
[x] Trigger konfigurierbar
[x] Early-Exit + kürzeres Watch
[x] Block-Capture pro Watch
[x] UI-Debugblock / preempt_monitor
[x] Watch-Fenster / Sleep-Audit
[x] Recovery zentral + Reset-Cooldown
[x] scan_next Audio erst nach Transition
[x] Capture-Lease + Cross-Process Owner-Datei
[x] StreamingRtlReader (Watch Early-Exit live) + Orphan-Fixes
[x] Nachbarkanal-Tuning
[x] E2E-Mock-Tests
[ ] Persistenter Mehrprozess-IQ-Streamer (optional, später)
```

---

## Feldtest (weiterhin empfohlen)

**A — Erkennung:** `scanner monitor start --no-tune`, Trigger ggf. 18–20 dB, 10× senden → peek vs. activity.  
**B — Latenz:** Autotune an → Diffs `activity_ts − watch_started`, `audio_started − activity`.  
**C — Stick:** 10–15 min Monitor + Spektrum-Snapshot → keine Orphans (`ps aux | grep rtl_sdr` zwischen Watches leer), `capture_error_streak` niedrig.

---

## Bewusst nicht angefasst

- Kompletter Ownership-Rewrite als eigener Service vor den Detektionsfixes (überholt durch Soft-Owner + Stream).  
- Aggressive Absenkung des **Default**-Triggers ohne Feldvergleich (Default bleibt 25 dB).  
- mpv-Feintuning (Latenz sitzt überwiegend vor Audio-Start).  

---

## Bezug

- Architektur: [`SCANNER-PMR.md`](SCANNER-PMR.md)  
- Betrieb: [`../betrieb/PMR-MONITOR.md`](../betrieb/PMR-MONITOR.md)  
- State: [`ZUSTANDSMASCHINE.md`](ZUSTANDSMASCHINE.md)  
- Compat-Shims abgebaut: siehe [`DEVELOPER_GUIDE.md`](DEVELOPER_GUIDE.md) § Compat  
- Tests: `tests/unit/test_source_spectrum_pmr.py`, `tests/unit/test_pmr_e2e.py`  
