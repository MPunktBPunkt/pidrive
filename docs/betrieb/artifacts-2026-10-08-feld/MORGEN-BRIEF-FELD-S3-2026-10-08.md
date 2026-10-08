# Morgen-Brief — Feld s3 im Auto · 2026-10-08

**Ziel:** P-/Resume-Bindung der HU eingrenzen · **FW-Freeze 0.4.46** · kein Stall-OTA · kein Stick/Hub  
**Packen:** Pi · Handy · ESP-Kabel · PD0089  
**Pocket:** [`feld-s3-prep/GO.md`](feld-s3-prep/GO.md) · Volltext: [`FELDPROTOKOLL-P-QUELLE-ESP.md`](FELDPROTOKOLL-P-QUELLE-ESP.md)

**Repos:** `pidrive` `d2e128a` · `esp32.pidrive` `698e607`  
**Review:** Mistral-Brief + unabhängige Präzisierungen (Zahlen gegen Roh-REPORT.json verifiziert).

---

## 1. Lab-Stand (nicht nochmal im Auto beweisen)

„Grün“ gilt **nur** bis SoftAP-Stream: Pi → `pump_bridge` → TCP → ESP → Ring → MPEG.  
**Nicht** bis HU / Decoder / Lautsprecher.

| Bereich | Status |
|---------|--------|
| Pump Burst / Feldrate / 120‑s-Soak | PASS |
| TCP-Bridge, HTTPS-Rock, lokale MP3 (nach Fix), Marker, BOB-Switch | PASS |
| BMW HU Audio / P-Bindung | OFFEN — heutiger Test |
| Stall / Stall-OTA | FREEZE |

Messwert behalten: Rock 48k Bridge ~**6 795 B/s** bei Ziel 9 000 (−24 %, underruns 0, Ring stabil). 96k ~17 303 bei Ziel 18 000.

Details:  
[`../artifacts-2026-10-08-lab/lab88-pump-calib-night/GESAMTBERICHT-PUMP-CALIB-NIGHT.md`](../artifacts-2026-10-08-lab/lab88-pump-calib-night/GESAMTBERICHT-PUMP-CALIB-NIGHT.md) ·  
[`../artifacts-2026-10-08-lab/lab88-pump-calib-morning/GESAMTBERICHT-PUMP-CALIB-MORNING.md`](../artifacts-2026-10-08-lab/lab88-pump-calib-morning/GESAMTBERICHT-PUMP-CALIB-MORNING.md)

---

## 2. Heute: nur P — Priorität C > A > B

`run-s3` nutzt Bridge **`--no-audio`** (Capture wie s2). Bridge-Fix `698e607` ist für diesen Lauf nicht kritisch, trotzdem auf dem Feld-Pi mitziehen.

| Prio | Phase | Aktion | Fragt |
|------|-------|--------|-------|
| ★1 | **C** | Rock 40 s → Kabel ab 5 s → rein → Index → Serial? → Rock 35 s | P überlebt Remount / Serial-Wechsel? |
| 2 | **A** | Rock 40 s → Soft-RST → Rock 35 s | P überlebt Soft-RST? |
| 3 | **B** | Rock 40 s → BOB 10 s → Rock 35 s | P überlebt Abwahl? |

**Zeitnot:** nur **C**, dann A. B opfern.

**Orakel (Messung):** Resume = Start≠0 / `r16_resume_like` · Kopf = Start bei 0 / `head_like`

**Orakel (Deutung — vorsichtig):** Resume beweist nur, dass die HU P nach dem Ereignis **wiederherstellen kann** — nicht den exakten Schlüssel (Serial, Track-ID, Name, Pfad, Größe, Volume-ID, DB-Eintrag oder Kombination). C verkleinert den Suchraum stark; kein Architektur-Schluss aus einem einzelnen C-Resume. **P ≠ Stall.**

---

## 3. Vor Abfahrt

```bash
# Feld-Pi
cd ~/projects/pidrive && git pull   # → d2e128a (+ ggf. neuer Prep-Commit)
chmod +x docs/betrieb/artifacts-2026-10-08-feld/feld-s3-prep/*.sh
# Bridge-Fix einspielen (empfohlen; s3 selbst ist --no-audio):
sudo cp /home/martin/projects/esphub/esp32.pidrive/tools/pump_bridge.py /home/pidrive/pump_bridge.py
# oder: git -C …/esp32.pidrive pull && cp …/tools/pump_bridge.py /home/pidrive/
curl -s -m 3 http://192.168.178.89/api/metrics | head -c 120; echo
```

- [ ] HEAD `d2e128a`+ · Working Tree sauber genug für Capture  
- [ ] `/home/pidrive/pump_bridge.py` vorhanden (idealerweise `698e607`)  
- [ ] ESP `.89` antwortet · FW Freeze 0.4.46 · **kein** OTA  
- [ ] Packen: Pi · Handy · ESP-Kabel · PD0089 — kein Stick, kein Hub  

Am Auto: Video + HU + Uhr; Serial vor/nach C laut sagen.
