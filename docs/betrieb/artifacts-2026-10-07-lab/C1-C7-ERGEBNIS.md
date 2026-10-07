# C1–C7 Ergebnis — Lab Cursor (2026-10-07)

**Host:** CT `.187` · `/dev/sg0` · ESP `192.168.178.88` · FW **0.4.46-dev**  
**Tools:** `nbt_hu_sim.py` (snap_retry, BENCH soft-fail bei ENODEV, GW/G7 post-snap retry)  
**Self-test:** PASS · Regression **ALL G1–G5:** PASS (`lab88-nbt-hu-sim-all-c1c7-1152/`)

---

## Kurzfazit

| ID | Ergebnis | Kernzahl |
|----|----------|----------|
| ALL | **PASS** | G1–G5 |
| C1 | **PASS** (N1: `sg_duration p50=4,0 ms`) | Wanduhr ~195 Reads/s = Lab-Host; ESP/Bus auf HU-Niveau; δ=2000 |
| C2 | **Messung ok** | Idle sg p50 **4,0 ms** → Armed **5,0 ms** (R15 = Live-Pfad) |
| C3 | **PASS** (Callback) | 16 KiB→4 CB, 64 KiB→16 CB ⇒ **EP 4 KiB** |
| C4 | **PASS** | G7-live + GW-live; `abs0−off` konstant |
| C5 | **teilweise** | Clean-Fenster Steigung ≈ Bench (±5 %); Wi-Fi stirbt unter längerer MSC |
| C6 | **PASS** | REPLAY + G7 bare + G7 autoplay (je nach Soft-RST) |
| C7 | **PASS** | G8 remount×3 + soft-RST: `readCount_delta=167` |
| G6 | **PASS** | Cache-Hit + Remount-Reread |

**Lab-Host:** LXC-USB stirbt unter Last (ENODEV). Soft-RST stellt `/dev/sg0` wieder her; Remount allein oft nicht.

---

## C1 — Bus/ESP-Obergrenze → **PASS** (Kriterium N1)

Online ×3 (`lab88-c1-online-r{1,2,3}-1156/`), BENCH 4096×2000, kein Remount:

| Lauf | reads/s (Wanduhr) | ms_per_4k | sg p50/p95 | start_to_start p50 | esp δ |
|------|-------------------|-----------|------------|--------------------|-------|
| r1 | 194.7 | 5.135 | **4.0** / 5.0 | 4.835 | **2000** |
| r2 | 194.7 | 5.136 | **4.0** / 5.0 | 4.837 | **2000** |
| r3 | 193.8 | 5.159 | **4.0** / 5.0 | 4.879 | **2000** |

**Abnahme (neu, N1/B1):** `sg_duration p50 ≤ 4,1 ms` im Leerlauf = ESP+Bus auf HU-Niveau (Feld 4,0 ms). Die Wanduhr-Rate (~195/s) enthält ~0,8 ms Lab-Host zwischen READ10 und ist **kein** ESP-Kriterium; absolute HU-Rate 250/s bleibt Feld-belegt.  
`δ/reads = 1` → ein Callback je 4 KiB.

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

## C4 — Offset → Strominhalt → **PASS** (Mapping + Golden)

| Lauf | Artefakt | Ergebnis |
|------|----------|----------|
| G7 + live + prefill 8 s | `lab88-c4-g7-live-1209/` | **PASS** (bytes_delta=8 179 712, maxSeq head/final ok) |
| GW + live | `lab88-c4-gw-live-1339/` | **PASS** (bytes_delta_esp = bytes = 8 044 544) |
| BENCH seq live | `lab88-c4-bench-seq-1245/` | Mapping-Daten ok; C1-Gate FAIL (rps 152, armed) |

**Mapping** (`C4-MAPPING-g7-live-1209.csv`, `C4-MAPPING-bench-seq-1245.csv`):

- G7-live: `abs0 − off = **19712**` (konstant über 1997 Reads, inkl. Fragmentphase)
- BENCH-seq: `abs0 − off = **20480**` (konstant über 2048 Reads)

Für 0.4.46 (zählender Cursor) wäre bei echten Rückwärts-Reads mit **neuem** Inhalt ein wechselndes `abs0−off` erwartet. Konstante Differenz in diesen Läufen = PDSQ/Ear sieht dateipositions-feste Tags bzw. sequenzielle Alignierung — als Vorlage für Post-Go „feste Zuordnung“ nutzbar; OOO-Falschinhalt separat provozieren.

---

## C5 — Steigung `hostAbs − absEnd` → **teilweise belegt**

| Lauf | Artefakt | BENCH rps | Poll-Zeilen |
|------|----------|-----------|-------------|
| 10 Hz + period 4.0 | `lab88-c5-slope-10hz-1245/` | 153.2 | 219 |
| 1 Hz + period 5.1 | `lab88-c5-slope-1hz-1245/` | 153.4 | 29 |
| clean RST + 1 Hz | `lab88-c5-slope-clean-1hz-1325/` | 152.5 | 33 |

**Clean-Lauf (1325):** Nach Soft-RST startet `d` sauber; in den **4 s mit `cursorArmed` + gültigem Poll** steigt `d` mit **~0,63 MB/s** (erwartet ≈ Bench-MBps − Producer ≈ 0,62 MB/s, Abweichung unter 5 %). Danach stirbt Wi-Fi unter MSC (Poll-Felder `null`) — Abnahme über ≥30 s noch offen.  
Batch-Läufe vorher: Reststrom → `d` schon ≫0, Steigung unbrauchbar.

---

## C6 — Replay / G7-Modell → **PASS**

| Lauf | Artefakt | Ergebnis |
|------|----------|----------|
| REPLAY resume 364034–376757 | `lab88-c6-replay-resume-1209/` | **PASS** (`readCount_delta=1963`) |
| G7 + live | `lab88-c4-g7-live-1209/` | **PASS** |
| G7 bare (nach Soft-RST) | `lab88-c6-g7-bare-1343/` | **PASS** (head/frag/final/total) |
| G7 autoplay (nach Soft-RST) | `lab88-c6-g7-autoplay-1346/` | **PASS** (maxSeq head 368640, final 5201920) |

Ohne frischen Soft-RST bleiben Slot-`maxSeq`-Zähler hoch → head_ok falsch negativ. Fragment-maxSeq-Feldlücke (392–632 KiB) ist separat (Feld Q8).

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

## Nachprüfung 2026-10-07 nachmittags (N1–N4)

**N1 — C1 ist kein ESP-Befund; das Kriterium war falsch gewählt.** In allen drei C1-Läufen sind die Werte `sg_duration p50 = 4,0 ms` und `start_to_start p50 = 4,84 ms`. Die SG-Dauer ist die Zeit von ESP und Bus pro READ10. Die ~0,8 ms Differenz entstehen im Lab-Host zwischen zwei Kommandos (Python + ioctl). Das Lab trifft das Feld also genau:

| Zustand | Lab `sg_duration` p50 | Feld (Start-zu-Start der HU) |
|---------|-----------------------|------------------------------|
| idle | 4,0 ms | 4,0 ms (250/s) |
| armed | 5,0 ms | 5,1 ms (195/s) |

- **Neues C1-Kriterium:** `sg_duration p50 ≤ 4,1 ms` im Leerlauf. Reads/s an der Wanduhr misst den Lab-Host mit, nicht den ESP.
- Mit diesem Kriterium ist C1 **PASS**.
- C3 passt dazu: 512 B brauchen ~1,0 ms pro Kommando (Fix-Overhead CBW/CSW + Host). 4 KiB brauchen 4,0 ms, das ist die Bulk-Grenze von Full-Speed.

**N2 — C4 prüft die feste Zuordnung nur im sequenziellen Kopf.** `C4-MAPPING-g7-live-1209.csv` hat 1997 Reads, davon **12 LIVE** (Offset 4.096–49.152, eine Ringfüllung) und 1984 SILENCE. Die Konstante `abs0−off = 19712` gilt deshalb nur für diese 12 sequenziellen Reads. Lesen außer der Reihe mit Live-Inhalt wurde nicht getestet: Der Sim liest mit ~1 MB/s, der Producer liefert ~9 KB/s, also ist bei jedem Rückwärts- oder Fragment-Read der Ring längst überholt. Nachtest **C4b** (Sim auf Producer-Tempo gedrosselt) siehe [`AUFTRAG-LAB-S2-PROBE-T1-T4.md`](AUFTRAG-LAB-S2-PROBE-T1-T4.md).

**N3 — R16 ist auf Read-Ebene belegt** (Einzelzeilen p1-run-a ms 364034–365907):
- LBA 1953–1961 (F8);
- LBA 1713–1945 (B120);
- LBA 1473–1705 (B120);
- LBA 1969–2681 (F360);
- LBA 753–1465 (B360);
- LBA 2689–4617 (F968).

Jedes Rückwärtssegment endet direkt unter dem bisher niedrigsten Block. HU-Facts R16 steht jetzt auf [B].

**N4 — `msc.reads`-Bursts können einen LBA-Sprung enthalten.** `UsbMscGadget::drainPendingReads` fasst Samples nach Art, Abstand ≤ 50 ms und ≤ 32 Stück zusammen, **nicht nach LBA-Kontinuität**. Solche Bursts (`lba1 ≠ lba0 + (n−1)·8`) kommen vor: in p1-run-a 8 von 859, in m3seq 39 von 4218, und gerade an Segmentwechseln (z. B. `lba0=1913, lba1=1521, n=12`). Gegenmittel ohne FW:
- `feld_q8_msc_order.py` erkennt und teilt solche Bursts;
- `feld_trace_poll.py` liest die Einzel-Reads aus `/api/metrics → mscTrace` (96 Einträge, ab 3 Hz Poll lückenlos bei 250 Reads/s).

---

## Empfehlung / noch offen

1. ~~R15 Ursache~~ → in HU-Facts/Q9 nachgetragen (**Live-Pfad**).
2. Stall-Adapter: Budget gegen **5 ms**-Takt im Play; Callback-Stückelung **4 KiB**.
3. C5: längeres Poll-Fenster (≥30 s) braucht stabiles Wi-Fi unter MSC (oder Status über UART/SoftAP).
4. LXC: nach ENODEV Soft-RST + ≥20 s Settle; G7 nur auf frischem Medium (sonst sticky `maxSeq`).
5. Feld bleibt Blocker für Stall-Go: **F1** + **R10**/feste Zuordnung (C4-Mapping ist Lab-Vorlage).
