# Feldabend 2026-10-01 ~20:03 (0.4.34-dev, Auto `.89`)

**Ohr:** Radio BOB gewählt, kein Ton. Rote LED-Blink bei Auswahl (Reaktion).

## Kern
- `play.guess fav2` + Bridge `audio_start`/ffmpeg BOB ok
- `msc.overlay_warm warm=8445 pre=182272` — HU las ~182 KiB Silence vor Live-Overlay
- danach `streamBytes≈0` (kein Live-Consume)
- früher im Boot: `play.guess fav1` bevor `pump.tcp.up` (Audio verpasst)

## Dateien
- `esp89-status-200435.json` / `esp89-events-200435.json`
- `pidrive_msc_reads.jsonl` (37) / `pidrive_msc_diag.jsonl`
- `bridge-since-otgwait.log`
