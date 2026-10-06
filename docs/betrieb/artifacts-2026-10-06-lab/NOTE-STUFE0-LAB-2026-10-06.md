# Lab-NOTE: Stufe 0 + Eager-Mimic / Profil (2026-10-06)

**Bezug:** [`Stufenplan.md`](../../planung/Stufenplan.md) · [`MASSNAHMEN-HU-CACHE-BACKPRESSURE-2026-10-06.md`](../artifacts-2026-10-06-feld/MASSNAHMEN-HU-CACHE-BACKPRESSURE-2026-10-06.md)

## Erledigt (ohne Stall-FW)

| ID | Artefakt | Abnahme |
|----|----------|---------|
| M1 | `docs/betrieb/templates/run.yaml` · `tools/feld_status_poll.py` | 1 Hz + Wanduhr |
| M2 | Spike-Rest in `SPIKE-TINYUSB-READ10-2026-10-06.md` | USBMSC 1:1, USB-Task max prio, BUFSIZE=4096 |
| M3 | `tools/nbt_profile_extract.py` · `tools/profiles/nbt_evo_2026-10-06.json` | gap median **4** ms, read_n mode **4096**, ACCEPT PASS |
| O6 | `soft_rst` / prep in `m3_lab_async_producer.py`, `m3_lab_arm_timeline.py` | leerer Restart-Body ≠ Fehler |
| Mimic | `tools/m3_lab_hu_eager_file.py` | fav1→fav2 @ 4 KiB / 4 ms; `--pump-bps 9000`; `--arm-before-read` |
| Bridge | `esp32.pidrive/tools/pump_bridge.py` | `audio_target_bps(bitrate)` (48k→9000, 128k→24000); `--marker` |

## Lab-Lauf Eager (wenn `.88` gesteckt)

```bash
sg disk -c 'python3 tools/m3_lab_hu_eager_file.py --dev /dev/sda --uid fav1 --next fav2 --arm-before-read'
sg disk -c 'python3 tools/m3_lab_hu_eager_file.py --dev /dev/sda --uid fav1 --next fav2'  # cold / Muster-B-nah
```

## Nicht in dieser Runde

- FW `stall_ms` / Cursor-strict / `streamBytesServed_` Reset (Freeze)
- Vollständiger `nbt_hu_sim` Golden G1–G5
