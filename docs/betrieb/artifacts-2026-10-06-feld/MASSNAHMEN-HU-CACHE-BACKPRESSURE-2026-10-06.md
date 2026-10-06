# Maßnahmen: HU-File-Cache + MSC-Backpressure (Konsolidierung 2026-10-06)

**Stand:** 2026-10-06 Abend (Nachzug Reviews s1-1700) · **HEAD-Bezug:** `44eb102` + C1-Fix  
**Quellen:** `summary-2026-10-06.txt` · `ANALYSE-HU-FILE-CACHE-BACKPRESSURE-2026-10-06.md` · `HU-Technical-Facts.md` · `KONZEPT-HU-SIM-NBT-2026-10-06.md` · `SPIKE-TINYUSB-READ10-2026-10-06.md` · `Stufenplan.md` · Mistral-/GPT-Review feld-s1-1700 · Lab NOTE

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
| Decode-Start inkrementell vs. after_eof | ❓ | **M4/F1 — nicht entschieden** (s1-1700 Teilerfolg) |
| Cache Abwahl / Remount | ❓ | **M5/F2 — unvollständig**; RST-Teil: USB-Re-Read fav2 |
| LED ≈ cold_body / MSC-Aktivität | 🟢 [S] | HU-Facts R14; kein absoluter Cache-Beweis |
| G1-Assertion C1 (und==expect, nicht OR-Kaskade) | 🟢 | `nbt_hu_sim` pre_arm vor Arm + strikte Checks |
| Klassifikator OTHER dominant (C2) | 🟢 | Phasen-tolerant; G1 OTHER=0 / silence_ratio=1.0 |
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
| **M1** | Stufe 0: `run.yaml`-Vorlage + 1-s-Status-Poll mit Wanduhr (Marker-Schalter darf warten) | Pi/Repo | ✅ + Ingest Parquet/DuckDB (`tools/ingest/`) |
| **M2** | Spike-Rest Stufe 2a: Arduino-Wrapper `USBMSC` / USB-Task-Prio / `CFG_TUD_MSC_EP_BUFSIZE` auf Debian lesen | Lab | ✅ Spike-Doc Nachtrag |
| **M3** | `nbt_profile_extract.py` + Profil `nbt_evo_2026-10-06.json` aus `feld-av-0723` | Lab | ✅ gap median 4 ms, n=4096 |

### Nächster Feldtermin (ohne FW-Änderung) — **höchste inhaltliche Priorität**

| ID | Maßnahme | Abnahme |
|----|----------|---------|
| **M4 = Stufe 1 F1** | Decode-Start: Spielzeit-Zähler vs. `slotMap.fav0.b` (8 MiB Silence, Bridge stop) + Video | ❓ **nicht entschieden** (s1-1700: kein Timer/Video) |
| **M5 = Stufe 1 F2** | Cache über Abwahl / Remount (`fav1→fav2→fav1`, OTG) | ❓ unvollständig; RST-Teil siehe `F2-TEIL-s1-1700.md` |
| **M6** | Ergebnisse → `HU-Technical-Facts.md` Q1–Q3 / R12–R14 | R14 ✅; Q1–Q3 / R12–R13 weiter offen |

### Nach F1/F2 (eigenes Paket, nicht Stall)

| ID | Maßnahme | Abnahme |
|----|----------|---------|
| **M13 = Q4a–c** | Eager einer Datei + Multi-File-Cache-Matrix + Eviction — **getrennt** von Live-Stall | siehe [`EXPERIMENTKATALOG-Q4-…`](EXPERIMENTKATALOG-Q4-CACHE-MARKER-2026-10-07.md) |
| **M14** | Marker-Blöcke / Offset-Log (Diagnose Cursor vs Producer) | READ-Map mit Pattern A/B/C…; kein Silence-als-Zukunft hinter Live-Grenze |

### Lab parallel (zweite Instanz)

| ID | Maßnahme | Abnahme |
|----|----------|---------|
| **M7** | `nbt_hu_sim.py` + Golden G1–G5 gegen 0.4.46 L3 | ✅ 3× ALL + **all-c1** + **all-c2** (C1+C2) |
| **M7b** | G6 Lab-F2-Rehearsal (Sim-Cache / Remount) | ✅ `lab88-nbt-hu-sim-g6` — ersetzt nicht Feld M5 |
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

1. **Feld (Priorität):** M4/F1 per Video + Spielzeit-Zähler; M5/F2 `fav1→fav2→fav1` + OTG-Remount — **kein** Stall-OTA. Siehe aktualisiertes [`feld-s1-1700/ARRIVAL.md`](feld-s1-1700/ARRIVAL.md).  
2. **Lab:** C1+C2 erledigt (`all-c2`); G6 Lab-F2-Rehearsal grün.  
3. **Stall-Go erst wenn:** F1 entschieden. Kein `stall_ms`-Flash vor Go.  
4. **Danach (nicht morgen vermischen):** M13 Q4a–c Cache-Kapazität; M14 Marker; Live-Grenze@X nur mit Stall-FW.

**PASS-Kriterium unverändert:** `live>0 ∧ und=0 ∧ behind=0` anhaltend + Ohr — aber Interpretation von `hostAbs`-„Burst“ ist nicht mehr Ringmaß.

**Cursor-Klarstellung (GPT 2026-10-07):** Bekannte Dateidaten helfen zur Positionsdiagnose; Silence bei Miss simuliert eine **falsche Zukunft** — die HU holt diese Offsets nicht erneut. Streaming braucht Backpressure, nicht nur „File vorher füllen“. Drei Slots reichen nicht für Cache-Größe → Q4b.

## 8. Ampel nach s1-1700 + Reviews

| Thema | Ampel |
|-------|-------|
| Stufe 0 Messbarkeit | 🟢 |
| Stufe 2 Lab Golden (aktuelle 3× ALL) | 🟢 |
| Feldformat / Profil 4 ms·4 KiB | 🟢 |
| Muster A/B + Feld-Replay | 🟢 |
| C1 G1-Assertion | 🟢 |
| C2 Klassifikator OTHER | 🟢 (phase-tolerant) |
| G6 Lab-F2-Rehearsal | 🟢 (Sim; Feld F2 offen) |
| M4/F1 Decode-Start | 🔴 offen |
| M5/F2 Cache/Remount | 🔴 offen (RST-Teil [S]) |
| Stall-FW / Stufe 3+ | 🔒 Freeze |
