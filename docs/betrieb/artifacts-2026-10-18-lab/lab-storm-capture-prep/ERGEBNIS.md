# Lab · Storm-Capture Prep · 2026-10-18

**ESP:** `.88` · FW `0.4.53-dev` · mess-fw  
**Bezug:** Tooling-Audit Storm-Capture (technology-audit `035cb72`) · M30–M32 · M36

## Urteil

P0-Pipeline (Poll v2 + MessCapture `--storm` + Q/S + Band-Report) ist lab-grün. M36 Live-Dashboard (`--qs`) lab-grün: keine False-Alerts auf Lab-`inv≠31/32`. BMW-Storm bleibt Feld.

## Qualitätslage Abend 17.10.

| Spur | Urteil | Lücke |
|------|--------|-------|
| Status-JSON | gut | nur Stichproben |
| Poll v1 | mittel | kein pref/midFile → **behoben in Schema v2** |
| MessCapture Abend | fehlend | Feld M30 |
| UART | fehlend | Feld M30 |
| Invariante 31/32 | ok in 1757 | Lab hat andere Diff (erwartet) |

Baseline `poll-replug-1757` (nur ΔbytesFile): S-Episoden 17:58:07–19 / 17:58:22–30 + 1 Guess-Event.

## Lab-Sessions

| Session | Ergebnis |
|---------|----------|
| `session-dryrun/` | frühes `arm` → `play_cleared` ~1 s (zu kurz für Storm) |
| **`session-storm-m32/`** | `--storm` → **timeout 30.5 s**, 48 cmds, schema 2, band `storm_hint=true` (file_body 77 %), qs=Q (Lab-Quiet, kein NBT-Storm) |
| `session-m36-qs/` | Live `--qs` 12 s · nach Fenster Q · **alerts=0** trotz `inv=36` (Plaus ≠ Alarm) |
| **`session-m36-storm/`** | Harness mit `--qs` · SUMMARY `alert_n=0` · band wie M32 · qs überwiegend Q |

`SUMMARY.json` der M32-Session:

- poll schema_ok, pref+midFile befüllt  
- arm `stop_reason=timeout`  
- band dominant `file_menue_stub` / `file_fav0` (Soft-USB-Lab, nicht BMW-S)  
- qs überwiegend Q — korrekt für ruhigen Lab-Host

## Tools (umgesetzt)

| Maßnahme | Tool | Lab |
|----------|------|-----|
| M30 Session | `tools/feld_storm_session.sh` + `mess_hu_capture arm --storm` | ☑ |
| M31 Q/S | `tools/feld_qs_classify.py` + poll schema v2 | ☑ |
| M32 LBA→Band | `tools/mess_band_report.py` (arm.json + dump) | ☑ |
| M36 Dashboard | `feld_status_poll --qs` · `alerts[]` / `storm_enter` | ☑ |

## Feld-Kommando

```bash
bash tools/feld_storm_session.sh --esp http://192.168.178.89 \
  --out docs/betrieb/artifacts-2026-10-18-feld/feld-storm-m30-01 \
  --sit none --seconds 120 --uart /dev/ttyACM0
```

Protokoll: [`../../artifacts-2026-10-17-feld/CAPTURE-PROTOKOLL-STORM-M30.md`](../../artifacts-2026-10-17-feld/CAPTURE-PROTOKOLL-STORM-M30.md)
