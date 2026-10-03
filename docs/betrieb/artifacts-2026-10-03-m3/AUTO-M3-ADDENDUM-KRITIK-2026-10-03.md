# Addendum Auto-M3 — kritische Korrektur (2026-10-03 Abend)

**Basis:** Reviews Mistral/Claude/GPT + Rohdaten/Code-Prüfung Cursor.  
**Commits Ausgang:** `pidrive` `f52e734` · `esp32` `eaa65f7`

---

## 1. Was bleibt belastbar (D)

Im Play-Fenster **17:15:34–17:22:53** (Polls) bzw. Status **17:22:34** (`status-14`):

- `ΔreadCount = 0`, `ΔreadsEmit = 0`, `readOverflow = 0`, phase **quiet**, TCP up, stream off  
- `lastLba` unverändert (3841)  
- Operator: Fortschrittsbalken läuft (~25 % @17:21)

**Korrekte Aussage:**

> A_then_E **innerhalb des beobachteten Fensters**; Cache-Erschöpfung **nicht** erreicht; HU zeigte Fortschrittsindikator ohne neue MSC-Reads.

---

## 2. fav0/fav1 — gelöst (D+C)

| Snapshot | mtime | msSincePlug | rc | playingUid |
|----------|-------|-------------|-----|------------|
| `status-09`…`status-14` | 17:15–17:22 | ≤521 s | 2087 | **leer** |
| `status-10-play-end-window` | **17:23:39** | 586 s | 2343 | **fav1** |
| `status-15-reselect` | 17:23:40 | 587 s | 2343 | fav1 |

`playingUid` kommt nur aus **play.guess** (`MenuStore`), nicht aus der HU-UI. Im gesamten Play-Fenster: `playGuessCount=0`, `playingUid=""`.  
`status-10` ist **nach** dem Reselect (17:23), kein Widerspruch innerhalb des Play-Fensters.

Operator „Rock Antenne“ bleibt die beste UI-Angabe; ESP hat play.guess dafür **nicht** bestätigt. Identität für Architektur: „HU zeigte Wiedergabe-UI ohne MSC-Nachlesen“ — nicht „nachgewiesen fav0-Decoder“.

---

## 3. Cache-Abdeckung — korrigiert (D+C)

Semantik: [`MSC-STATUS-SEMANTIK-0.4.42.md`](../MSC-STATUS-SEMANTIK-0.4.42.md)

| Quelle | fav0-relevant | Bedeutung |
|--------|---------------|-----------|
| `slotMap.bytes` @status-14 | **8 421 376** | kumulativ inkl. Wiederholungen (**> 8 MiB Datei**) |
| `maxSeq` | **6 389 760** | längste zusammenhängende Sequenz — **kein** Unique-Vollscan |
| JSONL Coverage (`m3_trace_coverage.py`) pre-Reselect | unique **≈4.13 MiB** (49 %), max_off≈EOF, **1 Gap ≈2.40 MiB**, Prefix in Export oft fehlend | nur Export; `bytesFile` 8.42 MiB ≫ JSONL-Summe → **Export unvollständig** |

**Nicht zulässig:** „kompletter 8‑MiB-Read“ (Claude) · „verifizierte 4‑MiB-Cachegröße“ (Mistral/Feldbericht grob).

**Zulässig:** Sweep las **erheblich** in fav0 (Status-Bytes); längste Sequenz **6.39 MiB**; eindeutige Abdeckung aus JSONL nur Untergrenze; **kein** Nachweis lückenloser 8 MiB.

Horizonte @6 KiB/s nur als Näherung: unique≈11.5 min · maxSeq≈17.7 min · Datei≈23 min — Fenster 8 min endete **vor** jeder dieser Erschöpfungsnäherungen.

Artefakt: `auto89-m3-static-170625/coverage-analysis.json`

---

## 4. Korrekturbilanz Reviews

| Review | Richtig | Zu weit |
|--------|---------|---------|
| **Mistral** | Null-Read-Fenster; vor Erschöpfung; M3seq; eingefroren | 4 MiB als harte Cachegröße; kurze Dateien erzwingen Erschöpfung |
| **Claude** | vor Erschöpfung; Felder nicht gleichsetzen; Chunk = Hypothese | Vollscan 8 MiB; „atomare Datei“ allgemein; D endgültig tot; Quasi-Live |
| **GPT-Konsolidierung** | Trennung D/I/H; Q1–Q3; S0–SR; drei Arme | — Übernahme mit Addendum timing/maxSeq |

---

## 5. Architektur — Lösungssuche (eng)

| Pfad | Status nach Korrektur |
|------|------------------------|
| A fortlaufendes Lesen derselben Datei | im Fenster **nicht gestützt**; Langpass erst sinnvoll **mit** Unique-Coverage + Ziel jenseits maxSeq/Gap |
| B Chunk/Playlist kurze Dateien | **prüfbar**, nur wenn Q1/Q2 Reads + Q3 Frische |
| C Remount | Option nach S0; nicht implementieren vor Nachweis |
| D BT-Audio + MSC-Menü | Produktentscheidung, nicht M3-Folge |
| E L4 größer | Diagnose separat **nach** M3seq |

**Kein** Ring/PSRAM/Pacing bis ein Pfad Host-Reads **nach** Sweep belegt.

---

## 6. Nächste Maßnahmen (verbindlich)

### Sofort (Doku/Tool) — dieser Push
1. Semantik-Doc + Coverage-Tool  
2. Feldbericht-Addendum (dieses File)  
3. Plan Q1–Q3 / S0–SR / Drei-Arme schärfen  

### Lab vor nächstem Feld
1. Kurze, **hörbare** Testdateien (nicht nur PDMK) + Decoder-Check  
2. Coverage-Tool gegen Lab-Host-Volltrace kalibrieren (Export=Status)  
3. Optional: Telemetrie „unique high-water“ in FW — **nur wenn** nötig, kein Architekturumbau  

### Feld M3seq (eigene Sessions)
- **Arm1** Select ohne Remount → S0/S1/S2  
- **Arm2** natürliches Trackende → S3?  
- **Arm3** Remount separat → SR?  
- **Q3 Frische** erst nach positivem S2/S3  

### Optional Langpass (Pfad A)
Nur mit stabilem WLAN, Bridge von Plug an, ov=0, Coverage live: Ziel **Play ≥ ~20 min** bzw. Cursor-Hypothese jenseits **maxSeq/Gap** — Ergebnis egal ob Read, Stille oder Absprung = harter Befund.

---

## 7. Ein-Satz-Urteil

Null-Read bei laufendem Balken ist echt; Vollcache-8‑MiB und feste 4‑MiB-Grenze sind es nicht — als Nächstes **Select/Track/Frische** messen, nicht den Ring bauen.
