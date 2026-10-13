# Feldabend 2026-10-01 ~19:48–20:07 (0.4.34-dev, Auto `.89`)

**Ohr:** Auswahl reagiert (rote LED), oft kein Ton. Siehe Feldbericht §11.6.

## Zwei Ursachen

| Befund | Bedeutung |
|--------|-----------|
| `pre=182272` (BOB 20:03) | HU liest ~182 KiB Silence **vor** `overlay_warm`, dann **0** Live-Reads (`streamBytes=0`) |
| Guess bei `pump.tcp.down` | `play_uid`/ffmpeg verpasst → **0.4.35** hello-Replay |

## Kern 20:03 BOB

- `play.guess fav2` + Bridge `audio_start`/ffmpeg ok
- `msc.overlay_warm warm=8445 pre=182272`
- jsonl: 37 Burst-Zeilen; vor Warm fav2≈346 KiB (+ fav0); nach Warm leer

## Dateien

| Datei | Inhalt |
|-------|--------|
| `esp89-status-200435.json` / `esp89-events-200435.json` | Status + Event-Ring ~20:04 |
| `pidrive_msc_reads.jsonl` | 37 Zeilen (BOB-Fenster) |
| `pidrive_msc_reads-pre-195505.jsonl` | 173 Zeilen (~19:49 Session, vollständiger) |
| `pidrive_msc_diag.jsonl` | diag |
| `bridge-since-otgwait.log` | Bridge-Slice |

## Lab-Traces (exportiert)

- `feld_bob_2003_prewarm.replay.json` — kumulatives `t_ms` (Export-Fix: nicht `+= gap`)
- `feld_bob_2003_prewarm_head.replay.json` — erste 7×4 KiB, SG-Smoke für Timing
- `feld_1949_session.replay.json` — 173 Burst-Zeilen; Meta `pre≈215040` (anderer Pass als 182272)
- `feld_prefetch_then_warm_gentle.replay.json` (~180 KiB @ 4 KiB/150 ms) — `nbt_suite` Szenario `prefetch_then_warm`
