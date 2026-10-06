# Maßnahmen: HU-File-Cache + MSC-Backpressure (Konsolidierung 2026-10-06)

**Stand:** 2026-10-06 Abend · **HEAD-Bezug:** `3ae4207` (+ Feld `ec56935`/`a1d76b5`, Lab bulk `1464c3c`)  
**Quellen:** `summary-2026-10-06.txt` · `ANALYSE-HU-FILE-CACHE-BACKPRESSURE-2026-10-06.md` · `HU-Technical-Facts.md` · `KONZEPT-HU-SIM-NBT-2026-10-06.md` · `SPIKE-TINYUSB-READ10-2026-10-06.md` · `Stufenplan.md` · Mistral-Review feld-av-0723 (§1–9) · GPT-Plan (in summary)

**Normativer Plan:** [`docs/planung/Stufenplan.md`](../../planung/Stufenplan.md) — dieses Dokument leitet **Maßnahmen + Ampel** ab und korrigiert überholte Hebel.

---

## 1. Kurzfazit

| Alt (bis Feldmorgen) | Neu (nach Querschnitt) |
|----------------------|------------------------|
| „Erstburst ≥400 KiB → Prefill/PSRAM/größerer Ring“ | **Burst = ungelesener Dateirest**, nicht Decoder-Puffer |
| Muster A vs. B als zwei AV-Probleme | **Ein Mechanismus:** Eager-Read bis EOF/Abwahl + Cache |
| Lab Hold-PASS (0.4.46) → Feld-Hoffnung | Lab-Host las **nicht** wie die HU → Transfer negativ belegt |
| Hebel: füttern | Hebel: **bremsen** (MSC Stall / Flow-Control) |

**Ein Satz:** Die HU muss gebremst werden, nicht nur gefüttert — und vor dem Stall-FW muss im Auto geklärt werden, ob sie **inkrementell** oder **Batch-then-Play** abspielt.

---

## 2. Was experimentell feststeht (Ampel-Kern)

| Thema | Stand | Beleg |
|-------|-------|-------|
| Bulk-`drainTcp` Idle ~840 KB/s | 🟢 | Lab A1 |
| maxpump-hold 248 KiB Lab PASS | 🟢 | A2 — **nicht** feldrelevant unter neuem Modell |
| Feld 0.4.46: Detect OK, **kein Ton**, `live=0` | 🔴 | feld-av-0723 |
| Burst = Restdatei (86k+438k = 524288, …) | 🟢 | ANALYSE B1–B3, summary |
| Muster A/B = Timing Arm vs. Datei-fertig | 🟢 | ANALYSE + HU-Facts R9 |
| Cursor++ bei Miss = Runaway | 🟢 | `StreamBuffer::readAt` |
| `liveBytes` nach Senderwechsel falsch | 🟢 | `streamBytesServed_` nur bei Remount |
| TinyUSB `return 0` / Teilantwort möglich | 🟢 Spike | Busy-Retry + 512-B-Regel |
| HU READ10-Timeout | ❓ | Stufe 5 |
| Decode-Start inkrementell vs. after_eof | ❓ | **Stufe 1 — kritisch** |
| Bridge-Drossel 9000 B/s < 128k-Echtzeit | 🟠 | Stufenplan N1 |
| Silence-Frame MPEG-1 44.1 vs Live MPEG-2 22.05 | 🟠 | Stufenplan N3 / R7 |

---

## 3. Überholte Maßnahmen (bewusst stoppen)

| Früher | Warum stoppen |
|--------|---------------|
| Prefill an ≥~400 KiB Erstburst | Burst ist Dateirest, kein Ringmaß |
| PSRAM / Ring vergrößern als Burst-Puffer | Ring muss nur ~4 KiB + Jitter fassen |
| Slot „Live ≤ 48 KiB“ als P2 (KRITIK c99ac36) | Unter Cache-Modell falsch priorisiert; großer Live-Slot erst **nach** Stall+inkrementell |
| Weiteres Prefill/Hold-Tuning ohne Stall | Obergrenze ~9 s Ton unverändert |
| Detect/Lock-Umbau | Detect funktioniert; Problem danach |
| Sofort `live_stall_ms` im Auto ohne Lab-Golden + F1 | Freeze + R2-Risiko |

---

## 4. Maßnahmen (priorisiert, an Stufenplan gekoppelt)

### Sofort / ohne Freeze (heute–Lab)

| ID | Maßnahme | Ort | Abnahme |
|----|----------|-----|---------|
| **M0** | Normative Korrektur in `MSC-AKTUELL`: Phase = **MSC-Backpressure / File-Cache**; Hebel Stall, nicht Prefill≥400k | Docs | ✅ |
| **M1** | Stufe 0: `run.yaml`-Vorlage + 1-s-Status-Poll mit Wanduhr (Marker-Schalter darf warten) | Pi/Repo | ✅ `templates/run.yaml`, `feld_status_poll.py` |
| **M2** | Spike-Rest Stufe 2a: Arduino-Wrapper `USBMSC` / USB-Task-Prio / `CFG_TUD_MSC_EP_BUFSIZE` auf Debian lesen | Lab | ✅ Spike-Doc Nachtrag |
| **M3** | `nbt_profile_extract.py` + Profil `nbt_evo_2026-10-06.json` aus `feld-av-0723` | Lab | ✅ gap median 4 ms, n=4096 |

### Nächster Feldtermin (ohne FW-Änderung) — **höchste inhaltliche Priorität**

| ID | Maßnahme | Abnahme |
|----|----------|---------|
| **M4 = Stufe 1 F1** | Decode-Start: Spielzeit-Zähler vs. `slotMap.fav0.b` (8 MiB Silence, Bridge stop) | **inkrementell** vs **after_eof** eindeutig |
| **M5 = Stufe 1 F2** | Cache über Abwahl / Remount | liest HU neu? → Muster-B-Heilung |
| **M6** | Ergebnisse → `HU-Technical-Facts.md` Q1–Q3 schließen (Status [B]/[H]) | Facts aktuell |

### Lab parallel (zweite Instanz)

| ID | Maßnahme | Abnahme |
|----|----------|---------|
| **M7** | `nbt_hu_sim.py` + Golden G1–G5 gegen 0.4.46 L3 | G1/G2/G4/G5 ✅ · G3 offen |
| **M8** | Producer **Echtzeit** (nicht 900 KB/s Lab-Hold-Illusion); Format-Stempel PDSQ | ✅ G5 8,7→6,1 KB/s + PDSQ; PDSQ-Ohr im Sim |

### Nach Go (Freeze-Bruch)

| ID | Maßnahme | Abnahme |
|----|----------|---------|
| **M9** | FW 0.4.47 hinter Flag: `streamBytesServed_=0` in `startStream`; `stall_ms`; Cursor nur bei Live; `return 0`+2 ms Delay; Teilantwort ×512 | `stall_ms=0` → G1–G5 bitgleich |
| **M10** | Pi: `AUDIO_TARGET_BPS = 1.5×bitrate/8` (128k → ≥24 KB/s); optional `--marker`; Format-A/B später | ✅ Bridge: dynamisch + `--marker` (Format-A/B später) |
| **M11** | Lab-Stall-Matrix (Stufe 4) → Auto-Leiter 128k (Stufe 5) | ≥30 s hörbar oder Timeout-Grenze bekannt |

### Fallback (nur wenn F1=Batch oder Stall scheitert)

| ID | Maßnahme |
|----|----------|
| **M12** | Dateikette 10–20 s Dateien (Stufenplan Fallback) — PSRAM erst hier |

---

## 5. Entscheidungsbaum (eine Seite)

```text
Stufe 1 F1?
├─ inkrementell ──► Stall-Pfad (M7→M9→M11) · Ring 48 KiB behalten
├─ after_eof     ──► Fallback Dateikette (M12) · Stall nur Hilfsmittel
└─ Read-Ahead-Fenster (bricht vor EOF) ──► Stall sehr geeignet; Fenstergröße messen
```

---

## 6. Bewertung der Reviews (Stichprobe)

| Quelle | Urteil |
|--------|--------|
| Mistral §1–8 (Prefill≥400 / Bridge-only tot) | Zahlen ✅ · Strategie **überholt** (§9.4 selbst korrigiert) |
| Mistral §9 / summary File-Cache | 🟢 Kernmodell übernommen |
| GPT-Reihenfolge Telemetrie→Mimic→Stall | 🟢 = Stufenplan |
| ANALYSE + HU-Facts + Spike + Konzept | 🟢 belastbare Arbeitsbasis |
| Stufenplan N1–N5 (Bridge-Drossel, MPEG-Mismatch) | 🟢 nicht vergessen bei 128k |

**Offen bewusst lassen:** R1 (HU-Timeout), R2 (Decode-Start), R3 (Cache/Remount), R7 (Format-Wechsel), 164-KiB-Fall 01.10.

---

## 7. Nächster konkreter Arbeitsschritt

1. **Lab:** G3 automatisieren + 3× `ALL`-Repro; danach Stall-Go vorbereiten.  
2. **Feld:** Stufe 1 F1/F2 (Silence, Video, `run.yaml`, `feld_status_poll.py`) — **kein** Stall-OTA.  
3. **Kein** Code für `stall_ms` bis Go + Golden grün (G3 inkl.).

**PASS-Kriterium unverändert:** `live>0 ∧ und=0 ∧ behind=0` anhaltend + Ohr — aber Interpretation von `hostAbs`-„Burst“ ist nicht mehr Ringmaß.
