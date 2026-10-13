# Experimentkatalog — nach GPT-Nachtüberlegungen (2026-10-07)

**Bezug:** `f397456` · Stufenplan · HU-Facts Q1–Q6 · MASSNAHMEN  
**Regel:** F1 (morgen) hat Vorrang. Q4a–c und Marker-Diagnose **nicht** mit Stall vermischen. Kein 0.4.47 ohne Go.

---

## 0. Was GPT bestätigt (bereits im Repo)

| Aussage | Status |
|---------|--------|
| Burst = Dateirest, nicht Ringmaß | ✅ ANALYSE + G1 `438272` |
| Hebel = MSC-Backpressure, nicht Prefill/PSRAM | ✅ MASSNAHMEN / Freeze |
| Lab G1–G5 / G6 / Profil 4 KiB·4 ms | ✅ `all-c2*` + Kalibrierblatt |
| F1 entscheidet Stall-Pfad | ✅ ARRIVAL |
| Bekannte Dateidaten lösen Streaming **nicht** — Silence hinter dem Cursor = falsche Zukunft | ✅ unten §2 präzisiert |

---

## 1. „Cursor“ — kurze Definition

**Cursor** = logische Dateiposition, die die HU als nächstes per READ10 erwartet (ESP: `hostAbsCursor` / File-Offset), **nicht** ein sichtbarer UI-Balken.

Wenn ESP bei Miss **gültige Silence** liefert, ist der READ für die HU erledigt → sie fragt dieselbe Position **nicht erneut**. Später erzeugte Live-Bytes an dieser Position kommen nie an = „Daten hinter dem Cursor“.

Bekannte Vorabfüllung hilft nur zur **Diagnose** (welche Offsets gelesen wurden), nicht als Streaming-Lösung ohne Backpressure.

---

## 2. Experimente klar trennen

```text
                    ┌─────────────────────┐
                    │  F1 Decode-Start    │  ← morgen, 0.4.46, Video
                    └──────────┬──────────┘
                               │
              inkrementell     │     after_eof
                     │         │         │
                     ▼         │         ▼
              Stall-Pfad       │    Fallback Dateikette
                     │         │
                     ▼         │
         ┌───────────┴─────────┴──────────┐
         │  nicht vermischen:             │
         │  A Cache-Kapazität (viele Files│
         │  B Live-Stall (eine File)      │
         │  C Read-Ahead einer Datei      │
         └────────────────────────────────┘
```

| Exp | Frage | Setup | Stall? |
|-----|-------|-------|--------|
| **F1** | Timer vs EOF | Silence fav0 8 MiB, Bridge stop, Video | nein |
| **F2** | Cache Abwahl/Remount | fav1→fav2→fav1, OTG | nein |
| **Q4a** | Max. Eager-Read **einer** Datei | Größenleiter 512 KiB…64 MiB, eine Datei, kein Live | nein |
| **Q4b** | Max. Bytes/Anzahl **mehrerer** gecachter Dateien | N=1…64 × 512 KiB, Hit/Miss per Re-Select | nein |
| **Q4c** | Eviction (FIFO/LRU/?) | Reihenfolge A…H dann A; Rückwärtslauf | nein |
| **Marker** | Offset-genaue Read-Map | Pattern-Blöcke A/B/C… pro 50–100 KiB; LBA-Log | nein (Diagnose) |
| **Live-Grenze** | Prefill bis Offset X, danach Backpressure | fertig 0…X, LIVE >X, READ wartet | **ja → Stufe 3+** |

Drei Dateien (fav0–2) reichen **nicht**, um Cache-Größe zu schätzen — das ist der brauchbare GPT-Punkt für Q4b.

---

## 3. Q4a — Eager-Read einer Datei (Feld, nach F1/F2)

Dateigrößen nacheinander (Bridge aus / Silence):

`512 KiB → 1 → 2 → 4 → 8 → 16 → 32 → 64 MiB`

Pro Größe: `maxSeq`/`bytes`, ob Wiedergabe startet, ob Next-Prefetch, Abwahl-Verhalten.  
Ergebnis: **maximale Read-Ahead-Menge einer Datei** ≠ Gesamt-Cache.

---

## 4. Q4b/c — Multi-File-Cache-Matrix (Feld oder Lab-Geometrie später)

Beispiel: `N ∈ {1,2,4,8,16,32,64}` Dateien × 512 KiB, eindeutiger Inhalt/Name.

1. Sequenz F00…F(N−1) je bis EOF (oder bis Quiet).  
2. F00 erneut → USB-Reads? Hit/Miss.  
3. Optional LRU-Probe: F00…F07 dann F00; oder H…A rückwärts.

**Abnahme:** Tabelle Hit/Miss → untere Schranke für Cache-Kapazität / Eviction-Heuristik.  
**Nicht** mit Live-Arm/Stall koppeln.

---

## 5. Marker-Diagnose (Lab jetzt möglich, Feld nice-to-have)

Inhaltliche Abschnitte mit erkennbaren Mustern (PDSQ / feste Frames):

| Offset | Inhalt |
|--------|--------|
| 0–3 KiB | ID3 |
| 3–50 KiB | Marker A |
| 50–100 | B |
| … | … |
| ab X | LIVE oder Silence (je Modus) |

Log pro READ10: LBA, len, erkanntes Muster.  
Beweis: „HU hat bis Offset Z gelesen, Producer erst bei Y“ ohne nur `hostAbs` zu vertrauen.

---

## 6. Live-Grenze @ Offset X (nur nach Stall-Go)

Nicht Silence hinter X — sonst wieder Cursor-Versatz.

```text
HU READ < X  → sofort (fertig Audio)
HU READ ≥ X  → WAIT bis Producer ≥ angefordert
```

X-Leiter: 100 KiB / 300 KiB / 1 MiB — misst, wie weit die HU über die Live-Grenze hinaus will **unter Backpressure**.  
Das ist Experiment B (Stall), nicht Q4b.

---

## 7. Priorität für morgen früh

1. **F1** (ARRIVAL) — Gabelung Stall vs. Fallback  
2. **F2** a+c mindestens  
3. Q4a/b/c nur wenn Zeit übrig oder eigener Termin  
4. Stall-FW erst nach F1=inkrementell + explizitem Go
