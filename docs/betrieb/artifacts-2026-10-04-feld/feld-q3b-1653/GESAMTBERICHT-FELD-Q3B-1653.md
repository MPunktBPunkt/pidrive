# Feldbericht — Q3b Prefill Session 16:53–16:57 — PD0060

**Datum:** 2026-10-04 · Fahrzeug-ESP `.89` · Bridge `.105`  
**FW:** OTA `0.4.42-dev` → **`0.4.44-dev`** (Serial blieb **PD0060**)  
**Artefakt:** `docs/betrieb/artifacts-2026-10-04-feld/feld-q3b-1653/`

---

## 1. Ampel dieser Session

| Prüfpunkt | Status | Beleg |
|-----------|--------|-------|
| Prefill Seed B ab LBA 761 | aktiv | SoftAP Oracle A `Q3B1B` ok |
| P1 / Auto-Next Body | **EVIDENCED** | Trace 16:55:45–57, LED, Operator |
| Feld-Oracle B (HU fordert Body) | **PASS** | ≥761 inkl. 1953, ~5,0 MiB body |
| `cold_body_burst` | **PASS (Log)** | mehrfach, immer `ev=not_from_head` |
| Detect-Policy | unverändert | Play über **Head** (`from=81`), nicht über Cold |
| Feld-Oracle C (Seed an HU) | **FAIL / blockiert** | Live-Overlay maskiert Seed |
| AV / Ohr | **FAIL** | Operator 16:57 kein Ton; `liveBytes=0` |

---

## 2. Was passiert ist (Zeitlinie)

1. ~16:54 OTA 0.4.44, Seed B, Traces geleert, kein Remount.  
2. Operator: Kurztrack → Autoplay **Rock** ~16:55, LED blinkt.  
3. USB-Trace: dichter fav0-Body-Read 16:55:45–57 (LBA bis ~15984).  
4. Detect: Head-Read `seq_short`→Play → `audio.start fav0` → Live-Ring aktiv.  
5. Cold-Bursts weiter als `not_from_head` geloggt (Diagnose ok).  
6. Status: `streamBytes == underruns` → **liveBytes=0**; `hostAbsCursor` weit vor `absEnd` (Ring-Fenster verfehlt).  
7. 16:57: **kein Ton**.

---

## 3. Kernbefund (Ursache kein Ton trotz Body-Reads)

Zwei getrennte Mechanismen:

**A) Seed vs Live (Q3b Oracle C)**  
`onRead` priorisierte bei aktivem Stream den Ring. Seed B galt nur im Non-Live-Zweig.  
→ Sobald Detect `audio_start` auslöste, bekam die HU **Underrun-Silence**, nicht Prefill-B.

**B) Live-Producer / Cursor (AV)**  
Selbst der Ring lieferte keine nutzbaren Live-Bytes (`underruns` = `streamBytes`).  
`hostAbsCursor` ≫ `absEnd` → Host liest außerhalb des gepufferten Fensters.

Seed≠Producer bleibt gültig: Selbst mit Seed-Fix ist Q3B1-Muster **kein gültiges MP3** → hörbarer Musikton ist nicht das Erfolgskriterium des nächsten Seed-Laufs.

---

## 4. Nächster Test (vorbereitet)

**FW `0.4.45-dev`:** Bei aktivem `body_seed` gewinnt Seed im Body (`fileOff≥fromOff`) **auch gegen Live**. Zähler `bodySeed.bytesServed`.

**Ziel nächster Lauf (getrennt):**

| Stufe | Erfolg |
|-------|--------|
| Feld-Oracle B | erneut HU-Body-LBAs im Trace |
| Feld-Oracle C' | `bodySeed.bytesServed` steigt während Burst (ESP hat Seed wirklich ausgeliefert) |
| AV mit Seed | weiterhin eher nein (kein MPEG) — nicht als PASS erwarten |
| AV/Producer | eigener Track nach Seed-Beweis (Cursor/Underrun) |

Skript: `tools/feld_q3b_next_prepare.sh` · EAR im Ordner `feld-q3b-next/`.

---

## 5. Freeze / Regeln

Detect-Policy unverändert · Ring/PSRAM/Pacing unverändert · Seed-Override ist Lab/Feld-Diagnosepfad nur bei aktivem `body_seed` (default aus).
