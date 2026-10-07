# C1–C7 Ergebnis — Lab Cursor (2026-10-07)

**Host:** CT `.187` · `/dev/sg0` · ESP `192.168.178.88` · FW **0.4.46-dev**  
**Tools:** `nbt_hu_sim.py` (snap_retry, BENCH soft-fail bei ENODEV, GW/G7 post-snap retry)  
**Self-test:** PASS · Regression **ALL G1–G5:** PASS (`lab88-nbt-hu-sim-all-c1c7-1152/`)

---

## Kurzfazit

| ID | Ergebnis | Kernzahl |
|----|----------|----------|
| ALL | **PASS** | G1–G5 |
| C1 | **FAIL** (Abnahme ≥245) | ~194–195 Reads/s online; `esp_readCount_delta=2000` |
| C2 | **Messung ok** | Idle sg p50 **4,0 ms** → Armed **5,0 ms** (R15 = Live-Pfad) |
| C3 | **PASS** (Callback) | 16 KiB→4 CB, 64 KiB→16 CB ⇒ **EP 4 KiB** |
| C4 | **teilweise** | G7-live PASS; `abs0−off` konstant; GW flaky (ENODEV/Wi-Fi) |
| C5 | **Daten da** | Poll 10/1 Hz; Steigung nicht ±5 % sauber (Reststrom/Poll-Last) |
| C6 | **teilweise** | REPLAY PASS; G7-live PASS; bare/autoplay flaky |
| C7 | **PASS** | G8 remount×3 + soft-RST: `readCount_delta=167` |
| G6 | **PASS** | Cache-Hit + Remount-Reread |

**Lab-Host:** LXC-USB stirbt unter Last (ENODEV). Soft-RST stellt `/dev/sg0` wieder her; Remount allein oft nicht.

---

## C1 — ≥ 245 Reads/s? → **FAIL**

Online ×3 (`lab88-c1-online-r{1,2,3}-1156/`), BENCH 4096×2000, kein Remount:

| Lauf | reads/s | ms_per_4k | sg p50/p95 | start_to_start p50 | esp δ |
|------|---------|-----------|------------|--------------------|-------|
| r1 | **194.7** | 5.135 | 4.0 / 5.0 | 4.835 | **2000** |
| r2 | **194.7** | 5.136 | 4.0 / 5.0 | 4.837 | **2000** |
| r3 | **193.8** | 5.159 | 4.0 / 5.0 | 4.879 | **2000** |

Offline-Referenz (vormittag): ~205 Reads/s. Online etwas langsamer (Status-Snaps).  
**1×4 KiB Callback** bestätigt (`δ/reads = 1`). Abnahme ≥245 weiterhin Lab-Host-Limit.

---

## C2 — 5,1 ms Herkunft → **Live-Pfad (ESP)**

Matrix stamp `1209`, je 2× BENCH 4096×2000, Poll/Bridge aus:

| Zustand | rps (Mittel) | ms_per_4k | sg_duration p50 | start_to_start p50 |
|---------|--------------|-----------|-----------------|---------------------|
| idle | 194.8 | 5.13 | **4.0** | 4.83 |
| armed (`audio_start`, kein Producer) | 160.2 | 6.24 | **5.0** | 5.82 |
| armed + Producer | 152.9 | 6.54 | **5.0** | 6.00 |

**Deutung:** Der Sprung sitzt in der **SG-Servicezeit** (4→5 ms), sobald `playingUid` gesetzt ist — nicht am Poll/Bridge. Producer kostet zusätzlich ~0,3 ms wall / ~8 Reads/s. Passt zu Feld-R15; Stall-Adapter bekommt im Play-Zustand weniger Budget.

---

## C3 — Callback-Granularität → **4 KiB**

Je Größe separat (`lab88-c3-sz*-1245/`), 500 Reads — kombinierter Sweep killt USB mitten im 16-KiB-Block:

| READ10 | reads/s | MBps | ms_per_4k | esp δ | **δ/reads** |
|--------|---------|------|-----------|-------|-------------|
| 512 | 998.1 | 0.51 | 8.02 | 500 | **1** |
| 4096 | 194.6 | 0.80 | 5.14 | 500 | **1** |
| 16384 | 52.2 | 0.86 | 4.79 | 2000 | **4** |
| 65536 | 13.0 | 0.86 | 4.79 | 8000 | **16** |

⇒ `CFG_TUD_MSC_EP_BUFSIZE = 4096`. Stall-Adapter kann höchstens in 4-KiB-Scheiben antworten.

---

## C4 — Offset → Strominhalt → **teilweise**

| Lauf | Artefakt | Ergebnis |
|------|----------|----------|
| G7 + live + prefill 8 s | `lab88-c4-g7-live-1209/` | **PASS** (bytes_delta=8 179 712, maxSeq head/final ok) |
| GW + live | `lab88-c4-gw-live-1209/1245` | Timeout / ENODEV |
| BENCH seq live | `lab88-c4-bench-seq-1245/` | Daten ok; C1-Gate FAIL (rps 152, armed) |

**Mapping** (`C4-MAPPING-g7-live-1209.csv`, `C4-MAPPING-bench-seq-1245.csv`):

- G7-live: `abs0 − off = **19712**` (konstant über 1997 Reads, inkl. Fragmentphase)
- BENCH-seq: `abs0 − off = **20480**` (konstant über 2048 Reads)

Für 0.4.46 (zählender Cursor) wäre bei echten Rückwärts-Reads mit **neuem** Inhalt ein wechselndes `abs0−off` erwartet. Konstante Differenz in diesen Läufen = PDSQ/Ear sieht dateipositions-feste Tags bzw. sequenzielle Alignierung — als Vorlage für Post-Go „feste Zuordnung“ nutzbar; OOO-Falschinhalt separat provozieren.

---

## C5 — Steigung `hostAbs − absEnd` → **Daten, Steigung unsauber**

| Lauf | Artefakt | BENCH rps | Poll-Zeilen |
|------|----------|-----------|-------------|
| 10 Hz + period 4.0 | `lab88-c5-slope-10hz-1245/` | 153.2 | 219 |
| 1 Hz + period 5.1 | `lab88-c5-slope-1hz-1245/` | 153.4 | 29 |

Während `cursorArmed`: `hostAbs`, `absEnd`, `underruns` bewegen sich; `d = hostAbs−absEnd` startet bereits ≫0 (Reststrom nach Vorläufen). Armed-Regression ~**−0,20 MB/s** (d sinkt), nicht die erwarteten +0,8–1,0 MB/s auf sauberem Reset.  
**Nächster C5:** Soft-RST → nur C5, kein Batch davor; optional Poll 1 Hz (C2: 10 Hz bremst wie Armed).

---

## C6 — Replay / G7-Modell → **teilweise**

| Lauf | Artefakt | Ergebnis |
|------|----------|----------|
| REPLAY resume 364034–376757 | `lab88-c6-replay-resume-1209/` | **PASS** (`readCount_delta=1963`) |
| G7 (ohne live, im C4-Kontext live) | `lab88-c4-g7-live-1209/` | **PASS** Modellzahlen |
| G7 bare | `lab88-c6-g7-1209/1245` | ENODEV / Timeout nach MSC |
| G7 autoplay | `lab88-c6-g7-autoplay-1245/` | **FAIL** (`maxSeq_after_head=8388608` statt 368640) |

Bekannte Feld/Modell-Lücke (Fragment-maxSeq) bleibt; Autoplay-Zähler im Lab nicht stabil.

---

## C7 — G8 Remount / Soft-RST → **PASS**

| Lauf | readCount δ | fav0_bytes δ | current_maxSeq | fav0_maxSeq |
|------|-------------|--------------|----------------|------------|
| remount r1–r3 | **167** | **32768** | **524288** | 7049216 (kumuliert) |
| soft-RST | **167** | **32768** | **524288** | 188416 |

`rc_ok` / `probes_ok` / `current_ok` alle true. Feld-Soll `fav0_maxSeq=4096` nach frischem Medium — Lab-Slots tragen Historie; Signatur **rc=167** und 32 KiB fav0-Probes erfüllt.  
Serial: Snap ohne `usbSerial`-Feld; Uptime-Sprung nur bei soft-RST sichtbar (Remount ohne ESP-Reboot).

---

## G6 — **PASS**

`lab88-g6-rehearsal-1209/` — Sim-Cache-Hit + Remount-Reread ok.

---

## Tool-Änderungen (heute)

- `--offline` BENCH + L3-Slotmap (Vormittag)
- `snap_retry` / BENCH ohne Remount-Sturm
- BENCH: ENODEV → ein Reopen, sonst soft-incomplete statt Traceback
- GW/G7: `snap_retry` + Pause vor Post-Snap (Wi-Fi unter MSC)

---

## Artefakte

```
docs/betrieb/artifacts-2026-10-07-lab/
  C1-C7-ERGEBNIS.md
  C4-MAPPING-g7-live-1209.csv
  C4-MAPPING-bench-seq-1245.csv
  lab88-nbt-hu-sim-all-c1c7-1152/          # ALL PASS
  lab88-c1-online-r{1,2,3}-1156/
  lab88-c2-{idle,armed,armedprod}-r{1,2}-1209/
  lab88-c3-sz{512,4096,16384,65536}-1245/
  lab88-c4-g7-live-1209/  lab88-c4-bench-seq-1245/
  lab88-c5-slope-{10hz,1hz}-1245/
  lab88-c6-replay-resume-1209/  lab88-c6-g7-autoplay-1245/
  lab88-c7-g8-remount-r{1,2,3}-1209/  lab88-c7-g8-softrst-1209/
  lab88-g6-rehearsal-1209/
```

---

## Empfehlung

1. R15 in HU-Facts: **Armed/Play kostet +1 ms SG** (Lab belegt).
2. Stall-Adapter: Budget gegen **5 ms**-Takt im Play-Zustand; Callback-Stückelung **4 KiB**.
3. C5 einmal isoliert nach Soft-RST wiederholen für Steigungs-Abnahme.
4. LXC: nach ENODEV immer Soft-RST (nicht nur Remount).
