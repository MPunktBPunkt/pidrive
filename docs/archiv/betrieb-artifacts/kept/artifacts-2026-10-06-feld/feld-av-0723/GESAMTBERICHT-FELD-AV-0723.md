# Gesamtbericht Feld AV — 2026-10-06 (`feld-av-0723`)

**Fahrzeug:** BMW / HU USB-OTG · ESP `.89` · Bridge `.105`  
**FW:** OTA **0.4.46-dev** (Bulk-`drainTcp`, Lab ~840 KB/s) — startete als 0.4.45  
**PASS-Kriterium:** `live>0 ∧ und=0 ∧ behind=0` anhaltend + Ohr  
**Ergebnis:** **AV FAIL** (kein Ton die ganze Session) · Detect teils PASS

---

## Timeline (kurz)

| Zeit | Ereignis |
|------|----------|
| 07:50 | ESP online, weiß = kein OTG |
| 07:51 | OTA → **0.4.46-dev**; Gate PASS; `MSC_MAP_FROZEN` |
| 07:51–53 | Autoplay BOB→Bayern→Rock; LED Body; kein Ton; Bridge Crash-Loop kurz |
| 07:55–57 | RST×2; PD0082→**PD0084** nach Replug |
| **07:58** | **Bayern Detect PASS** (`audio_start fav1`, armed) — Host-Burst **~438 KiB** → `und=438272`, `live=0`, `hostAbs` fest |
| 08:00 | Rock ohne LED (Cache); BOB Detect, `hostAbs=0`, kein Ton |
| 08:01–03 | OTG Replug + RST |
| 08:04 | Bayern Detect + LED, aber `armed=False`/`hostAbs=0` |
| 08:05–08 | weitere RST; schnelle Wechsel |
| 08:10–13 | RST-Runde: Detect oft, zeitweise `armed` + `hostAbs` bis ~4 MiB / `und` bis ~6 MiB, **`live=0`**, Ohr still |

---

## Befunde

1. **0.4.46 allein reicht im Feld nicht** für hörbares Streaming — Lab-Hold-PASS transferiert nicht 1:1.
2. **Zwei Silence-Muster:**
   - **A:** Arm + HU-Erstburst ≫ Prefill/Fenster → nur Underruns (`07:58`, Runde `08:10`).
   - **B:** Detect/Producer an, HU liest nicht den Live-Ring (`hostAbs=0`, Cache/Prefetch/LED only).
3. **LED ≠ Ton** — Body/cold bestätigt; kein Live-MPEG-Beweis.
4. Gate/Freeze/Detect funktionieren wiederholt; **Sequenz-GO bleibt gesperrt**.

---

## Artefakte

Ordner: [`feld-av-0723/`](.)  
Operator: [`OPERATOR-NOTES.txt`](OPERATOR-NOTES.txt) · Runde: [`runde-0810/`](runde-0810/) · Correlate-Läufe: `correlate-run*`

---

## Nächste Schritte (nicht im Auto)

- Prefill/Hold an **Feld-Erstburst ≥400 KiB** (nicht nur 48 KiB-Ring) ausrichten  
- hostAbs=0-Fälle: warum HU nach Detect keinen Head-Cursor fährt (Cache vs. Geometrie)  
- Kein Detect/Lock-Umbau ohne Lab-Repro dieser zwei Muster
