# Lab Folge: Pace-Raten + Prefill-Kombi + Fenster-voraus · 2026-10-05 ~20:45

**Basis:** Weiche 2035 (`03dbccf`) · Tool: `--tail-pump-s` neu  
**ESP:** .88 · Freeze hält

---

## Kurzfazit

1. **Prefill 48 + Pace 8 KiB/Step:** `underruns=0`, `in_window=true` über 248 KiB — Kombi PASS (wie Free allein, Arm schon im Fenster).
2. **Pace-Schwelle:** 8 KiB/Step und 4 KiB/Step → praktisch keine Underruns; **2 KiB/Step** → Host overholt Producer (`und≈252 k`, live≈2 k). Pace muss **≥ Host-Readrate** sein.
3. **Feld 18:07-Geometrie 1:1:** Burst ohne Pump → `hostAbs=253952`, dann Tail-Pump 5 s ohne Host-Reads → `absBase=286720`, **`behind_base=32768`**, `live=0`. Fenster läuft dem Cursor davon.
4. **Pace-dann-voraus (2050):** Während Burst `in_window`; danach Tail-Pump → `behind≈200 KiB` trotz historischem `live=253952`. Erklärt, warum Feld-Ring „voll“ und trotzdem kein Ton sein kann.
5. **Prefill+Gate:** Ring schon voll beim Start → Gate pumpt 0 → wie Prefill allein (Fail).

---

## Tabelle

| Run | Label | End host | End abs | live | und | in_win | behind | Notiz |
|-----|-------|----------|---------|------|-----|--------|--------|--------|
| 2045 | prefill48+pace8k | 512000 | 507904..557056 | 266240 | **0** | **true** | 0 | Kombi PASS |
| 2046 | pace4k | 253952 | 204800..253952 | 253952 | **0** | false* | 0 | host==absEnd (Rand) |
| 2047 | pace2k | 253952 | 77824..126976 | 2048 | 251904 | false | 0 | Unter-Pace FAIL |
| 2048 | window_ahead | 253952 | 286720..335872 | 0 | 253952 | false | **32768** | **18:07-Geometrie** |
| 2049 | prefill48+gate | 265728 | 0..49152 | 49664 | 216576 | false | 0 | Gate pump=0 |
| 2050 | pace_then_ahead | 462848 | 663552..712704 | 253952† | 0 | false | **200704** | Burst ok, dann voraus |

\* `in_window` strikt `host < absEnd` — an der Kante false, aber und=0.  
† kumulativ aus Burst-Phase; nach Tail nicht mehr im Fenster.

---

## Design-Implikation

| Hebel | Lab |
|-------|-----|
| Bridge Pace ≥ HU-Burst | **notwendig** (2k FAIL, 4k/8k PASS) |
| Prefill vor Arm | hilfreich für frühen Treffer, **nicht** hinreichend |
| Gate allein / Prefill+Gate | ungeeignet für langen Burst |
| Producer nach Host-Stopp weiter | erzeugt 18:07 (`behind_base>0`, live-Pfad tot) |

**Bridge-Zielbild:** Nach `audio_start` sofort füllen + während HU-Reads mind. 1:1 nachschieben; wenn HU pausiert, Producer **nicht** ungebremst `absBase` über den Cursor schieben (sonst 18:07) — das ist der sinnvolle Rest von „Gate“, aber gekoppelt an Cursor-Lage, nicht nur Ring-Voll.

Feld-nächstes: dense Correlate ab `audio_start` + `absEnd`-Steigung vs. `hostAbs`.
