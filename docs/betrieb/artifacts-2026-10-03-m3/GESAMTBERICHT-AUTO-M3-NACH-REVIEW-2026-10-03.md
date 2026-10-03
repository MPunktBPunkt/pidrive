# Gesamtbericht: Auto-M3 nach Addendum und Review-Schleife

**Stand:** 2026-10-03 Abend  
**Repos:** `pidrive` (Ziel: dieser Push) · `esp32.pidrive` `eaa65f7`  
**Artefakte:** `artifacts-2026-10-03-m3/auto89-m3-static-170625/`  
**Vorarbeiten:** `4a1c844` / `4b518da` · Semantik · Coverage-Tool · Plan Rev.2  

**Evidenzklassen:** **D** Daten · **C** Code · **I** Interpretation · **H** Hypothese

---

## 0. Kurzurteil

Die Nacharbeiten (`playingUid`-Timing, Zählersemantik, Coverage-Tool) schließen die offenen Interpretationsschulden des M3-Passes weitgehend.

**Belastbarer Kern (D):**

> **A_then_E im beobachteten Fenster:** Nach dem initialen Lesevorgang keine weiteren registrierten MSC-Reads (~8 min), während die HU einen Fortschrittsindikator zeigte. Cache-Erschöpfung wurde nicht beobachtet.

**Nicht bewiesen:** vollständiger eindeutiger 8‑MiB-Scan; hörbare Wiedergabe; Trackende-/Select-Trigger; Frische; allgemeines Cache-Limit.

**Review-Bilanz:** Mistral hat den Identitäts- und Semantik-Stand richtig aufgenommen, setzt aber Export-Coverage (~4 MiB) unzulässig mit Cache-Inhalt gleich. Claude korrigiert das zu Recht und liefert eine **starke, aber nicht direkte** Vollscan-Rekonstruktion; „spielt“ und „sicher komplette 8 MiB“ sind zu hart.

**Nächster Schritt:** M3seq Rev.2 (Q1–Q3), vorher Lab-Kalibrierung **A (Pre-Connect)** und **B (Burst/50 ms)** getrennt. Ring/PSRAM/Pacing/BT/Live eingefroren.

---

## 1. Was die Umsetzung geleistet hat

| Maßnahme | Nutzen |
|----------|--------|
| `playingUid` / Statuskette 09–14 | Identitäts-Asterisk am Hauptfenster entfernt (**D**) |
| Semantik `bytes` / `maxSeq` / `bytesFile` | verhindert Zähler-Verwechslung (**C**) |
| `m3_trace_coverage.py` | Unique-Coverage aus Export (**D**, Untergrenze) |
| Plan Rev.2 Q1–Q3 / Arme / S0–SR | richtige Operationalisierung |

---

## 2. Rohdaten-Abgleich (Cursor, diese Runde)

### 2.1 Play-Fenster-Identität (**D**)

| Status | Zeit | `playingUid` | `rc` |
|--------|------|--------------|------|
| 09–14 | 17:15–17:22 | **leer**, `playGuessCount=0` | 2087 |
| 10 / 15 | 17:23:39+ | fav1 | 2343 |

→ fav1 gehört zum Reselect, nicht zum Play-Fenster. Leeres `playingUid` = kein play.guess (**C**), kein positiver Decoder-Nachweis.

### 2.2 Zähler vs. Export (**D**)

Aus `status-14` (Ende Play-Fenster, vor Reselect):

| Größe | Wert |
|-------|------|
| `readCount` | 2087 |
| `readsEmit` | 532 |
| `readOverflow` | **0** |
| `bytesFile` | 8 421 376 |
| fav0 `slot.bytes` | 8 421 376 = **2056 × 4096** |
| fav0 Dateigröße | 8 388 608 = **2048 × 4096** |
| fav0 `maxSeq` | 6 389 760 |
| fav0 `midFile`+Head-Hits | 2054+2 = 2056 |
| fav1/fav2 `bytes` | **0** (dieser Snapshot) |

JSONL pre-Reselect (`kind=2`, ms 6409…11658):

| Größe | Wert |
|-------|------|
| Bursts | 362 |
| `Σ bytes` / unique | **4 132 864** (~3,94–4,13 MiB) |
| Unique-Intervalle | 2 (kl. Insel + Block ~4,13→~8,00 MiB) |
| Gap | ~2,40 MiB mitten drin |
| Prefix unter Export-Min | ~1,85 MiB |
| `Σ burst.n` | 1009 |
| Doppelte Start-LBAs | 0 |

**Wichtig:** `ov=0`, aber Export ≪ Status (`Σn` JSONL gesamt 1265 vs `rc` 2087). Verluste vor Queue **zählen nicht als Overflow** — Pre-Bridge-Gap ist damit **vereinbar** (**H**, zu kalibrieren).

### 2.3 Vollscan-Hypothese — Einstufung

**Claude (H, stark gestützt):**

- Kumulativ fav0 ≈ Dateigröße (+ genau **8** × 4 KiB = 32 KiB Überhang, nicht „≤20 Wiederholungen“ ohne Herleitung).  
- Export zeigt vor allem die **zweite** Dateihälfte; fehlende ~4 MiB passen grob zu Prefix+Gap.  
- Keine wiederholten Start-LBAs in der exportierten Hälfte.

**Daraus folgt nicht zwingend (Grenze):**

- Eindeutige Sektorabdeckung der fehlenden Hälfte (nur indirekt).  
- Hörbare Wiedergabe.  
- „Kompletter Scan in ~10 s“ als gemessene Vollabdeckungs-Zeit.

**Mistral-Fehler:** Export-Unique ≈ Cache-Inhalt ≈ 11–12 min — widerspricht der eigenen Untergrenzen-Logik.

**Cursor-Formulierung:**

> Vollständiger eindeutiger 8‑MiB-Read: **wahrscheinlich (H)**, gestützt durch `slot.bytes≈Dateigröße` und komplementäre Exportlücke; **nicht D**.  
> Nachweisbare Export-Unique: **~4,1 MiB (D, Untergrenze)**.  
> Cache-Horizont daher **nicht** auf 11–12 min festnageln; bei Vollscan-Hypothese rechnerisch eher **~23 min @ 48 kbit/s**.

---

## 3. Bewertung Mistral (explizit)

| Punkt | Urteil |
|-------|--------|
| Identitätsauflösung | **richtig** |
| Semantik / Tool / M3seq vor Langpass / Freeze | **richtig** |
| 50‑ms-Burst-Kalibrierung | **richtig, aber unvollständig** (nur Fall B) |
| Cache ≈ 4 MiB / 3–4 min bis Erschöpfung | **unzulässig** |
| „Messphase reif“ | **bedingt** — erst nach Kalibrierung A+B |

Mistrals Beitrag bleibt konstruktiv; die Cache-Horizont-Zahl darf nicht in den Plan wandern.

---

## 4. Bewertung Claude (explizit)

| Punkt | Urteil |
|-------|--------|
| Kritik an 4‑MiB-Cache | **richtig** |
| Rekonstruktion Vollscan | **plausibel / wahrscheinlich (H)** |
| „Restunsicherheit ≤20“ | **zu ungenau**; aus 2056−2048 folgen **8** 4‑KiB-Äquivalente Überhang |
| Pre-Connect-Lücke | **plausible H**; Ursache Lab-testen |
| „spielt ≥8 min“ | **zu stark** → UI-Fortschritt ohne weitere Reads |
| Langpass ≥25 min | **sinnvoll unter Vollscan-H**, nach M3seq |
| fav1-87 s-Vorversuch | **sinnvoller Billig-Indikator**, ersetzt Q2 nicht |

---

## 5. Evidenzebenen (verbindlich)

| Ebene | M3-Stand |
|-------|----------|
| 1 Host-Read | Sweep/Prefetch ja; Play-Fenster keine neuen Reads (**D**) |
| 2 Read-Ahead | initial großzügig; laufendes Ahead im Play-Fenster nein |
| 3 Play-Read/Cursor | **nicht** belegt (`playingUid` leer, stumme Datei) |
| 4 Live | nein / nicht Gegenstand |

UI-Balken ≠ hörbare Wiedergabe ≠ Decoderposition.

---

## 6. Lösungspfad (geschärft)

### P0 Lab-Kalibrierung (vor Feld) — **zwei getrennte Fälle**

**Kalibrierung A — Pre-Connect**

1. Bridge/TCP **vor** Plug verifizieren.  
2. Separat: Read-Beginn **während** Connect provozieren.  
3. Bilanz: Soll-Reads/LBA vs Status vs JSONL; Anteil vor Export-Ready.

**Kalibrierung B — Burst**

1. Bekannte LBA-Bursts, Abstände um `kBurstGapMs=50`.  
2. Prüfen Aggregation/Queue/Export (Anzahl **und** Intervalle).

Negatives Q2 ohne A+B = **ungültig** als „HU liest nicht“.

### P1 Feld M3seq Rev.2

- Q1 Select · Q2 Trackende · Q3 Frische — **getrennte** Arme/Artefakte.  
- Hörbare Kurzdateien, Decoder-Check.  
- Bridge vor Messfenster up; M0 + Coverage-Qualität ausweisen.  
- S0–SR **pro Arm**.

### P1b Optional Billig-Indikator

fav1 512 KiB (~87 s @48 k) passiv Trackende — nur mit verbundener Bridge; kein Ersatz für Arm2.

### P2 Nach M3seq

- Langpass: unter Vollscan-H eher **≥25 min** + Sicherheitsmarge; oder kürzere Datei mit konstruktivem Ende.  
- L4 Cache-Limit: eigene Frage, nach FAT-Validierung, nicht parallel zu M3seq vermischen.

### Entscheidung (konditional)

| Ergebnis | Folge |
|----------|--------|
| S4 | Chunk-Modell vertiefen (Latenz/UX) |
| nur SR | Remount skizzieren |
| S0 und kein S3 | MSC-Live/Chunk ohne Stimulus schwach |
| alles negativ + kalibrierte Trace | BT-Hybrid als **Produktentscheidung** diskutieren |
| unsichere Trace | wiederholen |

**Eingefroren bis dahin:** Ring, PSRAM, Pacing, Remount-Implementierung, BT-Hybrid-Code, Live-als-M3, L4 parallel.

---

## 7. Zahlen-Spickzettel (nicht vermischen)

| Größe | Wert | Klasse |
|-------|------|--------|
| Play-Fenster Δrc | 0 | D |
| Export unique fav0 | ~4,1 MiB | D Untergrenze |
| fav0 `slot.bytes` | 8 421 376 (2056×4 KiB) | D kumulativ |
| fav0 Datei | 8 388 608 (2048×4 KiB) | D |
| Überhang kumulativ | 8×4 KiB | D |
| `maxSeq` | 6 389 760 | D Sequenz, kein Unique |
| Vollscan 8 MiB unique | — | **H** wahrscheinlich |
| Cache-Horizont 11–12 min | — | **ungültig** als Tatsache |
| Horizont bei Vollscan-H | ~23 min @48 k | I/H Näherung |

---

## 8. Schluss

Die Review-Schleife ist methodisch geschlossen: Befund → Identitätsklärung → Semantik → Coverage-Untergrenze → Tool → Plan.  

Mistral und Claude ziehen die Grenze an unterschiedlichen Stellen zu hart (4 MiB-Cache bzw. gesicherter Vollscan/„spielt“). Die Synthese bleibt:

**A_then_E im Fenster; Vollscan plausibel aber indirekt; nächster Schritt kalibriertes M3seq; kein Ring.**
