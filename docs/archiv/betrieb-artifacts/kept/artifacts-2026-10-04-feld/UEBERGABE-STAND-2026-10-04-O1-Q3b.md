# Übergabebericht — PiDrive / ESP32 MSC / BMW NBT

**Stand:** 2026-10-04 · nach Abgleich Mistral-/GPT-Übergaben · Commit `878b2c9`  
**Repository:** `MPunktBPunkt/pidrive`  
**Firmware:** ESP32 PiDrive `0.4.42-dev` · Bridge: `pump_bridge.py --msc-lock` · Fahrzeug: BMW F20 LCI / NBT Evo  
**Einstieg:** [`../MSC-AKTUELL.md`](../MSC-AKTUELL.md) → **dieses Dokument** → Rohtraces `p1-run-a|b/msc_reads.jsonl`

Erledigt vor dieser Übergabe: Trace-Verifikation · Gesamtbericht-Kritik · Lab `bufferMs`/Ring · Commit/Push.  
**Neu in dieser Übergabe:** O1 (LBA 753 vs 1953) aus Rohtraces **geschlossen**; Prefill-Grenzen verbindlich.

---

## 1. Gesamtbewertung (eigene Prüfung)

Mistral- und GPT-Übergaben sind in den Kernaussagen **richtig und freigabefähig**:

| Punkt | Urteil |
|-------|--------|
| P0 PASS | bestätigt |
| P1 EVIDENCED / PASS_WEAK | bestätigt (kaltes fav0-Body-Next, nicht „unmessbar“) |
| LED = Burst-Indikator ≠ AV | bestätigt |
| `bufferMs` = tote Telemetrie | bestätigt (Code + Lab) |
| PD0058 `liveBytes=0` | bestätigt; Fehlerstelle noch offen |
| Q3b/Prefill als Schritt 1 | bestätigt |
| Detect zuerst nur loggen | bestätigt |
| Freeze Ring/PSRAM/Pacing | bestätigt |
| Drei Oracles A/B/C (GPT) | **übernehmen** |
| Getrennte Prüfpunkte P1/Q3a/Q3b/AV/Detect | **übernehmen** |

**Einziger harter Nachtrag:** O1 ist nicht mehr offen — siehe §3. Prefill-Offset darf nur noch aus diesen Grenzen abgeleitet werden.

---

## 2. Verbindlicher Status

| Prüfpunkt | Status | Basis |
|-----------|--------|-------|
| **P0** Menü-Lock | **PASS** | Favoriten gesiegelt, `frozen_reject`, Lock in Bridge |
| **P1** Kalter Auto-Next | **EVIDENCED / PASS_WEAK** | 2× Muster 484 → Pause → 1479 Reads; Lauf B Burst1 +0,35 s zu Nominal 87,381 s; Anker = fav1-Touch, nicht UI-Uhr |
| **LED** | Burst-Indikator | ~87 s nach Kurztrack = diese Bursts; kein AV-Beweis |
| **bufferMs** | **TOTE TELEMETRIE** | nie geschrieben; Lab: Ring 6→48 KiB, Underruns 0, `bufferMs`=0 |
| **AV / PD0058** | **FAIL** | `streamBytes==underruns` → `liveBytes=0`; Stelle Producer↔Buffer↔Slot↔Silence offen |
| **Q3a** | **PASS_WEAK** | Host≠Silence; Oracle in Q3b integrieren |
| **Q3b** | **LAB PASS** (2026-10-04) | [`../artifacts-2026-10-04-lab/GESAMTBERICHT-Q3B-PREFILL-2026-10-04.md`](../artifacts-2026-10-04-lab/GESAMTBERICHT-Q3B-PREFILL-2026-10-04.md) — Feld-AV/HU-Oracle-B noch offen |
| **Detect** | **OFFEN** | Warm-Head feuert; Cold-Body → `not_from_head`; erst `cold_body_burst`-Log |
| **L4** | OFFEN, kein Blocker | fortlaufendes Lesen großer Dateien |
| **O1 LBA-Grenzen** | **GESCHLOSSEN** | §3 |

Ein Q3b-PASS setzt **nicht** automatisch AV oder Detect auf PASS.

---

## 3. O1 — LBA 753 vs 1953 (geschlossen)

### 3.1 Methodik (wichtig)

In `msc_reads.jsonl` ist **`lba1` nicht das Transfer-Ende**.  
Gültige Sektoren eines Events:

```text
end = lba0 + (bytes / 512) - 1
```

Auswertungen, die `range(lba0, lba1+1)` als gelesene Sektoren nehmen, sind **falsch** (blähen den Scan künstlich auf die ganze Datei auf).

### 3.2 Scan (PD0056/57, fav0, Datei ab LBA 81)

| Größe | Wert |
|-------|------|
| Scan-Bytes | ~385 024 B (~0,367 MiB transferiert) |
| Unique Sektoren | **688** |
| Dichter Kopf | LBA **81…760** (Ende dicht = **760**) |
| Sparse Peek | z. B. Dateiende `lba0=16457` (8 Sektoren) — **kein** voller Body-Scan |

### 3.3 Cold-Burst 0 (erster Auto-Next-Burst, ~10:51:58)

Beide Läufe A und der erste schwere Burst in den Traces:

| Größe | Wert | Rolle der alten Zahlen |
|-------|------|------------------------|
| Span (min…max gelesen) | **753…4624** | Claude **753** = Span-Minimum / BODY0-Schwelle |
| Erstes Event `lba0` | **1953** | GPT **1953** = Start des geloggten Burst-Events (HU springt mittig rein) |
| Unique / Dichte | ~3816 Sektoren, ~98,5 % des Spans | dichter Body-Read |
| vs. Scan | **3808 neu**, **8 Rescans** (753…760) | echtes Cold-Body beginnt bei **761** |
| Contiguous Runs | 753…1472 · 1529…4624 | Lücke ~1473…1528 |

Burst 1 (Fortsetzung, ~5 s später): Span **4625…16456**, `first_lba0=4625`, praktisch 100 % neu vs. Scan.

### 3.4 Auflösung in einem Satz

**753 und 1953 beschreiben dasselbe Burst-0-Muster auf zwei Ebenen — sie sind nicht austauschbar und nicht „0,33 vs 0,95 MiB Prefill“.**

- **753** = untere Span-Grenze (inkl. 8 Sektoren Rescan des Scan-Kopfs).  
- **1953** = `lba0` des ersten Burst-Events (nicht der Prefill-Start).  
- **Prefill-Body** = ab LBA **761** = Datei-Offset **(761−81)×512 = 348 160 B ≈ 0,332 MiB** hinter Dateianfang / dicht hinter Scan-Kopf.

### 3.5 Verbindliche Prefill-Grenzen

| Region | LBA (absolut) | Offset ab Dateistart (LBA 81) | Inhalt |
|--------|---------------|-------------------------------|--------|
| Scan-Kopf (einfrieren) | 81…760 | 0 … ~340 KiB | unverändert während Q3b |
| Prefill-/Oracle-Body | **761…≥4624** (mind. Burst-0-Span) | **ab ~340 KiB** | deterministische B-Nutzdaten |
| Optional Burst-1 | 4625…16456 | ab ~2,27 MiB | zweite Welle; nicht Blocker für ersten Oracle |

Der früher genannte Korridor **~0,33–0,5 MiB** bleibt gültig als **Kopfende**; Prefill liegt **dahinter**, nicht ab 1953.

---

## 4. Q3b / Prefill — Auftrag an die nächste KI

### 4.1 Ziel

Nachweisen: Beim Cold-Burst fordert die HU aktuelle Body-Bytes an und bekommt sie über MSC ausgeliefert.

### 4.2 Drei Oracles (alle nötig)

| Oracle | Misst | Nicht verwechseln mit |
|--------|-------|------------------------|
| **A** Slot-Inhalt | Erwarteter Inhalt der LBA-Region **vor** HU-Zugriff | Ring-/Buffer-Interna allein |
| **B** Host-Zugriff | USB-Trace: HU liest genau die erwarteten LBAs (Burst-0-Muster) | „irgendein Read“ |
| **C** MSC-Auslieferung | Bytes der **USB-MSC-Antwort** == erwartete B-Daten, zuordenbar zu LBA/Read | lokaler Slot-Oracle ohne Response-Pfad |

Nur **A+B+C** = Datenfrische. Oracle C muss die **tatsächliche MSC-Response** erfassen.

### 4.3 Testmatrix

| Test | Scan-Kopf | Body | Erwartung |
|------|-----------|------|-----------|
| A | eingefroren | A | Oracle A |
| B | eingefroren | B | Oracle B |
| **C** | eingefroren | **A→B** | Cold-Burst liefert **B** |
| Kontrolle | eingefroren | A | kein künstlicher Remount |

### 4.4 Erfolgskriterien (getrennt)

| Stufe | Beweist |
|-------|---------|
| P1 | Reproduzierbares Cold-Body-Muster / Timing |
| Q3a | Frische auf bisherigem Startpfad |
| **Q3b** | Aktuelle Daten beim Cold-Burst über MSC ausgeliefert |
| AV | HU dekodiert Testsignal **hörbar** |
| Detect | Software erkennt Cold-Burst korrekt |

### 4.5 Datenformat

Deterministische Bytefolgen, Blocknummern, Prüfsummen, Audio-Signatur, dokumentierter LBA-/Offset-Bezug ab LBA **761**.

---

## 5. Detect — Schritt 2 (nur Diagnose)

- `evaluatePlay` nachvollziehen (Warm-Head vs Cold-Body / `not_from_head`).
- Neues Event **`cold_body_burst`** — **nur Logging**: Slot/UID, LBA-Span, Read-Anzahl/-Volumen, Zeit, Warmheitsannahme, Detect-Entscheidung, Ablehnungsgrund.
- Gegenüberstellung PD0056/57-Cold vs PD0058-Warm.
- **Keine** Umschaltung von `play_uid`, Buffer, Pacing, PSRAM.

---

## 6. Feld nach Lab-Q3b (Schritt 3)

1. Scan-Kopf + Body vorbereiten, P0-Lock, Mount ohne Remount.  
2. Kurzdatei → Auto-Next → Cold-Burst.  
3. Parallel: UI-Timer + LED + Ton filmen.  
4. Trace + ESP-Status sichern.  
5. Getrennt bewerten: P1 · Q3b · AV · Detect. Kein PASS durch LED oder `audio_ack`.

---

## 7. Architekturregeln (unverändert)

Eingefroren bis Q3b-/AV-Abnahme: Ringgröße, PSRAM-Streaming, Pacing, Remount-Karussell, USB-Geometrie, Live-Overlay-Optimierung, größere Detect-Policy.  
P0 unangetastet · `bufferMs` kein KPI · BT-Hybrid nur Fallback · Sequenz-GO gesperrt.  
`bufferMs`-Schreibpfad: nachrangiger Bug, vor künftigen Lab-Metrik-Läufen sinnvoll — **kein** Q3b-Blocker.

---

## 8. Arbeitsreihenfolge

| Prio | Aufgabe | Done wenn |
|------|---------|-----------|
| 0 | O1 / Prefill-Grenzen | **erledigt** (dieses Dokument) |
| 1 | Q3b Oracles A/B/C implementieren | drei unabhängige Nachweise |
| 2 | Lab-Testmatrix A/B/C + Kontrolle | reproduzierbare Datenfrische |
| 3 | Detect-Bedingungen + `cold_body_burst` | nur Log, Cold/Warm dokumentiert |
| 4 | Feld Ohr/Film | AV-Nachweis getrennt |
| 5 | Review | erst dann Sequenz-GO diskutieren |

---

## 9. Fehler, die vermieden werden müssen

1. `bufferMs=0` als Buffer-Fehler deuten.  
2. P1 wieder „unmessbar“ nennen.  
3. USB-Reads ⇒ hörbarer Ton.  
4. Aus `streamBytes==underruns` die genaue Producer-Stelle „ableiten“.  
5. LED als AV-Beweis.  
6. Detect vor Diagnose umschalten.  
7. Ring/PSRAM parallel zu Q3b ändern.  
8. Q3b mit P1/AV verschmelzen.  
9. Slot-Oracle mit MSC-Delivery-Oracle verwechseln.  
10. Erfolg nach unkontrolliertem Remount als Prefill-Beweis.  
11. **`lba1` als Transfer-Ende** verwenden.  
12. Prefill erst ab LBA **1953** legen (verfehlt den frühen Burst-Teil 761…1952).

---

## 10. Meta: Mistral / GPT / Claude

| Quelle | Was bleibt |
|--------|------------|
| Claude | P1-Bursts + Detect-Kritik richtig; **753** = Span-Min, nicht allein Prefill-Start |
| GPT | `bufferMs`≠Ursache / tot; Drei-Oracle-Trennung; Anchor-Schwäche; Counter-Disclaimer |
| Mistral | „P1 unmessbar“ / bufferMs-Priorisierung falsch; Lösungspfad Q3b inzwischen korrekt |

---

## 11. Fazit für die nächste KI

Die HU liest beim Auto-Next **reproduzierbar kalte Body-LBAs** (P1 PASS_WEAK).  
Die Architekturfrage ist: **Liegen hinter dem eingefrorenen Kopf (LBA ≤760) aktuelle Bytes, die beim Burst ab LBA 761 über MSC wirklich ausgeliefert werden?**

**Nächste Aufgabe:** Q3b Lab mit Oracles A/B/C und Prefill ab **LBA 761** — nicht „Audio blind reparieren“, nicht Ring/PSRAM anfassen, nicht Detect schalten.

Lesereihenfolge: `MSC-AKTUELL.md` → **dieses Dokument** → `GESAMTBERICHT-KRITIK-…` → Rohtraces → Lab `lab88-av-stream-1400/` → Plan Rev.5.
