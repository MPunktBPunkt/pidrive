# Übergabe an die nächste KI · PiDrive Stand 2026-10-16

**Prüfer dieser Übergabe:** Cursor (Composer) · **Datum:** 2026-10-16 (Abend)  
**Repo:** [MPunktBPunkt/pidrive](https://github.com/MPunktBPunkt/pidrive)  
**HEAD:** `6e17ddd` (`main` == `origin/main`, lokal verifiziert nach `git fetch`)  
**FW-Repo:** [MPunktBPunkt/esp32.pidrive](https://github.com/MPunktBPunkt/esp32.pidrive) · origin `7ffed20` · **Soft-USB-Identity-Fix nur lokal uncommitted** (`esphub/esp32.pidrive`)

**Kanonische Quellen im Commit:**
- [`UEBERGABE-TAG-2026-10-16.md`](UEBERGABE-TAG-2026-10-16.md)
- [`feld-512kib-predict-01/ERGEBNIS.md`](feld-512kib-predict-01/ERGEBNIS.md)
- [`../artifacts-2026-10-16-lab/lab-soft-cycle-052/ERGEBNIS.md`](../artifacts-2026-10-16-lab/lab-soft-cycle-052/ERGEBNIS.md)
- [`../artifacts-2026-10-16-lab/lab-soft-cycle-052/PRIORITAET-SHIFT.md`](../artifacts-2026-10-16-lab/lab-soft-cycle-052/PRIORITAET-SHIFT.md)
- [`docs/fahrzeug/HU-PARAMETER-MATRIX-2026-10-16.md`](../../fahrzeug/HU-PARAMETER-MATRIX-2026-10-16.md)
- Quiet-Gate: `tools/soft_cycle_orchestrator.py`

**Externe Reviews (Konsens, hier verdichtet):** Mistral · GPT · Grok — methodisch einig; Abweichungen unten markiert.

---

## 0. Ein Satz

Der 512‑KiB-Modelltest hat die Vorhersage `8+4×240+56` widerlegt und durch das reproduzierte Muster **`240,240,32,240,240,32`** ersetzt (A2/A7 → [S]); der alleinige P0-Blocker ist jetzt **Panic/weiße LED bei physischem OTG** — Full-File-READ ≠ hörbarer Ton.

---

## 1. Verifikation (diese Sitzung)

| Check | Ergebnis |
|-------|----------|
| `pidrive` HEAD == origin/main | ☑ `6e17ddd` |
| A7 in drei Captures (Blöcke) | ☑ `240,240,32,240,240,32` Summe 1024 |
| A7 kontinuierliche LBA | ☑ z. B. BOB `17489→17729→17969→18001→18241→18481`; Tip Bayern anderer Slot `16465…17457` |
| Quiet-Gate `play`/`scan` | ☑ in `soft_cycle_orchestrator.py` |
| Soft-USB `armSoftUsbKeepIdentity` auf GitHub | ✗ **nicht** auf `esp32.pidrive` origin; lokal dirty (3 Dateien) |
| R34 Rohquelle | ☑ in `HU-Technical-Facts.md` R34/R23 (S3/S4/F1) — **nicht** aus heutigem Feldlauf, aber nicht „ohne Quelle“ |
| Matrix-Inkonsistenz | ⚠ §1 A2 = [S], aber §2-Tabelle „Max. READ10“ noch Status **[A]** — Housekeeping |
| `HU-Technical-Facts.md` ohne A7-Blindcommit | ☑ korrekt freigehalten |

---

## 2. Was als Fakt gilt (USB / READ10)

| Parameter | Stand | Status |
|-----------|-------|--------|
| Max READ10 | 240 Blöcke = 120 KiB | **[S]** (A2) |
| READ10 > 240 | in gültigen Captures nicht gesehen | — |
| 512‑KiB Full-File (dieser Betriebszustand) | `240/240/32/240/240/32` | **[S]** (A7) |
| Summe | 1024 × 512 B = 524 288 B | exakt |
| Full-File-READ ⇒ Ton | **nein** (Tip Bayern: 1024 ohne Ohr) | Beobachtung [S] |
| LIVE nach Klasse-A-OTG | 2× ~5–6 s (einmal +Bild) | Beobachtung; **kein** harter „NBT-Limit=5 s“-Parameter |
| Panic bei physischem OTG | häufig; Serial `PD0261`→`PD0282` | P0-Blocker |

**Modellgrenze A7:** gilt für **512‑KiB-Slot** unter den gemessenen Bedingungen — **nicht** generalisieren ohne Größenleiter.

**Transporteinheit:** CBW = 120 KiB. 4 KiB bleibt ESP-Callback-Größe.

---

## 3. Lab (grün, bewusst gestoppt)

| Gate | Status |
|------|--------|
| Soft-USB Zelle | PASS |
| Vollmatrix 5 Zellen | PASS (`matrix-full-03`) |
| Soft-USB 10/10 | PASS → **Stopp** (kein Overnight-100) |
| Capture Lab | `ram_local`; `ram_wifi_off`+Soft-USB → 409 |

---

## 4. Konsens der Reviews + Abweichungen

**Einigkeit Mistral/GPT/Grok:**
1. Modelltest-Disziplin vorbildlich (Vorhersage → Messung → Widerlegung).
2. P0 allein = Panic/OTG; Reihenfolge Panic → (Capture-Arm) → 128k/Stall → F0 → Größenleiter.
3. Kein Ring blind, kein Overnight Soft-Cycle, keine weiteren reinen 512‑KiB-Wiederholungen, kein F0 jetzt.
4. Capture vor Tip/OTG + Auto-Stop ist Pflicht vor dem nächsten Feldtermin.
5. 128 kbit/s nach stabilem OTG = hoher Erkenntnisgewinn/pro Feldminute.

**Diese Übergabe präzisiert:**
- **R34:** nicht „ungeprüft“ — Quelle ist Facts R23/R34 (S3/S4). Flag nur: Matrix-Zeile sollte auf Facts verweisen; kein heutiger Feldbeleg nötig für Bestand.
- **5–6 s:** Beobachtungsfenster unter instabiler Klasse A, **kein** neuer Live-Dauer-Parameter (GPT/Grok) — übernehmen.
- **A7-Folgemesse:** Größenleiter erst **nach** Panic-Fix (nicht parallel als P0).

---

## 5. Offene Punkte (B-Liste)

| ID | Punkt | Prio |
|----|-------|------|
| **B1** | Panic/Brownout physischer OTG: UART-Resetgrund, Panic-Tail, `resetReason`, Netzteil A/B, VBUS (Q11) | **P0** |
| **B2** | MessCapture vor Tip/OTG armieren + Auto-Stop (`play` leer / Underrun-Spike); Lab-Smoke, dann Feld | C → vor nächstem Feld |
| **B3** | `esp32.pidrive`: Soft-USB-Identity-Fix committen + pushen (`armSoftUsbKeepIdentity`) | C sofort |
| **B4** | Matrix §2 „Max. READ10“ Status [A]→[S] angleichen; R34-Zeile Quelle `Facts R34` explizit | Housekeeping |
| **B5** | A3/A4: Stall-Leiter 10/20/30/45 s **pro 240-CBW** am NBT — erst dann Facts | nach B1 |
| **B6** | A5 Prefetch [H] — Marker+LBA, keine Bestätigungsmessung | später |
| **B7** | Artefakt-Volumen (+121k Zeilen) — langfristig Index/Archivschema | C niedrig |

---

## 6. Auftrag — Reihenfolge (nicht umstellen)

### Phase 1 — P0 Panic/Brownout
Ziel: physischer OTG-Replug **ohne weiße LED** reproduzierbar.  
Instrumentierung: UART + Panic-Tail + `resetReason` + VBUS/Strom + Netzteil A/B.  
Entscheidung: Stack/USB vs. Power.

### Phase 2 — Capture-Automatisierung (B2)
Vor dem nächsten Feldtermin im Lab: Arm → Tip/OTG → korreliert READ/Status/Underrun/`play` → Auto-Stop.

### Phase 3 — 128 kbit/s Gegenprobe
Nach stabiler Klasse A: 48 vs 128 kbit/s, gleicher Slot/Aktion.  
Messen: UI-Freeze, CBW-Dauer, Ring, Host-Cursor, Tonfenster, Underruns.

### Phase 4 — Stall-Leiter (A3/A4)
10/20/30/45 s pro 240-Block-CBW.

### Phase 5 — F0 B1–B3
Nur mit stabiler Klasse A (sonst Panic⊕Identity vermischt).

### Phase 6 — Größenleiter (A7 verallgemeinern)
Vorhersage **vorher schriftlich**, z. B. 256 KiB → `H0: 240,240,32` / Alternativen. Keine weiteren 512‑KiB-Only-Wiederholungen.

### Nicht jetzt
- Ring blind vergrößern  
- Soft-Cycle Overnight-100  
- F0 starten  
- A7/A-Ableitungen ungeprüft nach `HU-Technical-Facts`  
- FM-TX / Soft-Cycle-Ausbau  

---

## 7. Ampel

| Bereich | Ampel |
|---------|-------|
| Modelltest 512 KiB / A2 / A7 | 🟢 |
| Matrix-Epistemik (Facts clean) | 🟢 |
| Lab Soft-Cycle + Quiet-Gate | 🟢 |
| LIVE prinzipiell | 🟠 (~5–6 s, selten) |
| Ton↔READ-Korrelation | 🟠 (kein Capture im Tonfenster) |
| Panic/OTG | 🔴 **alleiniges P0** |
| Stall | 🔴 Freeze (korrekt) |
| F0 | 🟡 Tooling bereit, zu früh |
| esp32 Soft-USB-Push | 🟡 lokal dirty |

---

## 8. Kernaussage (Copy-Paste)

> Stand 2026-10-16 / pidrive `6e17ddd`: Modelltest widerlegt `8+4×240+56`; NBT liest 512‑KiB-Slots als `240,240,32,240,240,32` (A2/A7 [S], LBA-kontinuierlich, dreifach). Full-File-READ ≠ Ton. P0 = Panic/weiße LED bei physischem OTG. Nächste Schritte: (1) Panic isolieren, (2) Soft-USB-Fix in esp32.pidrive pushen, (3) Capture vor OTG armieren, (4) 128k + Stall-Leiter, erst dann F0 und Größenleiter. R34 hat Facts-Quelle (S3/S4); Matrix §2 A2-Status noch angleichen.
