# Übergabe — Lab D-Startgate / HU-A1 · für die nächste KI · 2026-10-13

**HEAD (verifiziert gegen GitHub, pull 2026-10-13):**

| Repo | Commit | Hinweis |
|------|--------|---------|
| `pidrive` | `4b0ec82` | Lab HU-A1 `gate_green`, Tooling, Artefakte |
| `esp32.pidrive` | `41f66c3` | **0.4.51-dev** Soft-Remount Phase-Fix |
| `technology-audit` | `fbabb86` | **Standard 0.7.1** (`VERSION`); enthält u. a. `ad029b5` (TinyUSB BUSY/ASYNC) und die 2026-10-13-Kampagnen |

**Lab `.88`:** `0.4.51-dev`, Exit **`stallEnable=false`**, Serial zuletzt `PD0446`  
**Feld `.89`:** aus diesem Netz nicht erreichbar; laut s6-Übergabe zuletzt **`0.4.48-dev`**, `stallEnable=false` — vor F0-Go bestätigen  
**UART:** weiterhin **nicht** angeschlossen (Lab Preflight skipped)

Kanonische Lab-Quelle: [`ERGEBNIS.md`](ERGEBNIS.md) · Artefakte `a1-*-051/`, `identity-*/` · Runbook [`../../LAB-D-STARTGATE-RUNBOOK.md`](../../LAB-D-STARTGATE-RUNBOOK.md)  
Vorherige Feld-Übergabe: [`../artifacts-2026-10-12-feld/UEBERGABE-S6-NAECHSTE-KI-2026-10-12.md`](../artifacts-2026-10-12-feld/UEBERGABE-S6-NAECHSTE-KI-2026-10-12.md)

Dieses Dokument ist der **kanonische** Auftrag nach Abgleich Mistral- + GPT-Bericht.

---

## 0. Kurzurteil

**D-STARTGATE (Lab) = GREEN.** Mechanik, Identity-Instrumentierung und Prefetch-Quantifizierung sind erledigt.

**Nicht GREEN:** NBT-Cache/Resume-P, UART/Q11, Stall-Feld-Go, D1–D3.

Nächster Meilenstein ist **F0 am NBT** (Identity vs. Silence-Cache diskriminieren) — **nach** Feld-Go OTA **0.4.51** auf `.89` mit Default `stallEnable=false`.

---

## 1. Review Mistral vs. GPT (faktisch)

| Claim | Mistral | GPT | Verifikation |
|-------|---------|-----|--------------|
| Lab HU-A1 no/mid/head PASS, nur Head `gate_green` | ✅ | ✅ | ✅ Artefakte `a1-*-051` |
| Prefetch 8 294 400 B = **98,877 %**, ID3:1 / SILENCE:2024 | ✅ | ✅ | ✅ alle drei 051-Reports |
| 0.4.51 Soft-Remount `phase=Idle` rettet Settle/Arm | ✅ | ✅ | ✅ Code `41f66c3` + Head-Events |
| Identity volume-id / label / serial isoliert PASS | ✅ | ✅ (+ Label=BPB+Root, Serial=+Rev) | ✅ |
| Silence-Prefetch = Ursache stummer fav0 | „mechanische Erklärung“ | starke Inferenz, kein Decoder-Beweis | **GPT richtig** — Status **[I]** |
| `gate_green` = NBT-Resume-Beweis | tendenziell überhöht („wasserdicht“) | klar nein | **GPT richtig** |
| Timing-Ausreißer Head (max ~843 ms, late_reads, waitMsMax 824) | untergewichtet | betont | **GPT richtig** — Stall-Feld-Go weiter **NO** |
| F0 als nächster Schritt; Rotate vs. No-Rotate trennen | ✅ | ✅ | **beide richtig** |
| F0 braucht Feld-OTA 0.4.51 | ✅ | ✅ (etwas vorsichtiger) | **übernehmen** |
| technology-audit HEAD | `e5c91ad` / 0.7.0–0.7.1 | `ad029b5` / **0.6.6** | **beide falsch/veraltet** → **`fbabb86` / `VERSION=0.7.1`**; `ad029b5`-Inhalt bleibt relevant (BUSY/ASYNC im Sheet) |
| „kein offener Punkt ohne Messwerkzeug“ | zu stark | korrigiert | UART + echte NBT-Cache-Wirkung offen |

**Fazit Abgleich:** Technische Kernaussage beider Berichte ist brauchbar. Für die nächste KI **diesen** Bericht nutzen, nicht Mistral oder GPT ungeprüft.

---

## 2. Was Lab belegt (0.4.51)

### 2.1 HU-A1

| Selection | PASS | gate_green | stall_armed | Artefakt |
|-----------|------|------------|-------------|----------|
| no-read | ✅ | false | false | `a1-no-read-051/` |
| mid @1 MiB | ✅ | false | false | `a1-mid-051/` |
| head | ✅ | **true** | **true** | `a1-head-051/` |

Head-Kette: `play.guess fav0` → `msc.stall_armed fav0` · Prefetch-Klassen unverändert SILENCE.

`gate_green` = Lab-Mechanik (Head ∧ S7 armed ∧ LIVE). **Nicht** NBT-P/Cache.

### 2.2 Prefetch

| Größe | Coverage | Klassen |
|------:|---------:|---------|
| 8 294 400 / 8 388 608 B | **98,877 %** | ID3:1 · SILENCE:2024 |

**FACT [B] Lab:** Read-Sequenz + Byteklassifikation.  
**INFERENCE [I]:** plausibler Mechanismus für s6-fav0-Stummheit.  
**UNKNOWN:** ob der NBT-Decoder später genau diesen Cache abspielt.

### 2.3 Identity-Smoke (0.4.50, Instrumentierung)

| Dimension | Drift | PASS |
|-----------|-------|------|
| volume-id | nur `bpbVolumeId` | ✅ |
| label | `bpbLabel` + `rootLabel` gemeinsam | ✅ |
| serial | `usbSerial` + `productRevision` | ✅ |

Belegt Steuerbarkeit — **nicht** NBT-P-Bruch.

### 2.4 FW-Fixes

| Ver | Inhalt |
|-----|--------|
| 0.4.50 | `ConfigStore.fatVolumeId`; Preflight `uptimeMs` PASS |
| 0.4.51 | Soft-Remount: `phase=Idle`, stall/playGuess clear → Quiet/Settle möglich |

### 2.5 Head-Timing (Gate grün ≠ robust)

Aus `a1-head-051`: SG p50≈4 ms, **max≈843 ms**, late_reads=36, `stall.waitMsMax=824`, Retries während Arm.  
→ logisches Gate PASS; **kein** Stall-Feld-Go.

---

## 3. Technology-Audit (korrekt)

- **HEAD:** `fbabb86` · **Standard: 0.7.1**
- Busy/ASYNC-Desk (`ad029b5`) ist im `usb-msc`-Sheet und Methodenindex enthalten — Host-Timeout ≠ Device-BUSY trennen.
- 2026-10-13-Kampagnen: HU-A1 zuerst; NBT-Index liefert keinen Live-Cache-Beweis.

---

## 4. Beweisstand (verbindlich)

| Claim | Status |
|-------|--------|
| E7-C NBT Busy-Pacing (s6) | FACT (C) Feld |
| S7-B Arm nur nach Head (0.4.51 Lab) | FACT (B) Lab |
| Soft-Remount Idle/Settle | FACT (B) Lab + Code |
| Prefetch 98,877 % SILENCE | FACT (B) Lab |
| Prefetch verursacht NBT-Stille | INFERENCE |
| Identity-Dimensionen isoliert steuerbar | FACT (B) Lab |
| Identity bricht NBT-Cache / Resume-P | **UNKNOWN → F0** |
| UART/Q11 Reset-Ursache | UNKNOWN |
| Stall-Feld-Go | **NO** (`stallEnable=false`) |
| D1–D3 | **blockiert durch F0** |

---

## 5. Maßnahmen (verbindliche Reihenfolge)

### P0 — Freeze / Infrastruktur

1. Lab `.88` und Feld: **`stallEnable=false`** bis explizites D-/F0-Go mit Stall.  
2. **UART physisch** Lab + Feld anschließen → `tools/lab_uart_reset_log.py` (DTR/RTS off).  
3. Kein Architektur-Umbau; kein dyn. FAT-Grow; kein Sofort-2 GiB.

### P1 — Feld-Go 0.4.51 (Voraussetzung F0)

4. **Ein Go:** OTA **`0.4.51-dev`** auf `.89` (bringt fatVolumeId + Remount-Phase + S7-B).  
5. Default nach OTA: **`stallEnable=false`**.  
6. Kurz-Smoke: Mount, Menü, eine Head-Station hörbar (ohne Identity-Matrix).

### P2 — NBT-F0 (Kerntest, ~15–25 min)

Ziel: **eine** Frage — beeinflusst Identity den NBT-Cache/Resume so, dass der nächste Start LIVE statt Silence/Mid ist?

**Protokoll (Dimensionen getrennt, nie kombiniert mit Head-Force):**

| Lauf | Identity | Erwartung wenn Rotate wirkt | Erwartung wenn nur Prefetch-Cache |
|------|----------|-----------------------------|-----------------------------------|
| B0 | keine Änderung, Replug bei P≫0 | weiter Stille / Mid / Cache | Stille / Cache |
| B1 | nur **serial** (+Rev) | Head → LIVE / hörbar | unverändert Stille |
| B2 | nur **label** (BPB+Root) | wie B1 | wie B0 |
| B3 | nur **volume-id** | wie B1 | wie B0 |

Messung: Operator-Ohr · `play.guess` Timing · erste LIVE-Bytes · Status `bpbVolumeId`/`bpbLabel`/`usbSerial` · Fenster-Telemetrie (`feld_status_poll` / Live-Window).  
Prefetch-Silence-Hypothese **mit** testen (B0 vs. B1–B3), nicht nur „Identity und hoffen“.

**F0-Ergebnis → D-Parameter:**

- Rotate bricht P/Cache → D-Slots mit Session-Identity-Rotation.  
- Rotate bricht nicht, B0=Stille → Prefetch-Cache dominant → Head-Force / Remount-ohne-keepIdentity spezifizieren (eigenes Lab-Gate).  
- Unklar / Klasse B → UART-Log + Wiederholung.

### P3 — erst nach F0

7. **D1** (1 MiB Fixed Huge) Lab, dann Feld — mit F0-Parameter.  
8. D2 / D3 (2 / 8 MiB) inkl. Resume-Test je Stufe.  
9. Offset→Audio-Timeline und `maxMs`-Feintuning **nach** grünem D-Hauptpfad.

### Nicht tun

- D1–D3 vor F0.  
- Stall im Feld ohne neues Go.  
- Alle Identity-Dimensionen in einem Replug mischen.  
- Identity-Rotation und Head-Force im selben Lauf.  
- `gate_green` oder 98,877 % als NBT-Beweis zitieren.  
- Audit-HEAD als `ad029b5` oder Standard `0.6.6` führen.

---

## 6. Ziel-Meilenstein nächste Iteration

> **F0:** Nach OTA 0.4.51 auf `.89`: mindestens eine isolierte Identity-Dimension erzeugt nach Replug bei P≫0 einen hörbaren Head/LIVE-Start statt Silence-Cache; Kontrolllauf ohne Identity-Wechsel bleibt stumm/cached — oder widerlegt die Rotate-These klar zugunsten Prefetch-Cache/Head-Force.

Wenn F0 scheitert (keine Dimension hilft) → Option B (Slot-Kette) und/oder Head-Force priorisieren (siehe s6-Übergabe).

---

## 7. Arbeitsanweisung an die nächste KI

1. Lab-Mechanik **nicht** erneut debattieren — D-Startgate ist GREEN.  
2. Drei Ebenen getrennt halten: ESP-FW · USB/NBT-Host · Audio-Ohr.  
3. Mit **P1 Feld-Go 0.4.51** starten (nach Operator-Go), dann **P2 F0**.  
4. Epistemik: Prefetch = FACT Lab / INFERENCE für Stummheit; Identity-P = UNKNOWN bis F0.  
5. Stall bleibt eingefroren bis neues Go.

---

## 8. Lab-Nachzug (ohne Feld, 2026-10-13 nachmittag)

Ohne NBT-Zeit zusätzlich gelaufen auf `.88` / `0.4.51-dev`:

| Test | Ergebnis | Artefakt |
|------|----------|----------|
| **D0** Regression (fav2 512 KiB, Mode B) | **PASS** — p50≈736 ms, undDelta=0, ~86,9 s | [`lab-d0-051/`](lab-d0-051/) |
| **D3-Partial** 1 MiB paced auf fav0 8 MiB | **PASS** — armed + p50≈736 ms, LIVE, und=0 | [`lab-d3-partial-051/`](lab-d3-partial-051/) |

**Nicht** erledigt (braucht Build bzw. Feld): D1/D2-Geometrie-Flags, volles D3-EOF (~22 min), F0.

Freeze danach: `stallEnable=false`.
