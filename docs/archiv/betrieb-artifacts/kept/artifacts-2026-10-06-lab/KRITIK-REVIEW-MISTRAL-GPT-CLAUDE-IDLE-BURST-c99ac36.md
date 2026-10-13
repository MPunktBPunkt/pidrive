# Kritik / Konsolidierung: Mistral + GPT + Claude · Idle/Burst `c99ac36`

**Datum:** 2026-10-06 · **HEAD:** `c99ac36` (Kern `3c37212` → `033e477`) · **FW:** 0.4.45-dev  
**Quellen:** Rohdaten lokal nachgerechnet · `PumpServer.cpp` gelesen · Feld 15:40 Status geprüft  
**Hinweis:** Der lange GPT-Text (Abschnitte 1–20) ist inhaltlich mit dem zweiten Mistral-Block identisch → **keine unabhängige dritte Quelle**.

---

## 1. Kurzfazit (Cursor)

Lab-Mechanik steht. Drei Schärfungen gegenüber Mistral/GPT:

1. **Ceiling-Ursache:** Nicht „~140 Frames/s × 512 B“, sondern sehr wahrscheinlich **Byte-für-Byte-`client_.read()`** in `drainTcp` (Byte-Rate konstant bei 256–1024‑B-Frames; Code bestätigt).
2. **Prefill-PASS** beweist Mechanik bei Burst ≤ Ring — **konstruktionsbedingt**, kein HU-Beweis.
3. **`behind>0` nicht lockern:** `behind_base = max(0, absBase−hostAbs)` = Cursor vor Fensterstart → nächster Read = Miss/Silence. PASS bleibt `und=0 ∧ behind=0 ∧ live>0`.

**Schicksalsfrage** bleibt Feld, aber präziser: Live-Pfad-Burst bei **gültigem MP3** (nicht Stub), plus Slot-Geometrie (Datei-/Kopfgröße).

---

## 2. Konsens (alle drei + Rohdaten)

| Befund | Stand |
|--------|--------|
| Idle-Ceiling ~70–74 KB/s; Gap/Batch/Chunk irrelevant | 🟢 |
| Frames >512 B abgelehnt (`binBuf_[512]`) | 🟢 |
| Nachschieben deckt 250–500 KB/s Host nicht | 🟢 |
| Hold = Pauseschutz, nicht Burst-Lösung | 🟢 |
| Prefill ≥ Burst → async PASS (Pump≈aus) | 🟢 Mechanik |
| `burst48-hold`: und=0, behind=7168, **pass=false** | 🟢 |
| Burst-then-Slow: und=0 beide Phasen, behind≠0, **kein formaler PASS** | 🟢 |
| Feld-Ton nie · Sequenz-GO gesperrt · Freeze hält | 🟢 |

---

## 3. Abweichungen — Entscheidung

### 3.1 Ceiling-Ursache (Claude vs. Mistral/GPT)

| Claim | Urteil |
|-------|--------|
| „~140 Frames/s × 512 B Frame-Verarbeitung“ | ❌ Idle: Byte-Rate ~69 KB/s auch bei 256 B (~268 Frames/s) und 1024 B (abgelehnt, ~69 Frames/s pumped) |
| Byte-Lese-Schleife `drainTcp` | 🟢 Code: `while (available) { read(); feedByte(); }` · **H:** ~14 µs/Byte → ~70 KB/s |

**Maßnahme P0-Lab (Freeze-Hinweis):** Auf .88 nur `drainTcp` → Bulk-`read(buf,n)` testen, Idle-Matrix wiederholen. Steigt Rate ≫70 KB/s → Ursache bestätigt. Kein USB/Ring-Umbau.

### 3.2 Prefill-PASS Interpretation

Mistral/GPT korrekt: PASS ≠ „Pump hält 264 KB/s“. Claude korrekt: Burst war absichtlich ≤48 KiB. **Merksatz:** Prefill-PASS = Mechanik-Nachweis, nicht Feld-Prognose.

### 3.3 `behind` / PASS-Kriterium

| Claim | Urteil |
|-------|--------|
| Mistral: Feld-PASS mit `behind ≤ Ring` | ❌ Semantik: Miss vor `absBase` |
| Claude: `behind=0` beibehalten | 🟢 übernommen |
| Chat „burst48-hold Key-PASS“ | ❌ nur und=0; Template = prefill-only / prefill-eq |

Burst-then-Slow: hostAbs 50 688 → 414 720 bei nur 96 KiB Post-Reads → **Resync/Cursor-Sprung** (Claude). `und=0` allein ≠ Audio-Kontinuität. **Maßnahme:** Resync-Events in Lab/Correlate loggen.

### 3.4 „248 KiB Schicksalsgröße“

Feld 15:40: fav1 `bytes` 0→524 288 (+128 Reads = ganze 512‑KiB-Datei); Live-Pfad `hostAbs=und=streamBytes=253952` = 62×4 KiB bei **leerem Fenster**.  
→ 253952 ist **Live-Pfad-Underrun-Zähler**, gekoppelt an Slot/Datei, kein bewiesener „natürlicher Decoder-Burst“. Inhaltseffekt (gültiges MP3 vs. Silence) bleibt offen — aber weniger mysteriös als „Silence-Artefakt ja/nein“.

**Maßnahme P0-Feld:** Erstburst bei gültigem Inhalt + Slot-Bytes/readCount mitmessen.  
**Maßnahme P1-Lab/Bridge:** Geometrie-Hebel prüfen (Live-Anteil ≤48 KiB) — Scan-Risiko beachten.

### 3.5 GPT-Unabhängigkeit

Langer GPT-Block = Kopie des zweiten Mistral-Texts. Abgleich nur Mistral-Review₁ + Claude zählt als Zwei-Quellen-Diskurs.

---

## 4. Maßnahmen (priorisiert)

| Prio | Maßnahme | Ziel / Entscheidungsregel |
|------|----------|---------------------------|
| **P0** | **Feld kurz:** RST → Bridge frisch → Gate → 1 Sender 20–30 s → Correlate dicht | Messen: Erstburst-Länge Live-Pfad (`d(hostAbs)/dt` bis Ratenknick), `d(absEnd)/dt`, Slot-`bytes`/`readCount`, Ton ja/nein |
| **P0** | **PASS-Kriterium unverändert:** `live>0 ∧ und=0 ∧ behind=0` anhaltend | Kein „behind bounded“ |
| **P0** | **Lab-FW-Mikrotest (.88):** `drainTcp` Bulk-Read | Rate >200 KB/s? → Ceiling-Ursache klar; sonst WLAN prüfen. **Freeze:** nur Lab-ESP, kein Feld-Flash ohne Abstimmung |
| **P1** | Hold strenger (Poll/Chunk) bis behind→0 nach Prefill-Burst | Burst-then-Slow formal PASS |
| **P1** | Spekulatives Prefill ab Gate (vor Head) | 48 KiB ≈0,7 s bei Ceiling |
| **P1** | Resync/Cursor-Sprünge in Tools loggen | und=0-Interpretation |
| **P2** | Slot-Geometrie: Live ≤ Ring | Nur wenn Feld Burst≫48 KiB zeigt |
| **Nicht** | PSRAM / Read-Pacing / Detect / Lock / Sequenz-GO / Pump≥300 KB/s blind | Erst nach P0-Feld + ggf. Bulk-Test |

---

## 5. Ampel

| Thema | Stand |
|-------|--------|
| Idle-Ceiling ~70 KB/s | 🟢 |
| Ursache | 🟡 Byte-Read-Hypothese (Code stark, Messung fehlt) |
| Prefill≥Burst Mechanik | 🟢 |
| Burst-then-Slow | 🟡 und=0, behind≠0, Cursor-Sprung |
| Hold | 🟢 Pause · 🔴 kein Burst |
| Feld-Erstburst bei Live-MP3 | 🔴/🟠 offen (Slot-Geometrie teilweise erklärt) |
| Bridge-Design | 🟡 Prefill+Hold klar, Maß fehlt |
| Freeze / Sequenz-GO | 🟢 hält / gesperrt |

**Gesamt:** 🟡⁺ Lab ausgereizt für Mechanik. Nächster Hebel: **Feld-Burstmaß bei gültigem Audio**; parallel optional **Bulk-Read-Lab** zur Ceiling-Ursache.
