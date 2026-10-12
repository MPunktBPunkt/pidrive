# Maßnahmen — E7 / Audit-Abgleich · 2026-10-12

**Quellen:** GPT nach `technology-audit` Kampagne `tinyusb-msc-busy-retry-2026` (closed) · Sheet `usb-msc` Busy/Async · Method `msc-busy-retry-semantics` · Application B `esp32-pidrive/usb-msc` · PiDrive Stall-Spec · Feld s5 (11.10.)  
**Status:** kanonischer Arbeitsauftrag. **Kein** OTA-/Stall-Feld-Flash ohne explizites Go. Stall-Defaults bleiben `stallEnable=false` (= 0.4.46-Verhalten).

**Lab-Stand (heute):** `.88` = **`0.4.48-dev`** (Busy-Timer-Fix), nach Tests `stallEnable=false`. Feld `.89` unberührt.  
E7-PC-Leiter: [`../betrieb/artifacts-2026-10-12-lab/lab-e7-ladder/ERGEBNIS.md`](../betrieb/artifacts-2026-10-12-lab/lab-e7-ladder/ERGEBNIS.md) — **L0/L1/L3/L4 PASS; L2 TEIL; NBT offen.**

---

## 1. Gesamturteil (Busy-Audit + GPT)

**GPT hat recht — zur Hälfte:** Das Desk-Audit löst den Stack-Unsicherheitsfaktor, beweist aber **nicht**, dass E7 im BMW funktioniert.

| Frage | Status nach Audit |
|-------|-------------------|
| TinyUSB MSC `return 0` = BUSY? | **FACT** (`TUD_MSC_RET_BUSY`) |
| Derselbe READ10/CBW bleibt offen, kein CSW? | **FACT** |
| Callback erneut mit gleichen Params? | **FACT** (Fake-`dcd_event_xfer_complete`) |
| `return 0` = STALL/Fehler? | **REJECTED** |
| TinyUSB Device-BUSY-Timeout? | **REJECTED** (kein Driver-Timeout) |
| Arduino-ESP32 0.15: onRead 1:1, kein ASYNC, EP 4096? | **FACT** |
| PiDrive: `vTaskDelay` + `return 0`, nie `<0`? | **FACT (B)** `onReadLiveStall` |
| PC/NBT toleriert lange BUSY-Zyklen? | **UNKNOWN** → E7 Lab/C |
| Hybrid B′ unter Producer/WiFi-Last stabil? | **UNKNOWN** (#3) |
| Löst BUSY das 132:1-Problem grundsätzlich? | **potentiell JA** — nur wenn Host wartet |

**Architekturfolge:** Mit belegt BUSY-Mechanismus ist E7 kein Architektur-Rätsel mehr, sondern ein **Machbarkeitstest**. Größerer Ring / PSRAM sind für *dieses* Lösungsprinzip nicht primär nötig — aber **erst nach E7-Negativ** spezifizieren (Plan B).

**Korrektur zu „direkt E7 im Auto“:** Feld s5 → Versorgung/Reset unter Last blockiert Ohr@32k. **Q11/Steckfestigkeit vor Stall-Feld.** Lab-E7 parallel erlaubt und jetzt der Haupthebel.

---

## 2. Modell (verbindlich)

```text
HU READ 4 KiB
    ↓
onRead: liveAvail < 4096?
    ├── nein → Bytes liefern → CSW
    └── ja  → vTaskDelay(retryMs) + return 0
              ↓
         BUSY (READ10 offen)
              ↓
         onRead erneut …
              ↓
         nach maxMs: Silence-Fallback (nie return <0)

132:1 (HU ~800 kB/s vs Producer ~6 kB/s):
  ohne BUSY → Ring leer → Stille
  mit BUSY  → Host-Takt ≈ Producer-Takt  (~683 ms / 4 KiB @6 kB/s)
              — NUR wenn Host die Wartezeit akzeptiert
```

```text
PiDrive MSC
                 │
    ┌────────────┴────────────┐
    ▼                         ▼
Host Identity              Read Timing
 Serial · Label · Name      Burst · Pacing(E7)
    │                         │
 empirisch: Serial/Name ✗     132:1 Konflikt
 Label isoliert: UNKNOWN  → Stall (E7) | Zeitversatz (PSRAM)
```

---

## 3. Zwei E7-Varianten (nicht vermischen)

| ID | GPT-Name | Repo-Tool / Spec | Frage |
|----|----------|------------------|-------|
| **E7-A** | künstliches Delay | `lab_e7_delay_ladder.py --mode A` + Spec L0/L3/L4 | Wie lange toleriert der **Host** einen offenen READ (BUSY-Retries)? |
| **E7-B** | echtes Producer-Pacing | `--mode B` + Spec L1/L2 | Funktioniert die **Produktmechanik** (MSC + TinyUSB + WiFi + Producer + pump + Callback)? |

**E7-B ist der Architektur-Gate.** E7-A findet zuerst die Abort-Grenze (PC, dann NBT).

Delay-Raster (Lab-ms, **kein** Sheet-A-FACT):  
`0 / 0.1 / 1 / 2 / 5 / 10 / 25 / 50 / 100 / 250 / 500 / 1000 / 2000 / 5000` ms — Grenze suchen, nicht sofort 5 s als Produktverhalten.

Messgrößen je Stufe: READ-Dauer, `stall.retries`, Host-Abort, Bus-/BOT-Reset (`botResets`), CSW ok?, gelieferte Bytes, Task-Alive (Producer/WiFi).

---

## 4. Maßnahmen

### P0 — Feldblocker (ohne Stall-FW) — parallel, nicht blockierend für Lab-E7

1. UART ohne DTR/RTS → `rst:` / Brownout vs. Soft-Reset (**Q11**).  
2. Stecklast: Bridge/WLAN erst nach stabilem OTG; Tip nur bei `playingUid`/`absEnd>0`.  
3. Ohr@32k A/B nachholen (s5-Diskriminator), sobald Klasse A trägt.

### P1 — E7 Lab (jetzt) — Reihenfolge strikt

| # | Schritt | Go / Gate | Soll |
|---|---------|-----------|------|
| 4 | L0 Baseline: `stallEnable=false` + `nbt_hu_sim --golden REPLUG` | Operator | wie 0.4.46 |
| 5 | **E7-A PC:** Delay-/`stallMaxMs`-Leiter, 4‑KiB-Callback, Host-Abort finden | Operator + SG | Abort-ms bekannt; ESP stabil |
| 6 | **UNKNOWN #3:** unter Live-Producer/WiFi messen, ob B′ (`vTaskDelay`+`return 0`) Tasks freigibt (`retries`↑, kein WDT, Pump lebt) | nach 5 | Hybrid nicht nur Desk |
| 7 | **E7-B PC:** Live-Pacing Spec L1 (chunk 4096) → L2 (chunk 512) | nach 5–6 | `sg_ms_per_4k`≈683 @6 kB/s; `undDelta=0` |
| 8 | L3/L4 Negativ: knappes `maxMs` → Silence; knappes Host-Timeout → `botResets`, ESP ok | nach 7 | Fallback + Reset-Signal belegt |

Tools: `tools/lab_e7_delay_ladder.py` · Spec [`STALL-BUILD-SPEC-2026-10-08.md`](STALL-BUILD-SPEC-2026-10-08.md) · Method `technology-audit/methods/msc-busy-retry-semantics.md`.

### P1b — E7 NBT (erst nach PC-Grün)

9. Dieselbe Spur am BMW **nur als C** (`audits/pidrive-2026-bmw-hu/`): E7-A-Raster → Abort-Grenze; dann E7-B Live-Pacing.  
10. Stall-Feld-OTA **nur** mit explizitem Go und nach Q11-Klasse-A-Pfad.

### P2 — Host-Identity (parallel zum Lab, nicht vor E7)

11. Volume-Label von Serial entkoppelt testen (`lab_k3_volume_label.py`).  
12. Nicht mit K3-Dateiname vermischen; Ergebnis = Cache-Hypothese, nicht Tonlösung.

### P3 — Fallback (erst nach E7-Negativ)

13. PSRAM-Zeitversatz (≥512 KiB / Slot-Kette) spezifizieren.  
14. Q10-CDB-Sniffer nur bei Gesamtdauer-Limit-Verdacht.  
15. ASYNC (#2967) nur tracken, falls 0.15-Busy unter Last scheitert — Port hat ASYNC heute nicht.

### Entscheidungsgate

```text
E7-B PC FAIL  → Architektur BUSY verwerfen für Produktpfad; P3 PSRAM
E7-B PC PASS, NBT FAIL → BUSY bleibt Lab-Fakt; Produkt = PSRAM / anderer Host-Pfad
E7-B NBT PASS → Dauerstrom-Architektur = BUSY-Pacing; Ring/PSRAM nicht primär
```

### Nicht tun

- Architektur weiter diskutieren statt E7-A/B messen  
- Q10 als Hauptspur; Ring-FW als Dauerstrom-Lösung  
- Stall-Feld unter Klasse B / ohne Go  
- NBT-Timeout-ms als Sheet-**A**-FACT schreiben  
- Label als „Tonfix“; neues Gadget-Repo  
- Sofort 5 s Delay als Produktverhalten

---

## 5. Umsetzungsschnitt

| Lieferobjekt | Repo | Stand |
|--------------|------|-------|
| Dieses Dokument (Busy-GPT-Abgleich) | `pidrive` | ✅ aktualisiert |
| `tools/lab_e7_delay_ladder.py` | `pidrive` | ✅ |
| Stall-Config + `onReadLiveStall` | `esp32.pidrive` | ✅ Code; Lab `.88` geflasht `0.4.47-dev` |
| Volume-Label-Override | `esp32.pidrive` | ✅ Code |
| Desk-Audit Busy/Async | `technology-audit` | ✅ closed |
| E7-A/B Messläufe PC | Lab | ✅ L0/L1/L3/L4; L2 TEIL (siehe ERGEBNIS) |
| Busy-Timer-Fix 0.4.48 | `esp32.pidrive` | ✅ Lab `.88` |
| NBT E7 (C) | Feld | ⬜ nach Q11/Go — Prep: [`../betrieb/artifacts-2026-10-12-feld/feld-s6-prep/`](../betrieb/artifacts-2026-10-12-feld/feld-s6-prep/) |

**Nächster Operator-Befehl (Lab `.88`):**

```bash
# L0 / Config-Leiter (Stall an für A, nach L0 wieder aus wenn nötig)
python3 tools/lab_e7_delay_ladder.py --mode A --stall-ready --esp http://192.168.178.88

# mit SG-Host:
python3 tools/lab_e7_delay_ladder.py --mode A --stall-ready --esp http://192.168.178.88 --sg /dev/sgX
python3 tools/lab_e7_delay_ladder.py --mode B --stall-ready --esp http://192.168.178.88 --sg /dev/sgX --bps 6000
```

**Freeze:** Flash/OTA Stall nur mit Go. Auto weiter Freeze. Q11 bleibt eigene Spur.

**Noch offen in Stall-Code (nicht blockierend für L0/E7-A):** `underrunCursorHold` / `silenceMatchLive` unvollständig; `botResets`-Telemetrie fehlt ggf.; PSRAM unberührt.

---

## 6. Verweise

- Audit: `technology-audit/audits/tinyusb-msc-busy-retry-2026/`  
- Sheet A: `technologies/usb-msc/SHEET.md` · Method: `methods/msc-busy-retry-semantics.md`  
- Application B: `projects/esp32-pidrive/applications/usb-msc.md` · Host C: `audits/pidrive-2026-bmw-hu/`  
- [`STALL-BUILD-SPEC-2026-10-08.md`](STALL-BUILD-SPEC-2026-10-08.md)  
- [`HU-Technical-Facts.md`](../fahrzeug/HU-Technical-Facts.md) E7, Q10, R24–R27  
- Feld s5: [`../betrieb/artifacts-2026-10-08-feld/feld-s5-prep/s5-20261011-184623/ERGEBNIS-S5.md`](../betrieb/artifacts-2026-10-08-feld/feld-s5-prep/s5-20261011-184623/ERGEBNIS-S5.md)  
- Lab-Flash: [`../betrieb/artifacts-2026-10-12-lab/lab-e7-stall-flash/ERGEBNIS.md`](../betrieb/artifacts-2026-10-12-lab/lab-e7-stall-flash/ERGEBNIS.md)
