# Lab-Auftrag P0: Arm-Timeline + RST-Matrix (2026-10-05)

**Hintergrund:** Review Mistral/GPT zu Feld 18:07 (`87d2523`) — siehe [`KRITIK-REVIEW-MISTRAL-GPT-FELD-1807-87d2523.md`](../artifacts-2026-10-05-feld/KRITIK-REVIEW-MISTRAL-GPT-FELD-1807-87d2523.md).

## GPT-Ideen — Einordnung

| Vorschlag | Brauchbar? | Umsetzung im Projekt |
|-----------|------------|----------------------|
| Zeitliche Entstehung von `hostAbsCursor` | **Ja, P0** | `tools/m3_lab_arm_timeline.py` — dense Snaps, `arm_transition` in REPORT |
| Viele FAT-Dateien mit „Cursor pro File“ | **Nein (irreführend)** | Cursor ist Laufzeit in StreamBuffer, nicht Datei-Metadatum |
| Lab-Matrix Read-Historie (Mid 64…512 KiB, Producer 1/5 s) | **Ja** | `--mid-kib`, `--producer-s`, `--prefill-kb` |
| Software-RST reproduzierbar | **Ja, teilweise schon da** | `--prep soft_rst` (`POST /api/restart`); Feld ≈ **rst + USB neu** → `--prep rst_remount` |
| RST vs USB-Remount vs Bridge-Restart | **Ja, wichtig** | Lab: `none` / `soft_rst` / `usb_remount` / `rst_remount`; Bridge-Restart manuell (Feld BrokenPipe) |
| Tests 1–4 (RST + Ring leer/voll/Mid/Producer lang) | **Ja** | Kombinationen prefill + producer-s + mid-kib |
| `fileOff` pro Read | **Ja, aber FW/JSONL** | Status-Polling reicht für Arm-Übergang; `fileOff` später aus `readsEmit`/MSC-JSONL |
| `headResyncs` | **Ja** | in Timeline-Snap enthalten |

**Nicht im Lab-Host:** echtes NBT-Datei-Cache-Verhalten — RST-Matrix im Lab approximiert nur ESP/USB-Seite; Feld bleibt Stichprobe für HU Head nach RST.

## Tool

```bash
sg disk -c 'python3 tools/m3_lab_arm_timeline.py --prep soft_rst --producer-s 5 --dense --label versuch_C'
sg disk -c 'python3 tools/m3_lab_arm_timeline.py --prep rst_remount --prefill-kb 96 --dense --label prefill_pass_shape'
sg disk -c 'python3 tools/m3_lab_arm_timeline.py --prep usb_remount --mid-kib 256 --dense --label remount_no_rst'
```

## Erfolgskriterien (Lab)

1. **`arm_transition`:** `hostAbsCursor` ≈ `absBase` beim ersten `cursorArmed=true` (Code-Erwartung).
2. **Versuch C:** Nach `producer-s>0` — beim Arm `behind_base` klein und `liveBytes>0` möglich (Prefill-Pfad).
3. **253952-Repro:** `post-head-kib 256` + dense — prüfen ob `hostAbs` ≈ 62×4096 bei Underrun-dominiertem Lauf.

Freeze hält — kein Detect-/FW-Snap vor Auswertung.

## Erste Läufe (2026-10-05 ~18:45 Lab .88)

| Run | Label | Arm-Übergang (`hostAbs` / `absBase`) | End `live` | Notiz |
|-----|-------|--------------------------------------|------------|--------|
| `lab88-arm-timeline-1847-prefill` | prefill96 | 52736 / 49152, `in_window`, live=4096 | 49664 | Prefill-Pfad: erster Head-Read **im** Fenster |
| `lab88-arm-timeline-1848-C` | versuch_C_v2 | 44544 / 40960, live=4096 | 49664 | Producer 5 s **dann** Head: Arm nahe `absBase`, danach Underrun-Lauf host→184k |
| `lab88-arm-timeline-1845-C` | versuch_C (Pump-Bug) | — | 0 | Vor Fix: falsches Pump-Framing → Ring leer; nur Underrun |

→ **GPT-Mechanik stützt sich:** Cursor armt nahe aktuellem `absBase`, zählt bei weiteren Reads hoch; Persistenz-Hypothese für 253952 **nicht nötig** (Feld-Timeline weiterhin wünschenswert).

## Matrix ~19:45 (Bridge-Mimic)

Siehe [`GESAMTBERICHT-ARM-TIMELINE-MATRIX-1945.md`](GESAMTBERICHT-ARM-TIMELINE-MATRIX-1945.md).

**P0 erledigt:** `1945-empty248` reproduziert Feld **`hostAbs=streamBytes=underruns=253952`** nach Arm bei `absBase=0`. Tool braucht default `--bridge-mimic` (`audio_start` nach Head-Tip), sonst kein Live-Pfad.
