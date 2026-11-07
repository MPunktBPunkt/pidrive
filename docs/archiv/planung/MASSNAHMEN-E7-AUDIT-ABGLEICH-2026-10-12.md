# Maßnahmen — E7 / Audit-Abgleich · 2026-10-12

**Quellen:** GPT nach `technology-audit` Kampagne `tinyusb-msc-busy-retry-2026` (closed) · Sheet `usb-msc` Busy/Async · Method `msc-busy-retry-semantics` · Application B `esp32-pidrive/usb-msc` · PiDrive Stall-Spec · Feld s5 (11.10.)  
**Status:** kanonischer Arbeitsauftrag. **Kein** OTA-/Stall-Feld-Flash ohne explizites Go. Stall-Defaults bleiben `stallEnable=false` (= 0.4.46-Verhalten).

**Lab-Stand:** `.88` = **`0.4.48-dev`**, `stallEnable=false`.  
**Feld s6 (12.10.):** `.89` = **`0.4.48-dev`** (Go-OTA); E7-NBT **belegt** (~65 s Dauer bis EOF); Exit `stallEnable=false`.  
E7-PC: [`../betrieb/artifacts-2026-10-12-lab/lab-e7-ladder/ERGEBNIS.md`](../betrieb/artifacts-2026-10-12-lab/lab-e7-ladder/ERGEBNIS.md) · Feld: [`../betrieb/artifacts-2026-10-12-feld/feld-s6-prep/ERGEBNIS-S6.md`](../betrieb/artifacts-2026-10-12-feld/feld-s6-prep/ERGEBNIS-S6.md).

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
| PC/NBT toleriert lange BUSY-Zyklen? | **PC FACT** · **NBT FACT (C)** s6 ~65 s bis EOF |
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

### P3 — Nach E7-C (s6) — Endlos-Radio

**Kanonischer Auftrag:** [`../betrieb/artifacts-2026-10-12-feld/UEBERGABE-S6-NAECHSTE-KI-2026-10-12.md`](../betrieb/artifacts-2026-10-12-feld/UEBERGABE-S6-NAECHSTE-KI-2026-10-12.md)

13. **Hauptpfad D:** Fixed Huge Live File (feste Größe von Anfang an) + BUSY; **nicht** dynamisch FAT-Size wachsen.  
14. **S7 zuerst:** Startup-Usability / Stall nur aktiver Body nach Head-Play (20 s-Problem).  
15. **D0–D3 Leiter** 512 KiB→1→2→8 MiB inkl. **Resume-P-Test** oder Identitäts-Rotation.  
16. Slot-Kette **B** nur als Fallback; PSRAM-Burst-Primärpfad obsolet.  
17. Q10-CDB / ASYNC nur bei Bedarf.

### Entscheidungsgate (aktualisiert nach s6)

```text
E7-C NBT PASS (s6) → Busy-Pacing = Produktkern
  → D Fixed Huge File (+ Resume-Abwehr) zuerst
  → B Slot-Kette nur wenn D scheitert
  → PSRAM nicht gegen HU-Burst
```

### Nicht tun

- Dyn. Dateigröße unter laufendem Mount als Hauptpfad  
- Sofort 2 GiB ohne Offset-Zuordnung + Resume-Plan  
- Slot-Kette als *einzigen* nächsten Schritt  
- „FAT/DIR werden gebusyt“ als Code-FACT (trifft 0.4.48 nicht)  
- Stall-Feld ohne Go; NBT-ms als Sheet-A-FACT
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
| NBT E7 (C) | Feld | ✅ s6 — [`ERGEBNIS-S6`](../betrieb/artifacts-2026-10-12-feld/feld-s6-prep/ERGEBNIS-S6.md) |
| Übergabe nächste KI | `pidrive` | ✅ [`UEBERGABE-S6`](../betrieb/artifacts-2026-10-12-feld/UEBERGABE-S6-NAECHSTE-KI-2026-10-12.md) |
| S7-B `stallArmed` | `esp32.pidrive` **0.4.49-dev** | ✅ Lab `.88` Messungen grün; Feld-Go offen |
| `lab_s7_startup_poll.py` + [`S7-D-LEITER-SPEC`](S7-D-LEITER-SPEC-2026-10-12.md) | `pidrive` | ✅ |
| S7 stream-before-guess | Lab `.88` | ✅ [`lab-s7-stream-before-guess/ERGEBNIS`](../betrieb/artifacts-2026-10-12-lab/lab-s7-stream-before-guess/ERGEBNIS.md) |
| D0 E7-B L1 Regression | Lab `.88` | ✅ [`lab-d0-regression/ERGEBNIS`](../betrieb/artifacts-2026-10-12-lab/lab-d0-regression/ERGEBNIS.md) |

**Nächster Fokus:** Feld-Go 0.4.49 (S7+D0 Lab grün). D1–D3 / Resume-P später.

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
