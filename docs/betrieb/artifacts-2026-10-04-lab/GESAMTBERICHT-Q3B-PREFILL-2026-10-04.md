# Gesamtbericht — Q3b Prefill Lab PASS — 2026-10-04

**Commit-Kette:** pidrive (dieser Push) · FW `esp32.pidrive` **0.4.43-dev** (Lab body_seed)  
**Lab:** ESP `.88` Serial `PD0042` · Host CT `.187` `/dev/sda` · Artefakt [`lab88-q3b-1515/`](lab88-q3b-1515/)  
**Einstieg:** [`../MSC-AKTUELL.md`](../MSC-AKTUELL.md)

---

## 1. Ergebnis

| Prüfpunkt | Status |
|-----------|--------|
| **Q3b Lab (MSC-Datenebene)** | **PASS** |
| Test A (seed A + Oracle A + host) | PASS |
| Test B (seed B SoftAP, kein Remount) | PASS |
| Test C (A→B, Cold-Burst-Sim, Oracle B+C, Kopf eingefroren, LBA 761=B) | PASS |
| Kontrolle (zurück A, kein Remount) | PASS |
| AV hörbar / Detect-Policy / P1 voll-GRÜN | **nicht** Teil dieses Laufs |

**Leitfrage beantwortet (Lab-Host):** Hinter eingefrorenem Scan-Kopf (LBA ≤760) liefert der ESP beim Body-Read ab LBA **761** die **aktuellen** Seed-Bytes über den echten MSC-Pfad (`dd iflag=direct` = USB-MSC-Response). A→B ohne Remount funktioniert; Region 761–1952 ist mit vorbefüllt (O1-Konsequenz bestätigt).

---

## 2. Was gebaut wurde

### Firmware `0.4.43-dev` (nur Lab, kein Ring/PSRAM/Detect)

- `LabBodySeed.h` — deterministisches 16-Byte-Zellmuster `Q3B1`+Tag+fileOff+Checksum
- `UsbMscGadget::onRead` — bei aktivem Seed und `fileOff >= fromOff` statt Silence
- SoftAP:
  - `POST /api/lab/body_seed` `{"slot":0,"tag":"A"|"B"|"off","fromOff":348160}`
  - `GET /api/lab/body_read?slot=0&off=&n=` (Oracle A ohne Host)

### Tool

`tools/m3_lab_q3b_prefill.py` — Testmatrix A/B/C/Kontrolle mit Oracles A/B/C.

---

## 3. Oracle-Nachweise (Lab)

| Oracle | Umsetzung | Ergebnis |
|--------|-----------|----------|
| **A** Slot-Inhalt | SoftAP `body_read` == erwartetes Muster an LBA 761,1000,1472,1953,3000,4624 | PASS |
| **B** Host-Zugriff | Lab-simulierter Cold-Burst (`dd` nach `t_switch` auf Burst-LBAs inkl. **761**) | PASS (⚠ nicht HU) |
| **C** MSC-Auslieferung | Host-`dd`-Bytes == Muster B; zuordenbar zu LBA/Länge | PASS |

**Disclaimer:** Oracle B im Lab ist **host-simuliert**, nicht die BMW-HU. Feld muss B mit echtem USB-Trace wiederholen. Oracle C misst die **tatsächliche MSC-Response** an den Host (Linux), nicht nur SoftAP/Ring.

**Kopf eingefroren:** Hash LBA 181 vor/nach A→B identisch · `remountGen` unverändert.

---

## 4. Abgleich GPT-Abnahmekriterien

| Kriterium | Lab |
|-----------|-----|
| A vor Wechsel im Slot | ja |
| B ab LBA 761 nach Wechsel; Kopf 0–760 unverändert | ja |
| Cold-Burst-Reads nach Wechsel liefern B blockweise | ja (simuliert) |
| Kontrolle ohne A→B-Wechsel / kein Remount | ja (zurück auf A) |
| Abbruch wenn nicht zuordenbar | n/a — zuordenbar |

---

## 5. Nächste Schritte

1. **Detect:** `cold_body_burst` nur loggen (Warm vs Cold) — keine Policy.
2. **Feld:** gleicher Prefill + Ohr/Film + UI-Timer; Oracle B aus HU-Trace.
3. Freeze Ring/PSRAM/Pacing hält. Sequenz-GO weiter gesperrt bis AV.
4. `bufferMs`-Fix nachrangig.

---

## 6. Vermeidete Fehler

- Prefill ab 1953 → wäre Lab-C an LBA 761 durchgefallen; ab **761** gewählt.
- `bufferMs` nicht als KPI.
- Kein Detect-Umschalten, kein Ring/PSRAM.
- Q3b-PASS ≠ AV-PASS.
