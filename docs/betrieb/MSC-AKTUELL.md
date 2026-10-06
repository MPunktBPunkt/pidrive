# MSC / BMW — aktueller Stand (Lesereihenfolge)

**Stand:** 2026-10-06 Abend — **HU = File-Cache / Eager-Read** · Hebel **MSC-Backpressure (Stall)**, nicht Prefill≥400 KiB / PSRAM · Feld 0.4.46: Detect OK, kein Ton  
**Phase:** Baustelle C — Stufe 1 Auto (Decode-Start + Cache) ∥ Lab HU-Sim Golden · Stall-FW erst nach Go · Sequenz-GO gesperrt

Dies ist der **einzige Einstieg**, wenn du wissen willst, wo wir stehen und warum.

---

## 1. Jetzt lesen (normativ)

| # | Dokument | Rolle |
|---|----------|--------|
| 0 | [`planung/Stufenplan.md`](../planung/Stufenplan.md) | **Stufen 0–6:** Messbarkeit → Auto-F1 → Lab-Sim → Stall-FW → Feld |
| 0m | [`artifacts-2026-10-06-feld/MASSNAHMEN-HU-CACHE-BACKPRESSURE-2026-10-06.md`](artifacts-2026-10-06-feld/MASSNAHMEN-HU-CACHE-BACKPRESSURE-2026-10-06.md) | **Maßnahmen** — M1–M3 + Bridge-Drossel ✅; Stall-FW offen |
| 0n | [`artifacts-2026-10-06-lab/NOTE-STUFE0-LAB-2026-10-06.md`](artifacts-2026-10-06-lab/NOTE-STUFE0-LAB-2026-10-06.md) | Stufe-0/Lab-Umsetzung (Profil, Eager-Mimic, Spike) |
| 0i | [`../tools/ingest/README.md`](../../tools/ingest/README.md) | **Ingest** Roh→Parquet/DuckDB (`run.yaml` + `data/`) |
| 0a | [`artifacts-2026-10-06-feld/ANALYSE-HU-FILE-CACHE-BACKPRESSURE-2026-10-06.md`](artifacts-2026-10-06-feld/ANALYSE-HU-FILE-CACHE-BACKPRESSURE-2026-10-06.md) | Modell: Burst=Dateirest, Cure=Stall |
| 0f | [`fahrzeug/HU-Technical-Facts.md`](../fahrzeug/HU-Technical-Facts.md) | HU-Fakten [B]/[S]/[H]/[?] |
| 0s | [`artifacts-2026-10-06-lab/SPIKE-TINYUSB-READ10-2026-10-06.md`](artifacts-2026-10-06-lab/SPIKE-TINYUSB-READ10-2026-10-06.md) | TinyUSB return 0 / Teilantwort |
| 0k | [`artifacts-2026-10-06-lab/KONZEPT-HU-SIM-NBT-2026-10-06.md`](artifacts-2026-10-06-lab/KONZEPT-HU-SIM-NBT-2026-10-06.md) | Lab-Simulator-Konzept |
| 0f6 | [`artifacts-2026-10-06-feld/feld-av-0723/GESAMTBERICHT-FELD-AV-0723.md`](artifacts-2026-10-06-feld/feld-av-0723/GESAMTBERICHT-FELD-AV-0723.md) | Feld 07:50–08:13 — 0.4.46, Detect OK, AV FAIL |
| 0sum | [`artifacts-2026-10-06-feld/summary-2026-10-06.txt`](artifacts-2026-10-06-feld/summary-2026-10-06.txt) | Rohauswertung + GPT-Plan |
| 0old | [`artifacts-2026-10-05-feld/feld-av-1807/GESAMTBERICHT-FELD-AV-1807.md`](artifacts-2026-10-05-feld/feld-av-1807/GESAMTBERICHT-FELD-AV-1807.md) | Feld 18:07 — historisch |
| 0r | [`artifacts-2026-10-05-feld/KRITIK-REVIEW-MISTRAL-GPT-FELD-1807-87d2523.md`](artifacts-2026-10-05-feld/KRITIK-REVIEW-MISTRAL-GPT-FELD-1807-87d2523.md) | Review Mistral+GPT — RST-Trigger, 253952-Korrektur, P0 Lab |
| 0f5 | [`artifacts-2026-10-05-feld/feld-av-1755/GESAMTBERICHT-FELD-AV-1755.md`](artifacts-2026-10-05-feld/feld-av-1755/GESAMTBERICHT-FELD-AV-1755.md) | Feld 17:55 — ohne RST kein Arm |
| 0h | [`artifacts-2026-10-05-lab/lab88-head-trigger-1754/GESAMTBERICHT-HEAD-TRIGGER.md`](artifacts-2026-10-05-lab/lab88-head-trigger-1754/GESAMTBERICHT-HEAD-TRIGGER.md) | Lab Mid→Head armt |
| 0p | [`artifacts-2026-10-05-lab/lab88-prefill-arm-1750/GESAMTBERICHT-PREFILL-ARM.md`](artifacts-2026-10-05-lab/lab88-prefill-arm-1750/GESAMTBERICHT-PREFILL-ARM.md) | Lab Prefill-vor-Arm PASS |
| 0e2 | [`artifacts-2026-10-05-feld/feld-av-abend-1530/GESAMTBERICHT-FELD-AV-ABEND.md`](artifacts-2026-10-05-feld/feld-av-abend-1530/GESAMTBERICHT-FELD-AV-ABEND.md) | Feld Abend 15:30 — Gate PASS, AV/Ohr FAIL Fenster/Arm |
| 0L4 | [`artifacts-2026-10-05-lab/lab88-arm-diag-1635/GESAMTBERICHT-ARM-DIAG.md`](artifacts-2026-10-05-lab/lab88-arm-diag-1635/GESAMTBERICHT-ARM-DIAG.md) | Lab Arm-Diagnose: Mid≠Arm, Head-Arm bei ring=0 |
| 0L3 | [`artifacts-2026-10-05-lab/lab88-hu-mimic-1617/GESAMTBERICHT-HU-MIMIC-1541.md`](artifacts-2026-10-05-lab/lab88-hu-mimic-1617/GESAMTBERICHT-HU-MIMIC-1541.md) | Lab HU-Mimic 15:41 Fenster-Outrun |
| 0L2 | [`artifacts-2026-10-05-lab/STREAM-COUNTER-SEMANTIK.md`](artifacts-2026-10-05-lab/STREAM-COUNTER-SEMANTIK.md) | StreamBuffer: underruns / hostAbs / liveBytes |
| 0L5 | [`artifacts-2026-10-05-lab/LAB-NEXT-ARM-TIMELINE-2026-10-05.md`](artifacts-2026-10-05-lab/LAB-NEXT-ARM-TIMELINE-2026-10-05.md) | **P0 Lab:** Arm-Timeline + RST-Matrix (`m3_lab_arm_timeline.py`) |
| 0L6 | [`artifacts-2026-10-05-lab/GESAMTBERICHT-ARM-TIMELINE-MATRIX-1945.md`](artifacts-2026-10-05-lab/GESAMTBERICHT-ARM-TIMELINE-MATRIX-1945.md) | **Lab Matrix:** 253952 = 62×4KiB Underrun (PASS) |
| 0L7 | [`artifacts-2026-10-05-lab/GESAMTBERICHT-ARM-WEICHE-2035.md`](artifacts-2026-10-05-lab/GESAMTBERICHT-ARM-WEICHE-2035.md) | **Lab Weiche:** Prefill-Sweep + Free vs Gate |
| 0L8 | [`artifacts-2026-10-05-lab/GESAMTBERICHT-ARM-FOLGE-2045.md`](artifacts-2026-10-05-lab/GESAMTBERICHT-ARM-FOLGE-2045.md) | **Lab Folge:** Pace-Raten + Fenster-voraus-Repro |
| 0L9 | [`artifacts-2026-10-05-lab/GESAMTBERICHT-CURSOR-HOLD-2110.md`](artifacts-2026-10-05-lab/GESAMTBERICHT-CURSOR-HOLD-2110.md) | **Lab Cursor-Hold PASS** (gegen 2050 / Host-Pause) |
| 0L10 | [`artifacts-2026-10-05-lab/GESAMTBERICHT-ASYNC-PRODUCER-2140.md`](artifacts-2026-10-05-lab/GESAMTBERICHT-ASYNC-PRODUCER-2140.md) | **Lab Async:** Free=18:07 · Hold behind=0 · Pace unter MSC-Last offen |
| 0L11 | [`artifacts-2026-10-05-lab/GESAMTBERICHT-PUMP-IDLE-BURST-REALISM.md`](artifacts-2026-10-05-lab/GESAMTBERICHT-PUMP-IDLE-BURST-REALISM.md) | **Lab Idle+Burst:** Pump-Ceiling ~70 KB/s · Prefill≥Burst async PASS |
| 0L12 | [`artifacts-2026-10-06-lab/lab88-async-064741-burst-then-slow/NOTE-BURST-THEN-SLOW.md`](artifacts-2026-10-06-lab/lab88-async-064741-burst-then-slow/NOTE-BURST-THEN-SLOW.md) | Burst-then-Slow: und=0, behind≠0 (kein formaler PASS) |
| 0L13 | [`artifacts-2026-10-06-lab/GESAMTBERICHT-BULK-DRAINTCP-046.md`](artifacts-2026-10-06-lab/GESAMTBERICHT-BULK-DRAINTCP-046.md) | **Lab Bulk-drainTcp:** Idle ~840 KB/s · maxpump-hold PASS (Lab≠HU) |
| 0k7 | [`artifacts-2026-10-06-lab/KRITIK-REVIEW-MISTRAL-GPT-CLAUDE-IDLE-BURST-c99ac36.md`](artifacts-2026-10-06-lab/KRITIK-REVIEW-MISTRAL-GPT-CLAUDE-IDLE-BURST-c99ac36.md) | Review Idle/Burst — Ceiling→bulk bestätigt; Prefill-Linie überholt |
| 0k3 | [`artifacts-2026-10-05-lab/KRITIK-MISTRAL-LAB-FOLLOWUP-305b55f.md`](artifacts-2026-10-05-lab/KRITIK-MISTRAL-LAB-FOLLOWUP-305b55f.md) | Kritik Mistral 305b55f (lokal verifiziert) |
| 0k2 | [`artifacts-2026-10-05-lab/KRITIK-MISTRAL-GPT-KONSOLIDIERT-2026-10-05.md`](artifacts-2026-10-05-lab/KRITIK-MISTRAL-GPT-KONSOLIDIERT-2026-10-05.md) | Konsolidiert: Gate-Wortlaut schärfen |
| 0L | [`artifacts-2026-10-05-lab/lab88-lock-after-rst-1022/GESAMTBERICHT-LOCK-AFTER-RST.md`](artifacts-2026-10-05-lab/lab88-lock-after-rst-1022/GESAMTBERICHT-LOCK-AFTER-RST.md) | Lab: Meta-Erstsiegel-Mechanismus (**Feldmorgen stark erklärt**, Seal-Log Feld fehlt) |
| 0menu | [`artifacts-2026-10-05-lab/lab88-menu-page-0816/GESAMTBERICHT-MENU-PAGE-AV-PREP.md`](artifacts-2026-10-05-lab/lab88-menu-page-0816/GESAMTBERICHT-MENU-PAGE-AV-PREP.md) | **Lab Menü-Seite PASS** + Abend-EAR |
| 0a1 | [`artifacts-2026-10-05-lab/lab88-correlate-meta-sender-0855/GESAMTBERICHT-CORRELATE-META-SENDER.md`](artifacts-2026-10-05-lab/lab88-correlate-meta-sender-0855/GESAMTBERICHT-CORRELATE-META-SENDER.md) | Correlate Meta=Negativ / Sender=Positiv **PASS** |
| 0a2 | [`artifacts-2026-10-05-lab/LAB-NEXT-MENU-AV-2026-10-05.md`](artifacts-2026-10-05-lab/LAB-NEXT-MENU-AV-2026-10-05.md) | Lab-Auftrag (Plan, erledigt) |
| 0b | [`artifacts-2026-10-04-lab/lab88-av-mpeg-2035/GESAMTBERICHT-AV-MPEG-AT-HOST.md`](artifacts-2026-10-04-lab/lab88-av-mpeg-2035/GESAMTBERICHT-AV-MPEG-AT-HOST.md) | Lab AV A+B PASS |
| 1 | [`artifacts-2026-10-05-feld/feld-q3b-next-0744/`](artifacts-2026-10-05-feld/feld-q3b-next-0744/) | C′ Artefakte (GATE+Watchdog PASS) |
| 2 | [`artifacts-2026-10-05-feld/feld-av-0750/`](artifacts-2026-10-05-feld/feld-av-0750/) | AV Correlate: stream off / live=0 |
| 3 | [`artifacts-2026-10-04-feld/feld-q3b-next-1738/GESAMTBERICHT-FELD-Q3B-1738.md`](artifacts-2026-10-04-feld/feld-q3b-next-1738/GESAMTBERICHT-FELD-Q3B-1738.md) | gestern C′ FAIL (Seed tot bei GO) |
| 4 | [`PLAN-NACH-M3-AE-2026-10-03.md`](PLAN-NACH-M3-AE-2026-10-03.md) | Freeze |

---

## 2. Ampel

| Thema | Stand |
|-------|--------|
| HU-Modell (File-Cache / Eager-Read) | 🟢 belegt (feld-av-0723 + ANALYSE) |
| Hebel | **MSC-Stall / Backpressure** — nicht Prefill≥400 KiB / PSRAM |
| Bulk-drainTcp / Lab Hold | 🟢 Lab · **≠** Feld-AV |
| AV / Ohr Feld | 🔴 kein Ton unter 0.4.46 |
| Detect / Gate / Freeze | 🟢 / 🟢 / hält |
| Sequenz-GO | gesperrt bis hörbarer AV |
| Stall-FW | spezifiziert, **Go nötig** |
| Decode-Start (inkrementell?) | ❓ Stufe 1 |

---

## 3. Nächste Schritte

1. **Feld (ohne FW):** Stufe 1 — Decode-Start (Spielzeit vs. Lesefortschritt) + Cache/Remount (`Stufenplan` / `MASSNAHMEN`).  
2. **Lab parallel:** Spike-Rest 2a · `nbt_hu_sim` + Golden G1–G5.  
3. **Danach Go:** Stall hinter Flag (0.4.47) · Bridge-Drossel an Bitrate · Auto-Leiter 128k.  
4. **Stoppen:** Prefill≥400 KiB, Ring/PSRAM als Burst-Puffer, Detect-Umbau.

```
Burst = Dateirest, nicht Decoder-Puffer
HU bremsen (Stall), nicht nur füttern
Nächstes: Stufe 1 Auto ∥ Lab-Sim
```
