# Maßnahmen — E7 / Audit-Abgleich · 2026-10-12

**Quellen:** GPT+Mistral nach `technology-audit@c052046` · PiDrive `b61df4d` (+ lokale Artefakte s5 11.10.) · Code `esp32.pidrive`  
**Status:** kanonischer Arbeitsauftrag. **Kein** OTA-/Stall-Feld-Flash ohne explizites Go. Stall-Defaults bleiben `stallEnable=false` (= 0.4.46-Verhalten).

---

## 1. Gesamturteil

Das 8‑s-Fenster ist mengenmäßig erklärt (Producer 6 KB/s vs. HU ~800 KB/s, Ring 48 KiB). Q10 als *Callback*-Frage ist erledigt (4 KiB FACT). Offene Dauerstrom-Frage: **E7** (Busy-Retry/`return 0`) vs. **PSRAM-Zeitversatz**. USB-Bandbreite und „Ring größer = Dauerstrom“ sind REJECTED.

**Korrektur zu „direkt E7 im Auto“:** Feld s5 (11.10.) → Versorgung/Reset unter Last blockiert Ohr@32k. **Q11/Steckfestigkeit vor Stall-Feld.** Lab-E7 parallel erlaubt.

---

## 2. Audit-Nachschärfung (weitere Klärungen)

| Frage | Vorher | Nach Abgleich | Epistemic |
|-------|--------|---------------|-----------|
| Callback-Größe | oft mit READ10 vermischt | 4096 B Callback FACT; CDB-Länge UNKNOWN/[S] | FACT / UNKNOWN |
| Delay-Leiter | generisch | Method `msc-lba-timing-instrument`; an PiDrive-Callback + Live-Pacing koppeln | Method |
| Volume Label als Cache-Schlüssel | Hypothese | Sheet: Label ändern ist **nicht** kosmetisch für viele Hosts; Community (iDrive 8.5) meldet Label allein **unzureichend** (Disk-ID) | HYPOTHESIS — **muss auf NBT Evo gemessen werden** |
| Label vs. Serial bei PiDrive | F6 vermengt | **Code-Fakt:** USB-Serial **und** FAT-Volume-Label hängen beide an `remountGen_` (`PD%04u`). Isolierter Label-Test ist **heute unmöglich** ohne Entkopplung | FACT (Code) |
| FAT32 vs. Lab FAT12/16 | — | Audit: FAT32 oft „zuverlässiger“ berichtet — Gate, nicht still wechseln | HYPOTHESIS |
| „Reading data“ bei langsamen Sticks | — | passt zur E7-Latenz-These, beweist keine NBT-Toleranz | HYPOTHESIS |
| NBT MediaStore | Serial/Label | Dump-Literatur: `media.db`/`sync.db` + Geräte-Metadaten; Mount-Skripte teils ohne UUID — P-Schlüssel weiter empirisch | INFERRED (fremd) |

**Erledigt / nicht weiter als Haupttpur:** Q10 Callback-Größe ermitteln; USB-Bandbreite; Ring-Vergrößerung als Dauerstrom-Lösung.

**Bleibt offen und priorisiert:** E7-Toleranz; Volume-Label isoliert; Q11 UART; Ohr@32k A/B; PSRAM-Plan-B; exakte READ10-CDB nur wenn E7 an Gesamtdauer scheitert.

---

## 3. Modell (verbindlich)

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

## 4. Maßnahmen

### P0 — Feldblocker (ohne Stall-FW)

1. UART ohne DTR/RTS → `rst:` / Brownout vs. Soft-Reset (Q11).  
2. Stecklast: Bridge/WLAN erst nach stabilem OTG; Tip nur bei `playingUid`/`absEnd>0`.  
3. Ohr@32k A/B nachholen (s5-Diskriminator), sobald Klasse A trägt.

### P1 — E7 Lab (Umsetzung gestartet)

4. Delay-Leiter an 4‑KiB-Callback: Tool `tools/lab_e7_delay_ladder.py` (Stufe A Host-Timeout / Stufe B Live-Pacing-Protokoll).  
5. Stall-Build laut [`STALL-BUILD-SPEC-2026-10-08.md`](STALL-BUILD-SPEC-2026-10-08.md) in `esp32.pidrive`: Defaults aus, Laufzeit-Stellschrauben, Telemetrie.  
6. Lab-Leiter L0–L5 gegen Lab-ESP/.88 + `nbt_hu_sim --golden REPLUG` — **erst nach Build, vor Auto**.

### P2 — Host-Identity (parallel)

7. **Volume-Label von Serial entkoppeln** (Config/API), dann Lab-/Feld-Test: Label wechseln bei konstanter Serial und umgekehrt.  
8. Nicht mit K3-Dateiname vermischen; Ergebnis = Cache-/P-Hypothese, nicht Tonlösung.

### P3 — Fallback spezifizieren

9. PSRAM-Zeitversatz (≥512 KiB / Slot-Kette) erst nach E7-Negativ spezifizieren.  
10. Q10-CDB-Sniffer nur bei Gesamtdauer-Limit-Verdacht.

### Nicht tun

- Q10 als Hauptspur; Ring-FW als Lösung; Stall-Feld unter Klasse B; Label als „Tonfix“.

---

## 5. Umsetzungsschnitt (2026-10-12 — erledigt im Arbeitsbaum)

| Lieferobjekt | Repo | Ziel | Stand |
|--------------|------|------|-------|
| Dieses Dokument | `pidrive` | kanonischer Auftrag | ✅ |
| `tools/lab_e7_delay_ladder.py` | `pidrive` | Leiter A/B + Report | ✅ |
| Stall-Config + onRead Busy-Retry | `esp32.pidrive` | Spec, `stallEnable=false` | ✅ Code (noch unflash’t) |
| Volume-Label-Override + `keepIdentity` Remount | `esp32.pidrive` | Isolierung für P2 | ✅ Code |

**Nächster Schritt:** Lab-ESP bauen/flashen (Operator-Go), dann  
`python3 tools/lab_e7_delay_ladder.py --mode A --stall-ready --esp …` und Stufe B mit `--sg`.

**Freeze:** Flash/OTA Stall nur mit Go. Lab-Flash mit Defaults aus ist erlaubt, wenn Operator Go für *Build-Test* gibt; Auto weiter Freeze.

**Noch offen in Stall-Code (nicht blockierend für L0):** `underrunCursorHold` / `silenceMatchLive` noch nicht voll verdrahtet; `botResets`-Telemetrie fehlt; PSRAM-Pfad unberührt.

---

## 6. Verweise

- [`STALL-BUILD-SPEC-2026-10-08.md`](STALL-BUILD-SPEC-2026-10-08.md)  
- [`Stufenplan.md`](Stufenplan.md) Optionen a–d  
- [`HU-Technical-Facts.md`](../fahrzeug/HU-Technical-Facts.md) E7, Q10, R24–R27  
- Feld s5: [`../betrieb/artifacts-2026-10-08-feld/feld-s5-prep/s5-20261011-184623/ERGEBNIS-S5.md`](../betrieb/artifacts-2026-10-08-feld/feld-s5-prep/s5-20261011-184623/ERGEBNIS-S5.md)  
- Audit: `technology-audit` methods `msc-lba-timing-instrument`, sheets `bmw-nbt-evo`, `virtual-fat`, audit `esp32-msc-gadget-refs-2026-foreign`
