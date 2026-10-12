# Übergabe — Feld s6 / E7-C · für die nächste KI · 2026-10-12

**HEAD:** `pidrive 2b285c9` · `esp32.pidrive e913ae9` (`0.4.48-dev`) · `technology-audit ad029b5`  
**Feld `.89`:** `0.4.48-dev`, Exit-Zustand **`stallEnable=false`**  
**Artefakte:** [`feld-s6-prep/ERGEBNIS-S6.md`](feld-s6-prep/ERGEBNIS-S6.md) · [`feld-s6-prep/s6-20261012-feld-e7/`](feld-s6-prep/s6-20261012-feld-e7/)  
**Lab-PC:** [`../artifacts-2026-10-12-lab/lab-e7-ladder/ERGEBNIS.md`](../artifacts-2026-10-12-lab/lab-e7-ladder/ERGEBNIS.md)

Quellen geprüft: gepushte s6-JSONs/Marks · Stall-Code `UsbMscGadget.cpp` · Mistral-Übergabe · GPT-Analyse · Mistral-Korrektur. Dieses Dokument ist der **kanonische** Auftrag.

---

## 1. Meilenstein (unverändert gültig)

| Claim | Status | Beleg |
|-------|--------|-------|
| Ohne Stall ≈ **6 s** Ringfenster | **FACT (C)** | s6 Phase 1 + Kontrollstichprobe 17:15 |
| Mit Stall ≈ **65 s** Musik+ID3 bis **EOF** (512 KiB-Slot) | **FACT (C)** | Operator 17:09; kausal A/B |
| NBT akzeptiert Busy-Retry (`return 0`) über Minuten | **FACT (C)** | Hör + Telemetrie |
| Ursache = Busy-Pacing, nicht Glück/größerer Ring | **FACT** | Stall aus → wieder ~6 s; Ring blieb 48 KiB |
| PSRAM als *Primär*lösung gegen HU-Burst | **nicht mehr nötig** | Welt A Stall-Spec |

**Telemetrie — zwei Snapshots nicht vermischen:**

| Snapshot | cmds | retries | timeouts | playReject |
|----------|------|---------|----------|------------|
| Long-audio (~17:06) | 2272 | 120730 | 76 | 1237 |
| Session-Ende (`status-final`) | **2399** | **147865** | **80** | **2279** |

`waitMsMax=1001` = `maxMs`. Kurze Hörlücken ≈ Silence-Fallback.

**Zeitrechnung:** 524288 B @ **6000 B/s** ≈ **87 s** Soll; Operator ~65 s = Schätzung, nicht Messuhr. EOF wurde erreicht — Plausibilität ok, keine exakte Dauer-Telemetrie (fehlt: Poll *während* Dauerstrom).

---

## 2. Prüfung Mistral / GPT — Urteil

| Thema | Mistral#1 (Slot-Kette B) | GPT (Fixed Huge File D) | Mistral#2 (Korrektur) | Diese Prüfung |
|-------|-------------------------|-------------------------|----------------------|---------------|
| E7-C belegt | ✅ | ✅ | ✅ | **✅ übernommen** |
| A/B-Kausalität | ✅ | ✅ | ✅ | **✅** |
| Primärpfad Endlos | **B** Slot-Kette | **D** großer fester Live-File | **D**, B=Fallback | **D zuerst**, B Fallback |
| Dyn. FAT-Größe wachsen | — | UNKNOWN / schlecht | zustimmt | **kein Hauptpfad** |
| Resume-P bei großem File | warnte fav0 | zu spät als „Stufe 2“ | **kritische Lücke** | **✅ Mistral#2** — D braucht Identitäts-Rotation oder erzwungenen Head-Start |
| 20 s Menü | stallScope/Meta | BUSY auf FAT/DIR | schärfer: Body-Probes / aktiver Slot | **Code-Check unten** |
| Zahlen 2272 vs 2399 | ERGEBNIS 2399 | mischte Snapshots | korrekt gerügt | **beide gültig, labeln** |

**Code-FACT zur 20‑s-Frage** (`onRead`):

- Stall greift **nur** wenn `stream active` **und** LBA ∈ **aktiver** `streamSlot_`.
- **FAT/DIR/Boot** werden **nicht** über `onReadLiveStall` gebremst.
- Andere Slots → sofort `Mp3Silence` (kein BUSY).
- ID3/Cover-Kopf (`fileOff < id3Len`) → nie Stall.

Damit ist GPT-Formulierung „BUSY bremst FAT/Directory“ als **Code-Claim REJECTED**.  
**FACT (C):** ~20 s Bedienbarkeit nach OTG unter Stall.  
**INFERENCE:** Initialisierung/Index der HU kollidiert mit frühen **Body**-Reads (ggf. schon live-armed Slot) und/oder hohen `playReject`s — nicht mit FAT-BUSY.  
**HYPOTHESIS:** Strikter „BUSY nur aktiver Slot **nach** gültigem Head-Play“ + sofortige Antworten sonst → Latenz sinkt (Test S7).

„Erst nur BOB, Ton erst nach Filewechsel“ passt zu: hoher `playRejectCount`, später `playGuess`; Filewechsel erzeugt frischen Head-Kontext → Stream zündet → E7-Pacing.

---

## 3. Kernfrage „Radio ohne Ende“

**Nicht:** Datei dynamisch in FAT vergrößern (Mount-Cache → UNKNOWN).  
**Sondern:** Von Anfang an **feste große** virtuelle Datei + BUSY an der Producer-Grenze + **niemals EOF während Radio**.

| Option | Rolle nach s6 |
|--------|----------------|
| **D — Fixed Huge Live File** | **Hauptpfad** (GPT + Mistral#2) |
| **B — Slot-Kette / Autoplay** | **Fallback**, wenn D scheitert oder Resume unlösbar; Autoplay-ohne-Kopf in s6 noch REJECTED |
| **A — nur größer** | Baustein von D, allein unzureichend (fav0 8 MiB stumm) |
| **C — „unendlich“/2 GiB + History** | später; braucht stabile Offset→Timeline (+ ggf. History/PSRAM für Seek) |

**D produktreif nur mit:**

1. **Offset → Audio-Timeline** monoto/stabil für die Session (Vorwärts-Live zuerst).  
2. **Resume-P-Abwehr:** Session-Identität rotieren (Serial/Label/Name — Tools existieren) **oder** Mid-File-Start → Remount/Head erzwingen — sonst toter Start (fav0-Warnung).  
3. **BUSY nur aktiver Slot nach Play** (Code schon nah; Startup-Pfad härten).  
4. Menü-Latenz messbar &lt; wenige Sekunden.

---

## 4. Maßnahmen (verbindliche Reihenfolge)

### P0 — Freeze / Feldzustand

1. Feld-Default: **`stallEnable=false`** bis explizites Go.  
2. FW `.89` = `0.4.48-dev` belassen.  
3. Kein Architektur-Umbau ohne Lab-Gate.

### P1 — S7 Startup-Usability (vor Größenleiter im Feld)

4. **S7-A:** Stall an wie s6; nach OTG Zeitstempel: first FAT/DIR (Host), first file body, first `playingUid`, first audio; `playReject`‑Rate.  
5. **S7-B:** Stall **nur** Body des aktiven Slots **nach** Head-Play; alles andere sofort (Silence/Meta). Ziel: Dateien &lt;~3 s nutzbar.  
6. Dokumentiere 20 s als Usability-FACT, nicht als „NBT mountet 20 s“.

### P2 — D-Leiter (Lab zuerst, dann Feld Go)

7. **D0:** Regression 512 KiB + Stall → &gt;60 s bis EOF (PC + optional NBT).  
8. **D1–D3:** 1 MiB → 2 MiB → 8 MiB Fixed Size; BUSY an; **jede Stufe mit Resume-Test** (Replug bei P≫0: Ton? oder Identity-Rotate → Head).  
9. **D4:** ID3/Cover/Head-Start je Größe.  
10. Telemetrie-**Poll während** Dauerstrom (nicht nur kumuliert).

### P3 — Tuning (parallel, nicht vor D0)

11. `maxMs`‑Leiter 2000/5000 erst nach Kenntnis der Timeout-Ursache (Producer leer vs. Scope).  
12. Q11 UART bei Klasse B (separat).

### P4 — Fallback B (nur wenn D stockt)

13. Slot-Kette + `leadBytes`/Head-Snap; Autoplay-Übergang gezielt lab+feld.

### Nicht tun

- Dyn. FAT-Size während Mount als Produktpfad.  
- Sofort 2 GiB ohne Offset-Zuordnung + Resume-Plan.  
- Slot-Kette als *einzigen* nächsten Schritt.  
- PSRAM-Primärpfad gegen Burst (erledigt durch E7).  
- „FAT wird gebusyt“ als Sheet-FACT schreiben.

---

## 5. Ziel-Meilenstein für die nächste Iteration

> **D-E7:** Fester großer virtueller Live-File bleibt offen; NBT wird an der Producer-Grenze nur per BUSY gepaced; im Testfenster kein Radio-EOF; nach OTG Menü in wenigen Sekunden bedienbar; Resume-P erzeugt keinen stummen Mid-File-Start (Rotate oder Head-Force).

Wenn D-E7 scheitert → Option B priorisieren.

---

## 6. Verweise

- [`feld-s6-prep/ERGEBNIS-S6.md`](feld-s6-prep/ERGEBNIS-S6.md)  
- [`../../../planung/MASSNAHMEN-E7-AUDIT-ABGLEICH-2026-10-12.md`](../../../planung/MASSNAHMEN-E7-AUDIT-ABGLEICH-2026-10-12.md)  
- [`../../../planung/STALL-BUILD-SPEC-2026-10-08.md`](../../../planung/STALL-BUILD-SPEC-2026-10-08.md)  
- Stall-Implementierung: `esp32.pidrive` `UsbMscGadget::onRead` / `onReadLiveStall`
