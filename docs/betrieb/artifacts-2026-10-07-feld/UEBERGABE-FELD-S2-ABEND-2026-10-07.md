# Technischer Übergabebericht — Feld s2 + F1-Abend · 2026-10-07

**Für:** nächste KI / Reviewer  
**Repo:** `MPunktBPunkt/pidrive` · **HEAD:** `f0f3343` (`main` == `origin/main`)  
**FW:** `0.4.46-dev` (Freeze, kein Stall-OTA) · **ESP Feld:** PD0089 / `.89` · **HU:** BMW F20 LCI, NBT Evo  
**Quellen:** Artefakte unter `docs/betrieb/artifacts-2026-10-07-feld/` und `…-lab/` · Mistral-Review (Abend) · GPT-Entwurf (Abend) · eigene Nachrechnung dieser Sitzung  
**Prüfer dieser Datei:** Cursor (Composer) · unabhängig von Mistral/GPT, Rohdaten lokal verifiziert

---

## 0. Kurzfazit (1 Absatz)

Der Abendtest ändert das HU-Modell: Die HU speichert eine Wiedergabeposition **P** und setzt nach Stick↔ESP-Medienwechsel dort fort — P liegt in der HU, nicht im Medium. Gleichzeitig ist F1 praktisch **inkrementell** (Marker ab 0 sofort hörbar, beide Dateien). Das erklärt, warum Feld-s2 bei UI-seitig „frischer“ Auswahl oft **nicht** bei Offset 0 liest (Q8: 5× `r16_resume_like`, dazu 4 Episoden mit klassischem Fragment-Präfix `F16 B120 B120 F360…`). Stall-Go bleibt **blockiert**: P-Identität offen, F1-Timing-Video offen, T3-Mapping bei OOO+Live nicht konstant. Ampel Stall: 🔴 · Erkenntnis: 🟡/🟢.

---

## 1. Was der neue Fund für den Stand bedeutet

| Vorher (implizit) | Nachher (Arbeitshypothese [S]) |
|-------------------|--------------------------------|
| R17: frische Auswahl → immer ab Kopf (360 KiB) | R17 gilt **nur ohne gespeicherte P** |
| R16/Q8-Resume bei „neuer“ Auswahl = Rätsel | Plausibel: UI-Tap ≠ positionsloser Start |
| Stall-Annahme Trackstart = Offset 0 | **Falsch.** Live-Pfad muss P=0 und P≠0 können |
| F1 formal offen (nur Balken) | F1 stark inkrementell [S]; Formalgo braucht Video-t |

**Konsequenz für die Reihenfolge:** nicht Stall bauen, sondern  
`P-Identität klären → P reproduzieren → OOO-Live-Mapping (T3) bestehen → erst dann Stall-Go`.

---

## 2. Verifikation (Rohdaten)

### 2.1 Inventar HEAD `f0f3343`

| Commit | Kern |
|--------|------|
| `341b7b3` | Lab-Auftrag T1–T4, Q8-Tool/Trace, F1-Builder, Protokoll 30 min |
| `5e6ed11` | Prep-Pocket + T1–T4-ERGEBNIS |
| `f06a337` | Feldlauf `s2-20261007-172123` (Q8 ohne F1) |
| `50b8281` | F1-Abend: `F1-ERGEBNIS.md`, `f1-car-notes.jsonl`, `f1-OPERATOR.txt` |
| `62fa2df` | Lab/Feld-Artefakte für Berichte, F1-INDEX/STICK.md |
| `f0f3343` | F1-MP3s + Logs + SYNC-TO-PI.tgz (GitHub-Warnung >50 MB) |

Zeilenzahlen s2-Lauf (gezählt): `msc_reads` 10079 · `trace` 23426 · `marks` 24 · `status-poll` 859 · Q8 `n_episodes` 14 · `lba0` 81 · `slot_bytes` 8388608.

### 2.2 F1-Abend (Stick, ~20:07–20:09)

Belege: [`F1-ERGEBNIS.md`](feld-s2-prep/s2-20261007-172123/F1-ERGEBNIS.md), [`f1-car-notes.jsonl`](feld-s2-prep/f1-car-notes.jsonl), [`F1-INDEX.json`](feld-s2-prep/f1-stick/F1-INDEX.json).

- 5 MB: 5 280 981 B / 330 s / 33 Marker; 100 MB: 104 801 244 B / 6550 s / 655 Marker; 128k, Marker alle 10 s, espeak-ng.
- Erster Zugriff: Zählen `0 → 10 → 20…` (Start vorn) — **beide** Dateien.
- Ausstecken ~10 → ESP/Rock → Stick rein → Weiterzählen ab ~**20**.
- Hub: HU erkennt Stick **und** ESP über den verwendeten Hub **nicht** (Protokoll plante USB-1.1; Notiz: USB-2-Hub nutzlos).

**Deutung streng:** Resume P≠0 über Medienwechsel ist **[S]** (Operator + Video vorhanden, Zahlen ≈). Ob der Sprung 10→20 exakt ein Positions-Jump ist oder Nachhörzeit nach Re-Plug, klärt nur das Video — „kein Sprung / Wanduhr-Passung“ ist **nicht** belegt.

**Formulierungskorrektur:** In `F1-ERGEBNIS` steht „Position am Stick/Datei gemerkt“ — präzise: **P persistiert in der HU**; der Stick speichert nichts.

### 2.3 Q8 Feld s2 (17:21–17:35, ohne F1)

Quelle: [`ERGEBNIS.md`](feld-s2-prep/s2-20261007-172123/ERGEBNIS.md), `q8/Q8-REPORT.json`, `q8/Q8-SEGMENTS.csv`, `q8-console.log`.

| Verdict | Anzahl | Episoden |
|---------|--------|----------|
| `r16_resume_like` | **5** | ep0, ep4, ep5, ep6, ep10 |
| `unclear` | 8 | ep1–3, ep7–9, ep12–13 |
| `no_slot_reads` | 1 | ep11 |

Klassischer Fragment-Präfix **`F16 B120 B120 F360…`** in **ep1, ep6, ep9, ep12** (nicht F8 wie Golden R16 in HU-Facts). Automatisches Verdict nur bei ep6 = `r16_resume_like`; ep1/9/12 = `unclear` trotz gleichem Präfix — Klassifikator und ERGEBNIS-Kurztext „ep1/6/9/12 = r16_resume_like“ sind **nicht deckungsgleich**.

Erste Slot-Segmente (alle vier): Start `file_off≈245760` (F16), dann Rückwärts-relative 120+120 KiB bis Offset 0, dann F360 — **near** (≤1 MiB), plus ein againkehrender Far-Touch bei `file_off≈8 384 512` (Dateiende-Nähe). Kein exakter Golden-LBA-1953-Lauf (P war hier anders).

`head_like=False` in allen 14 Episoden. Stall-Implikation unverändert: Startposition oft ≠ 0.

### 2.4 Lab T1–T4 / C1–C7

| Test | Befund |
|------|--------|
| C1 | PASS unter N1 (`sg_duration p50 ≤ 4,1 ms`) |
| C2 / T2 | +1 ms nur am **Live-Slot**; fremder Slot bleibt 4,0 ms |
| C4 sequentiell | PASS; **T3 OOO+Live:** 207 LIVE, `abs0−off` **53** unique → Mapping FAIL |
| C5 | teilweise (Wi-Fi unter MSC) |
| T1 | Poll verfälscht sg_p50 nicht; lost 33 % @4 Hz / 6,6 % @3 Hz |
| T4 | REPLAY PASS; `run-s2` bewusst nur im Feld |

---

## 3. Prüfung Mistral-Bericht

| Thema | Urteil |
|-------|--------|
| Gesamtrichtung, Stall-Freeze, P-in-HU, F1 inkrementell, Hub nutzlos, T1–T4, C1-N1 | **korrekt** |
| Artefakt-Zeilenzahlen, F1-INDEX, HEAD | **korrekt** |
| ep1/6/9/12 alle als Verdict `r16_resume_like` | **ungenau** — Muster ja, Verdict nur ep6 (+ andere Eps ohne dieses Präfix) |
| „exakt F8/B120/…/F968“ | **überzogen** — s2 zeigt **F16** B120 B120 F360…, nicht Golden-F8/…/F968 |
| „kein Sprung“ 10→20 | **nicht belegt** — Operatornäherung; Video nötig |
| Hub USB-1.1 vs USB-2 | **gemischt** — Protokoll 1.1 geplant, Abendnotiz USB-2; Fakt „Hub ignoriert“ bleibt |
| B1–B7 Maßnahmenkatalog | **sinnvoll**; B4 (100-MB-Binary) berechtigt |
| Ampel Stall 🔴 / Erkenntnis 🟡 | **übernommen** |

**GPT-Entwurf:** inhaltlich konsistent und vorsichtiger bei P-Identität; Fall A/B für Stall und Experimente P1–P3 sind die richtige nächste Arbeit. Nummerierung B1–B4 weicht von Mistral B1–B7 ab — unten vereinheitlicht.

---

## 4. Modell-Update (Arbeitsstand)

```text
ohne P  → R17-Kopfstart (360 KiB … EOF)     [B] s1-morgen 5/5
mit P   → R16-Fragmenttanz um P, dann EOF  [B] Read-Ebene; [S] Ursache = gespeicherte P
P       → überlebt Stick↔ESP               [S] F1-Abend
F1      → spielt während Lesen             [S] Marker; Formalgo = Video-t
Hub     → Full-Speed-Erzwingen entfällt    [B] diese HU/dieser Hub
```

Offen: **Woran hängt P?** (Dateiname, Pfad, Serial, Größe, Inhalt, Track-ID, …)

---

## 5. Maßnahmen (verbindlich, priorisiert)

| # | Maßnahme | Done wenn | Stall-Go? |
|---|----------|-----------|-----------|
| **M1** | HU-Facts nachtragen: R23 [S], R12/Q2 inkrementell [S], R17-Präzisierung, Q8 s2-Zeile, E/F Hub-Fakt | Diff in `HU-Technical-Facts.md` | vorbereitend |
| **M2** | F1-Video: t(Tap→„null“), Verlauf 0/10/20, 5MB vs 100MB (Batcher-Gegenprobe) | Zahlen in Q2/R12 + F1-Formalgo ja/nein | **Blocker** |
| **M3** | P-Quelle Feld/Lab: P1 gleicher Inhalt/anderer Name; P2 gleicher Name/anderer Inhalt; P3 Größenwechsel | Entscheidungstabelle Identität | **Blocker** |
| **M4** | Stall-Verhalten spezifizieren für Start P≠0 (nach M3) | Abschnitt in Stufenplan 3.x | Blocker |
| **M5** | Stufe 3.2 Abnahme = T3-Bedingung: gleiche OOO-Folge → `abs0−off` konstant | Text in `Stufenplan.md` §3.2 | Blocker FW |
| **M6** | Q8: Klassifikator vs. Muster dokumentieren; SEGMENTS near/far in Auswertung | kurzer Nachtrag an ERGEBNIS oder Q8-README | neat |
| **M7** | Repo-Hygiene: keine neuen >50-MB-Binaries; F1-MP3s als Beweismittel belassen oder LFS | Policy in Pflegehinweis | neat |
| **M8** | Trace-Lücken T1: Feld nur Muster; quantitative Lückenfreiheit später (Bridge-Trace / Ramp-only) | Known Issue | neat |
| **M9** | **Kein** Stall-Adapter-Code / OTA bis M2+M3+M5 | Freeze | hart |

Design-Rucksack (unverändert mitnehmen): 4-KiB-Stückelung · Busy-Retry · 512-B-Teilantworten · 5-ms-Budget **nur Live-Slot** (T2) · feste Offset-Zuordnung (nicht zählender Cursor).

---

## 6. Ampel

| Bereich | Ampel | Bemerkung |
|---------|-------|-----------|
| Feld-Disziplin / Artefakte | 🟢 | |
| Q8 Rohdaten | 🟢 | Auswertung: Muster klar, Verdict-Labels inkonsistent → 🟡 |
| F1 + Positionsgedächtnis | 🟡 | stark, Video-Timing + P-ID offen |
| Lab C1–C7 / T1–T4 | 🟢 | T1-Lücken + T3-FAIL bekannt |
| Stall-Go | 🔴 | M2+M3+M5 |
| Repo 100-MB-MP3 | 🟡 | Warnung, Push ok |

---

## 7. Einstieg für die nächste KI (Checkliste)

1. `git pull` → HEAD `f0f3343` prüfen.  
2. Lesen: diese Datei → `F1-ERGEBNIS.md` → `ERGEBNIS.md` (s2) → `T1-T4-ERGEBNIS.md` → `HU-Technical-Facts.md` → `Stufenplan.md` §3.2 / R10.  
3. M1 ausführen (Facts), sofern noch offen.  
4. M2 wenn Video verfügbar; sonst M3-Protokoll für nächsten Feldtermin schreiben.  
5. Stall-Code: **Freeze**.

---

## 8. Absolute Pfade (Kernartefakte)

```text
docs/betrieb/artifacts-2026-10-07-feld/feld-s2-prep/s2-20261007-172123/ERGEBNIS.md
docs/betrieb/artifacts-2026-10-07-feld/feld-s2-prep/s2-20261007-172123/F1-ERGEBNIS.md
docs/betrieb/artifacts-2026-10-07-feld/feld-s2-prep/s2-20261007-172123/q8/Q8-REPORT.json
docs/betrieb/artifacts-2026-10-07-feld/feld-s2-prep/s2-20261007-172123/q8/Q8-SEGMENTS.csv
docs/betrieb/artifacts-2026-10-07-feld/feld-s2-prep/f1-car-notes.jsonl
docs/betrieb/artifacts-2026-10-07-lab/T1-T4-ERGEBNIS.md
docs/betrieb/artifacts-2026-10-07-lab/C1-C7-ERGEBNIS.md
docs/fahrzeug/HU-Technical-Facts.md
docs/planung/Stufenplan.md
```
