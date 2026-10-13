# Lab Weiche: Prefill-Sweep + Producer Free vs Gate · 2026-10-05 ~20:35

**HEAD-Basis:** `8d4f028` + Tool-Erweiterung (`--producer-gate`, `--post-pump-chunk`)  
**Anlass:** Mistral/GPT-Reviews Arm-Timeline — Design-Weiche ohne FW-Eingriff  
**Kritik:** [`KRITIK-REVIEW-MISTRAL-GPT-ARM-TIMELINE-8d4f028.md`](KRITIK-REVIEW-MISTRAL-GPT-ARM-TIMELINE-8d4f028.md)

---

## Kurzfazit

1. **Prefill allein reicht nicht für den 62×4KiB-Burst:** 16/32/48 KiB → Arm `in_window`, aber ohne Nachschub outrannt der Host das **statische** Fenster; `live` wächst nur ≈ Prefill-Größe (kumulativ), Ende `in_window=false`.
2. **Freilaufender Producer mit Pace ≥ Host (8 KiB Pump / 4 KiB Read):** `underruns=0`, Ende **`in_window=true`**, `live=253952` — Cursor und Fenster wandern gemeinsam. Das ist der bisher stärkste Lab-Hinweis auf „Ton möglich“.
3. **Producer-Gate (Pause bei Ring voll) allein hilft hier nicht:** Ring füllt auf 48 KiB, dann pausiert; Cursor läuft am Fensterende vorbei → Fenster friert bei `0..49152`, Host bei 253952, **204800 Underruns**. Gate ohne Resume/Nachführen = eingefrorene Daten hinter dem Cursor.
4. **Remount ohne RST:** Settle nach Remount `cursorArmed=true`, `hostAbs=65536` vom Seed-Lauf — Cursor-Zustand bleibt (Feld 17:55-Analog, jetzt mit Bridge-Mimic-Vorlauf).

→ GPT hatte recht: Producer-Gate ist **Hypothese**, nicht bewiesen. In dieser Matrix gewinnt **Pace/Vorfüllen+Nachschub**, nicht Gate-alone.

---

## Prefill-Sweep (silent post-pump, 248 KiB Host)

| Run | Prefill | Arm host/abs / in_win | End host | End abs | End live | End und | End in_win |
|-----|---------|----------------------|----------|---------|----------|---------|------------|
| 2035 | 0 | 4096/0 false | 253952 | 0..0 | 0 | 253952 | false |
| 2036 | 16 | 3584/0 **true** | 265728 | 0..16384 | 16896 | 249344 | false |
| 2037 | 32 | 3584/0 **true** | 265728 | 0..32768 | 33280 | 232960 | false |
| 2038 | 48 | 3584/0 **true** | 265728 | 0..49152 | 49664 | 216576 | false |

**Lesart:** Mehr Prefill → mehr historische `liveBytes`, aber der 248‑KiB-Burst ohne Producer-Nachschub endet immer außerhalb.

---

## Producer Free vs Gate (chunk=8192, budget=1024 KiB, Burst 248 KiB)

| Run | Mode | Arm in_win | End host | End abs | End live | End und | End in_win | pumped / gate_pauses |
|-----|------|------------|----------|---------|----------|---------|------------|----------------------|
| 2039 | **free** | true | 462848 | 458752..507904 | **253952** | **0** | **true** | 507904 / 0 |
| 2040 | **gate** | true | 253952 | 0..49152 | 49152 | 204800 | false | 49152 / 1 |

**Mechanik Gate-Fail:** Nach Ring-Voll pausiert der Pump; Host liest über `absEnd` hinaus → sequentieller Cursor vor dem Fenster; Ring bleibt voll mit Bytes **hinter** dem Cursor → Gate bleibt pausiert → nur noch Underrun.

**Mechanik Free-PASS:** Pump 2× Host-Rate hält `absEnd` vor dem Cursor → jeder Live-Read trifft → keine Underruns.

---

## Remount (sauber)

| Run | Prep | Settle armed/host | Notiz |
|-----|------|-------------------|--------|
| 2041 | soft_rst seed | false/0 → End host 65536 | Vorlauf |
| 2042 | **usb_remount** | **true/65536** | Zustand überlebt Remount |

---

## Folgerung für Design-Weiche

| Kandidat | Lab-Status |
|----------|------------|
| Vorfüllen allein (0–48 KiB) | Arm ok; Burst ohne Nachschub → Fail |
| Producer-Gate allein | Fail (Cursor outrannt eingefrorenes Fenster) |
| Producer-Pace ≥ Host (Bridge) | **PASS** live & in_window über 62er-Burst |
| Kombi Prefill + Pace | noch nicht kombiniert getestet; naheliegend |

**Feld-Implikation:** Nach `audio_start` muss die Bridge **mindestens** Host-Burst-Rate nachschieben (oder HU-Pace drosseln — nicht steuerbar). Gate nur sinnvoll, wenn Cursor das Fenster nicht verlässt (oder Resync) — sonst kontraproduktiv.

Freeze hält — kein FW-Snap. Nächstes: Bridge-Prefill+Pace-Strategie skizzieren / Feld dense Correlate ab `audio_start`.
