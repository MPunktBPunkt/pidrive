# Lab-Session MSC M0→M3 — 2026-10-03 (ohne Auto)

**Zweck:** Saubere, nachvollziehbare Lab-Dokumentation des Tages, solange kein BMW-Feldzugriff möglich ist.  
**Repos:** `pidrive` · `esp32.pidrive`  
**Hardware:** ESP Lab `192.168.178.88` · Bridge-Pi `192.168.178.105` · USB-Host Proxmox `192.168.178.108` (`/dev/sda`, `/dev/sg0`)

**Leitaufträge:**  
[`AUFTRAG-MSC-HOST-READ-NACHWEIS`](../../auftraege/AUFTRAG-MSC-HOST-READ-NACHWEIS.md) Rev.4 ·  
[`AUFTRAG-M0-MESSINTEGRITAET`](../../auftraege/AUFTRAG-M0-MESSINTEGRITAET.md) ·  
[`UEBERGABE-MSC-BEWERTUNG-2026-10-03`](../UEBERGABE-MSC-BEWERTUNG-2026-10-03.md)

---

## 0. Evidenzklassen (für diese Datei)

| Klasse | Bedeutung |
|--------|-----------|
| **D** dokumentiert | Status-JSON, Host-`file -s`, Tool-Reports in `artifacts-2026-10-03-m3/` / `artifacts-2026-10-03-m0/` |
| **C** Code | `esp32.pidrive` Quellen (`Mp3Silence`, `MscGeometry`, Burst-`kBurstGapMs=50`) |
| **I** Interpretation | Lab-Host ≠ NBT; A–E nur für Lab-Host, bis Auto-Feld |

---

## 1. Tagesziel und Abgrenzung

### Ziel
1. Messintegrität (**M0**) beweisen.  
2. M3-Messpipeline ohne Live/Bridge-Overlay etablieren.  
3. Algorithmische Zeitmarker (PDMK) im Slot verifizieren.  
4. Geometrie bis **L3 (8 MiB Messdatei)** auf echtem **FAT16** bringen.  
5. Alles mit Artefakten und Commits absichern.

### Nicht-Ziele (bewusst)
- Ring / PSRAM / Remount-Karussell / BT-Hybrid  
- BMW-NBT-A–E (kein Auto)  
- Live-Overlay als Messvariable in M3  
- Plateau-Gate („Datei > Cache-Limit“)

---

## 2. Firmware-Leiter im Lab

| FW | Env | Geometrie | Marker | Commit (esp32.pidrive) |
|----|-----|-----------|--------|-------------------------|
| 0.4.37 | `pidrive-s3-l0` | 4 MiB, damals „FAT16“-Label | nein | früherer Stand |
| **0.4.40** | `pidrive-s3-l0` | **FAT12** 4 MiB / 1 MiB-Slots (Clusterzahl &lt;4085) | **PDMK** ~30 s | `b846410` |
| **0.4.41** | `pidrive-s3-l0-16m` | **FAT16** 16 MiB / 3×4 MiB | PDMK | `02c8755` |
| **0.4.42** | `pidrive-s3-l3` | **FAT16** 16 MiB / **fav0=8 MiB** + 2×512 KiB | PDMK | (dieser Push) |

**Wichtige Geometrie-Lehre (C+D):** Bei 4 MiB/4 KiB-Clustern ist die Clusterzahl ≈1018 → Hosts klassifizieren **FAT12**, auch wenn das BPB „FAT16“ sagt. Deshalb L0-4MiB bewusst FAT12-kodiert; echtes FAT16 erst ab 16 MiB (≥4085 Cluster).

**Host-Bestätigung FAT16 (D):**  
`file -s /dev/sda` → `FAT (16 bit)`, `sectors 32768`, `sectors/FAT 16` (Artefakte `lab88-16m-markers/host-fat.txt`, `lab88-l3-1526/host-fat.txt`).

**BPB+fsck Freigabe (D) — `lab88-l3-fat-verify-1615/`:**  
Reserviert=1, SPC=8, SPF=16, Root=32 Sektoren, Data-Start=65, **4087 Cluster** → Microsoft-FAT16 (Margin +2 über 4085). `fsck.fat -vn` bestätigt. Code↔BPB konsistent. Urteil **PASS_GEOMETRY_LAB** (knapp, nicht mehrdeutig). Details: [`AUTO-M3-READINESS-2026-10-03.md`](../AUTO-M3-READINESS-2026-10-03.md).

---

## 3. M0 — Messintegrität (Abschluss)

**Artefakte:** [`artifacts-2026-10-03-m0/`](artifacts-2026-10-03-m0/)  
**Tool:** `tools/m0_lab_mount_sweep.py`

### Normative Gleichung
```
ΔreadCount = Σ(burst.n) + ΔreadOverflow
```
nicht: `readCount = Anzahl JSONL-Zeilen`.

### Code-Semantik (C)
- `readCount`: SCSI-/Host-Reads; Reset nur an USB-Plug-Kante, **nicht** bei Soft-Remount.  
- `readsEmit`: Burst-Flushes (`kBurstGapMs=50`, `kBurstMaxN=32`).  
- `ΔreadsEmit` ≡ Anzahl exportierter JSONL-Zeilen (bei verbundenem Bridge).  
- Ohne `pump_bridge`: Export leer, `readsEmit` stagniert — trotz `readCount↑`.

### Abnahme Lab (D)
| Pass | Ergebnis |
|------|----------|
| `lab88-140905` | Lernlauf FAIL (Absolut-Gleichung / leerer Export) |
| `lab88-141005` | **PASS×2**: Δrc 296/295 = Σn; emitΔ = Zeilen |
| **`lab88-l3-m0-1542`** | **PASS×2 auf L3/0.4.42**: Δrc **457/457** = Σn; emitΔ = Zeilen; Spread same |

**Status M0:** geschlossen für Lab (auch unter L3-Geometrie 8 MiB). Feld weiterhin: leerer Export = Fail des Transporturteils; Session-Δ verwenden.

---

## 4. M3 — Marker und Timeline (Lab-Host)

**Artefakt-Index:** [`artifacts-2026-10-03-m3/`](artifacts-2026-10-03-m3/)

### 4.1 PDMK-Stamp (C)
In `Mp3Silence::fill`:
- ID3+Info-Head 252 B, Silence-Frames 156 B @ 48 kbit/s.  
- Alle `kMarkerIntervalBytes = 180000` (~30 s): Frame-Bytes 4..9 = `P D M K` + big-endian Index.  
- Sync-Header (0..3) bleibt erhalten.  
- Alignment-Fallstrick: `markerBodyOff(i)` kann `&lt; i*interval` sein → Stamp-Erkennung mit guess und guess+1 (Fix in 0.4.40).

### 4.2 Verify (D)
Tool: `tools/m3_lab_verify_markers.py`  
**Voraussetzung:** `POST /api/lab/stop` — sonst Live-Overlay statt Silence.

| Pass | Slot | Ergebnis |
|------|------|----------|
| `lab88-markers-1503` | 1 MiB fav0 | **6/6** |
| `lab88-16m-markers` | 4 MiB fav0 | **8/8** |
| `lab88-l3-1526` | **8 MiB** fav0 | **12/12** (weitere Marker existieren bis ~46) |

### 4.3 Timeline Sweep → Idle → Paced (D)
Tool: `tools/m3_lab_host_timeline.py`

Wiederkehrendes Lab-Host-Muster:
1. **Sweep** (Remount/Nudge): kurzer Burst, Bilanz oft `Δrc = Σn`.  
2. **Idle 45–90 s:** `Δrc = 0` — keine weiteren Payload-Reads.  
3. **Paced @ 6 KiB/s:** neue Reads nur weil Lab bewusst nachliest.

**Klassifikation (I, Lab-Host):** `A_then_forced_C`  
→ entspricht Muster **A/E** ohne Stimulus, **C** nur unter kooperativem Host.  
**Nicht** übertragbar auf NBT ohne Auto-Feld.

### 4.4 Marker↔Zeit-Korrelation (D)
Tool: `tools/m3_lab_marker_pace.py`

| Pass | FW | Crossings (t) |
|------|-----|----------------|
| `lab88-marker-pace-151344` | 0.4.40 | ~0.7 s / **30.3 s** / **60.4 s** |
| `lab88-l3-1526/marker-pace` | 0.4.42 | ~0.7 s / **30.1 s** / **60.1 s** / **90.1 s** |
| **`lab88-l3-langpace-1535`** | **0.4.42** | **12 Kreuzungen** m0–m11, spacing_mean **29.979 s** (360 s Fenster) |

Erwartung bei 6 KiB/s ≈ Marker-Offsets / 6000 — Übereinstimmung gut (D).  
Das belegt die **Messmethode** für spätere NBT-Cursor-Korrelation (Ebenen 1–3), nicht Live-Verwertbarkeit (Ebene 4).

### 4.4b Langpace L3 (D) — `lab88-l3-langpace-1535/`
- Dauer 360 s @ 6 KiB/s, stream OFF, fav0=8 MiB.  
- Pre-Verify PDMK idx 0/1/2 OK.  
- **12/12** Kreuzungen im Fenster (Marker 0…11); Marker 12 (~351 s Soll) knapp außerhalb der effektiven Cursorreichweite.  
- Spacing: mean **29.979 s**, min 29.38, max 30.05 — Raster stabil über ~5,5 min.  
- Fehler vs. 30‑s-Gitter ab m0: |err| ≤ 0,62 s, driftend Richtung 0.  
- `ΔreadCount` (Tool-Fenster) **4230** ≈ Sektoren der gepaced Payload (~1,9 MiB Cursor).  
- Tool-Anpassung: `nmark` jetzt dauer-/slotbasiert (kein Hard-Cap 12).

### 4.5 ffmpeg-Assets
`mp3/L1.mp3`, `mp3/L2.mp3` + `*.markers.json` — hörbare Beeps für spätere Ohr-Tests.  
ESP-Payload bleibt vorerst algorithmisches Silence+PDMK (kein 8 MiB-Blob im Flash).

---

## 5. L3-Geometrie 0.4.42 (Detail)

**Env:** `pidrive-s3-l3` · Flag `PIDRIVE_GEO_L3=1`  
**Ready-Detail:** `FAT16 L3 16MiB fav0=8M`

| Slot | Größe | Rolle |
|------|------:|-------|
| fav0 | **8.0 MiB** (16384 Sektoren) | M3-L3 Messdatei |
| fav1 | 0.5 MiB | Begleiter |
| fav2 | 0.5 MiB | Begleiter |
| Menue | 6 KiB | Action |

Ungleiche Slot-Größen über `MscGeo::kSlotSectors0/1/2` + angepasstes `slotRanges()` (C).

**Lab-Smoke L3 (D) — `lab88-l3-1526/`:**
- Host: FAT16, 32768 Sektoren  
- Marker verify 12/12  
- Timeline: Sweep Δ221 (Bilanz ok), Idle **0**, Paced Δ528 → `A_then_forced_C`  
- Pace 120 s: 4 Marker-Kreuzungen im 30‑s-Raster  

---

## 6. Vier Ebenen — Lab-Stand

| Ebene | Lab-Status |
|-------|------------|
| 1 Host-Read | **ja** (Sweep, Paced, Verify-dd) |
| 2 Read-Ahead | Lab-Host paced ≈ Cursor; NBT unbekannt |
| 3 Play-Read | nur unter Lab-Pacing nachgewiesen; Idle=0 |
| 4 Live-Verwertbarkeit | **nein** (M3 bewusst ohne Live) |

---

## 7. Betriebsregeln für weitere Lab-Läufe

1. Vor Marker-Tests: `POST /api/lab/stop` (Overlay killt PDMK).  
2. Nach Geometrie-OTA: Host-Größe prüfen (`/sys/block/sda/size`); ggf. USB unbind/bind.  
3. Soft-Remount: Counter **Δ** bilanzieren, nicht Absolutwerte.  
4. Bridge muss für JSONL-Export laufen; M0-Gleichung sonst nur über Status-Δ.  
5. Jeder Pass: Ordner unter `artifacts-YYYY-MM-DD-m3/` mit EAR + report.json.  
6. NBT-Aussagen nur mit Auto-Artefakt und nicht-leerem Trace.

---

## 8. Tools (pidrive)

| Tool | Aufgabe |
|------|---------|
| `m0_lab_mount_sweep.py` | M0 Bilanz 2× Remount/Nudge |
| `m3_make_marked_mp3.py` | ffmpeg L1/L2 Assets |
| `m3_lab_verify_markers.py` | PDMK-Stamps per dd |
| `m3_lab_host_timeline.py` | Sweep / Idle / Paced |
| `m3_lab_marker_pace.py` | Zeit↔Marker-Kreuzungen |

---

## 9. Offene Lab-Fragen / nächste Schritte

1. ~~Auto-Feld M3~~ → **done A_then_E** 2026-10-03 ([`AUTO-M3-FELD-2026-10-03.md`](AUTO-M3-FELD-2026-10-03.md)).  
2. **Nächster Plan:** M3seq kurze Dateien — [`../PLAN-NACH-M3-AE-2026-10-03.md`](../PLAN-NACH-M3-AE-2026-10-03.md).  
3. ~~Optional Lab-Langpace~~ → **done** 360 s / 12 Kreuzungen (`lab88-l3-langpace-1535`).  
4. ~~L3 FAT16 BPB/fsck~~ → **done** (`lab88-l3-fat-verify-1615/`, PASS_GEOMETRY_LAB).  
5. Optional: Xing-Varianten-Reihe 2 (erst nach Sequenz-Klarheit).  
6. L4 (50 MiB): erst nach Feld-Bedarf + neuer Geometrie-Abnahme.  
7. Ring/BT weiter eingefroren.

---

## 10. Commit-Anker (Stand Dokument)

| Repo | Thema | Hinweis |
|------|--------|---------|
| `esp32.pidrive` | 0.4.40 Marker, 0.4.41 16M, 0.4.42 L3 | `eaa65f7` (0.4.42) |
| `pidrive` | M0/M3 Artefakte + Tools + diese Session | `764c1f5` + Langpace-Nachzug |

**Lab live nach Session:** `.88` = **0.4.42-dev** L3 FAT16, Bridge auf `.88`, Host sieht 16 MiB FAT16.
