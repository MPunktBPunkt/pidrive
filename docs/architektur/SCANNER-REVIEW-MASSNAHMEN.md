# Scanner / PMR446 — Review-Nachbewertung und Maßnahmen

Stand: 2026-09-21 · Grundlage: GPT-Reviews (7+5+4) gegen Live-Betrieb und Code

Dieses Dokument filtert die Review-Ergebnisse gegen den tatsächlichen Code und die
beobachteten Live-Symptome (viele `peek` ~18–20 dB, `hits=0`, Capture-/Timeout-Loops,
mehrere Sekunden Audio-Delay).

---

## Kurzfazit

Die Reviews sind **weitgehend treffend**. Die drei Realprobleme

1. keine Hits trotz Nahfeld-Senden,
2. späte Hörbarkeit nach Autotune,
3. RTL-Busy / Recovery-Loops

sind **kein Zufall aus drei getrennten Bugs**, sondern hängen zusammen:

| Symptom | Hauptursache(n) |
|---------|-----------------|
| Kein Hit | FFT-Mismatch (echt), Trigger 25 dB (Tuning), pro-Frame-`rtl_sdr` (Architektur) |
| Audio-Delay | `watch_seconds≈2` ohne Early-Exit, feste Sleeps, Prozessstart `rtl_fm`/`mpv` |
| Stick-Hänger | Viele kurze `rtl_sdr`-Opens + verteilte Recovery/`pkill`-Pfade |

**Nicht** alles aus den Reviews ist P0: Ownership-Rewrite, persistenter Streaming-Reader
und UI-Komplettumbau sind sinnvoll, aber nach den schnellen Detektions-/Diagnose-Fixes.

---

## Was bestätigt wurde (Code)

| Claim | Status | Ort |
|-------|--------|-----|
| Profil-FFT 2048 vs. Processor 512 | **echter Bug** (behoben) | `spectrum.watch_channels` / `build_default_watcher` |
| `scan_next`/`scan_prev` ohne Return | **echter Bug** (behoben) | `scanner.py` → `td_scanner` sah immer „kein Treffer“ |
| Monitor-Trigger 25 dB | Design/Tuning | Live: Peeks ~18–20 dB → unter Trigger |
| Einzelcapture pro Frame | Designschwäche | `RTLSDRBackend.capture_iq` |
| Hold braucht `refresh_transition` | korrekt / getestet | Hold 15 s > Stale 12 s |
| `play_freq` schon low-latency | bestätigt | mpv-Cache/Buffer bereits knapp |
| WebUI Poll ~2 s verstärkt Delay-Eindruck | UX | `index.html` |
| Preemption / Status „running ≠ produktiv“ | gültig | Monitor-Loop |

---

## Priorisierte Maßnahmen

### P0 — sofort (Detektion / Korrektheit)

1. **FFT-Size an Profil koppeln** — erledigt.
2. **`scan_next` / `scan_prev` Rückgabe** — erledigt.
3. **Diagnose-Mindestsatz** — erledigt.
4. **Trigger testweise absenkbar** — erledigt.

### P1 — kurzfristig (Latenz + Robustheit)

5. **Early-Exit** — erledigt.
6. **Watch-Fenster konfigurierbar** — erledigt (`scanner_pmr_watch_s`, Default 1.0 s).
7. **Pro-Watch-IQ-Block** — erledigt.
8. **Sleep-Audit** — erledigt (Start/Preempt/Listen-Ende verkürzt).
9. **WebUI Debug / preempt-Schalter** — erledigt.

### P2 — mittelfristig (Ownership)

10. **Recovery zentral** — erledigt (`rtlsdr.recover_busy_device`).
11. **Reset-Cooldown** — erledigt (60 s).
12. **`scan_next` Audio nach Transition** — erledigt (`autoplay=False` + play im Trigger).

### P3 — später

13. Persistenter IQ-/Owner-Service.
14. Nachbarkanal-/Best-Channel-Tuning.
15. Vollständige E2E-Integrationstests mit Mock-RTL.

---

## Empfohlene Umsetzungsreihenfolge

```
[x] FFT-Mismatch
[x] scan_next/prev Return
[x] Peek/Activity/Error-Metriken + Zeitstempel (Status/API)
[x] Trigger konfigurierbar + Feldtest A (nur Erkennung)
[x] Early-Exit + kürzeres Watch (Feldtest B Latency)
[x] Block-Capture pro Watch (Feldtest C Stick-Stabilität)
[x] UI-Debugblock
[x] Watch-Fenster konfigurierbar / Sleep-Audit
[x] preempt_monitor UI-Schalter
[x] Recovery zentralisieren (`rtlsdr.recover_busy_device`) + Reset-Cooldown
[x] scan_next Audio erst nach Transition
[ ] Persistenter IQ-/Owner-Service (P3)
[ ] Nachbarkanal-/Best-Channel-Tuning (P3)
[ ] Vollständige E2E-Integrationstests (P3)
```

---

## Feldtest (kurz)

**A — Erkennung:** `scanner monitor start --no-tune`, 10× 3 s senden → `peek_count` vs. `activity_count`, `last_peek_relative_db`.  
**B — Latenz:** Autotune an → Diffs `activity_ts − watch_started`, `audio_started − activity`.  
**C — Stick:** 10–15 min Monitor + Snapshot mit/ohne Preempt → `capture_error_streak`, `usb_reset_count`.

Details: Design in den GPT-Folge-Reviews (Mess-/UI-/Ownership-Design) — hier bewusst auf Umsetzbares verdichtet.

---

## Was bewusst *nicht* sofort angefasst wird

- Kompletter Ownership-Rewrite vor Block-Capture (würde Symptome ohne Root-Fix umbauen).
- Aggressive Trigger-Absenkung ohne Diagnose (erschwert Vergleich vorher/nachher).
- mpv-Feintuning (Latenz sitzt überwiegend vor Audio-Start).

---

## Bezug

- Architektur: [`SCANNER-PMR.md`](SCANNER-PMR.md)
- Betrieb: [`../betrieb/PMR-MONITOR.md`](../betrieb/PMR-MONITOR.md)
- State: [`ZUSTANDSMASCHINE.md`](ZUSTANDSMASCHINE.md)
- Tests: `tests/unit/test_source_spectrum_pmr.py`
