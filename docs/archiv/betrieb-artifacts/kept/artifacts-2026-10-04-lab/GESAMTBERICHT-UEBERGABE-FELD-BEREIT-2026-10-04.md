# Gesamtbericht — PiDrive / ESP32 MSC / BMW NBT

**Stand nach Detect-Diagnose-Lab — 04.10.2026**  
**Gesamturteil:** Übergabe **freigabefähig**. Lab-Vorbereitung abgeschlossen. Nächster Schritt: **Feld** mit echter HU, Prefill ab LBA 761, HU-Trace, Ohr/Film. Detect-Policy unverändert.

Konsolidiert aus Mistral-/GPT-Review + eigener Nachprüfung gegen Artefakte/`origin/main`.

---

## Repository- und Firmware-Stand

| Komponente | Stand |
|------------|--------|
| `MPunktBPunkt/pidrive` | `1d7afd8aafcddaa24bb7aa4f017279b8e4f55e77` |
| `MPunktBPunkt/esp32.pidrive` | `14100254fe26bf78a263ef4f8d315e3f1240a3c1` |
| Firmware | `0.4.44-dev` (Detect-Log); Q3b-Lab lief auf `0.4.43-dev` body_seed |
| Lab-Gerät | ESP `.88`, Serial `PD0042` (zum Prüzeitpunkt offline OK) |
| Q3b-Artefakt | [`lab88-q3b-1515/`](lab88-q3b-1515/) |
| Detect-Artefakt | [`lab88-detect-cold-1536/`](lab88-detect-cold-1536/) |
| Offline | [`detect-cold-vs-warm-offline/`](detect-cold-vs-warm-offline/) |

Beide Repos gegen `main`: identical / synchron.

**Einstieg:** [`../MSC-AKTUELL.md`](../MSC-AKTUELL.md) → **dieses Dokument**.

---

## 1. Verbindliches Urteil

Lab-Vorbereitung abgeschlossen:

- Q3b Prefill-Lab PASS · O1 geschlossen · Tool-Präzisierungen (len-check, Oracle-B-Klarstellung) · `cold_body_burst` Log only · Cold/Warm belegt · keine Schaltwirkung · gepusht.

**Neuer Diagnosebefund:** Detect verwirft Cold-Body als `not_from_head`; Warm-/Head-Pfad kann später `play.guess` auslösen. **Keine Policy-Freigabe.**

Nächster Schritt ist **Feld, nicht weiteres Lab**.

---

## 2. Prüfpunkte

| Prüfpunkt | Status |
|-----------|--------|
| P0 | PASS — nicht anfassen |
| P1 | EVIDENCED / PASS_WEAK — Anchor≠UI-Timer |
| O1 | GESCHLOSSEN — Prefill ab **761** |
| Q3b Lab | PASS — MSC-Datenebene; Seed≠Producer |
| Detect-Diagnose | LAB PASS — Log only |
| Detect-Policy | UNVERÄNDERT |
| Q3b Feld / HU-Oracle B | OFFEN |
| Feld-Oracle C | OFFEN |
| AV | OFFEN / bisher FAIL |
| `bufferMs` | tote Telemetrie — ignorieren |
| Freeze | HÄLT |
| Sequenz-GO | GESPERRT |

Kein Erfolg überträgt sich automatisch auf einen anderen Prüfpunkt.

---

## 3. Verifizierte Umsetzung

### 3.1 Q3b-Tool
- `len(blob) == sectors * 512` vor Muster-PASS  
- Oracle B = `lab_controlled_host_dd` (nicht HU)

### 3.2 FW `0.4.44-dev`
- `noteColdBodyRead` / `emitColdBodyBurst` aus `noteDataRead`  
- Schwelle 32768 B · Gap-Reset 2000 ms · Cooldown 3000 ms  
- Kein `play_uid` / Stream-Arm / Policy  
- Event = Aggregat, kein Ersatz für USB-Trace; `lba=x..y` = Min/Max, nicht lückenlos

### 3.3 Lab `lab88-detect-cold-1536` (nachgeprüft)
- `cold_body_burst`: `lba=761..824 n=64 B=32768 w=0 ev=not_from_head set=1`  
- `play.guess` nach Cold: **[]**  
- Warm-Kontrast: `play.guess` **ja**; davor/dabei auch `seq_short` / später `already_playing`  
  → nicht behaupten, jeder Warm-Read löse sofort Detect aus  
- Lab-Host-dd ≠ NBT-Burst

### 3.4 Offline PD0056/57
- Cold0: Span 753…4624, first≈1953 → `not_from_head`  
- Cold1: 4625…16456 → `not_from_head`  
- Regelauswertung historischer Traces, keine neue Feldmessung mit 0.4.44

---

## 4. O1 / Prefill (verbindlich)

- `lba0=81` · Kopf …760 · Prefill ab **761** (`fromOff=348160`)  
- Burst-0: 753…4624 · first_event 1953  
- `end = lba0 + bytes/512 − 1` (`lba1` ≠ Transfer-Ende)  
- Prefill ab 1953 ist falsch

---

## 5. Q3b-Lab-Beweisgrenze

Bewiesen: ESP liefert hinter eingefrorenem Kopf aktuelle Seed-Bytes über MSC an kontrollierten Host (A/B/C/Kontrolle).

Nicht bewiesen: HU-Anforderung · Live-Producer · Dekodierung · hörbarer Ton.

**Seed ≠ Producer · Q3b Lab ≠ Q3b Feld · Q3b ≠ AV.**

---

## 6. Nächster Auftrag: Feld

1. Prefill ab 761 · Kopf unverändert · klares Testsignal · P0-Lock · kein Remount.  
2. `0.4.44-dev` nur nach bewusster Freigabe auf Fahrzeug-ESP; Version dokumentieren.  
3. Kurzdatei → Auto-Next → Cold-Burst · Film (UI-Timer+LED) · Ton · USB-Trace · ESP-Status · `cold_body_burst` nur Log.  
4. Getrennt: P1 (UI-Timer) · Feld-Oracle B (HU-Trace) · Feld-Oracle C (MSC→HU Bytes) · AV (Ohr) · Detect (Log vs Trace).  
5. Freeze hält. Sequenz-GO gesperrt.

---

## 7. Detect-Log im Feld lesen

- Emit erst ab ≥32 KiB; Gap >2 s reset; Warm-Head reset; nach Emit Volumen reset, Span bleibt zunächst  
- Kein Event ≠ keine Body-Reads — immer gegen USB-Trace halten  
- `ev=not_from_head` = Aggregatbewertung

---

## 8. Fehlinterpretationen (kurz)

Lab≠HU · Event≠Trace · Span≠lückenlos · Warm-guess≠jeder Read · Seed≠Producer/AV · LED/`audio_ack`≠AV · keine Policy vor Feld · kein Ring/PSRAM · keine Prüfpunkt-Verschmelzung · 0.4.44 nicht ungeprüft im Auto.

---

## 9. Fazit

Lab-Phase zu. Offene Frage nur noch die echte NBT: fordert sie die Body-LBAs an, erhält sie die Daten, dekodiert sie hörbar?  
**Feldversuch.** Detect nur loggen. Freeze hält. Sequenz-GO gesperrt.
