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

1. **FFT-Size an Profil koppeln** — erledigt in `watch_channels()`; Debugfeld `effective_fft_size`.
2. **`scan_next` / `scan_prev` Rückgabe** — erledigt (`return ch` / `None`).
3. **Diagnose-Mindestsatz** (als Nächstes):
   - Status: `last_peek_*`, `peek_count`, `activity_count`, `capture_error_streak`
   - Zeitstempel: `watch_started_ts`, `activity_ts`, `tuned_ts`, `audio_started_ts`
4. **Trigger testweise absenkbar** (Settings/CLI, z. B. 16–20 dB Lab-Modus) — ohne Softcode-Hardcoding nur 25.

### P1 — kurzfristig (Latenz + Robustheit)

5. **Early-Exit** in `watch_channels()` bei starkem Hit (Margin über Trigger + Mindestzeit ~300 ms).
6. **Watch-Fenster** für Monitor konfigurierbar / `fast`-Modus (0.6–1.0 s).
7. **Pro-Watch-IQ-Block** statt N× `rtl_sdr` pro Frame (größter Hebel gegen Stick-Stress).
8. **Sleep-Audit** im Monitor (Start 1.0 s, Preempt 0.8 s, Listen-Ende 0.6 s).
9. **WebUI**: Snapshot vs. Backend-Monitor klarer; `preempt_monitor` sichtbar; Debug-Poll 0.5–1 s.

### P2 — mittelfristig (Ownership)

10. Recovery-Eskalation zentral in `rtlsdr.recover_device(level=…)` statt Sonder-`pkill` in `scanner.py`.
11. Reset-Cooldown + Zähler im Status.
12. `scan_next`: Scan und `play_freq` entkoppeln (Trigger startet Audio nach Transition) — heute startet Audio schon vor `begin_transition`.

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
[x] Early-Exit + kürzeres Watch (Feldtest B Latency)  # Early-Exit; Watch-Länge noch Default 2s
[ ] Block-Capture pro Watch (Feldtest C Stick-Stabilität)
[x] UI-Debugblock
[ ] Recovery zentralisieren
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
