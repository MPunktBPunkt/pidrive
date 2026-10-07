# C1–C7 Ergebnis — Lab Cursor (2026-10-07)

**HEAD-Tools:** lokal mit `--offline` für BENCH (Wi-Fi Lab-ESP `.88` down; USB MSC `/dev/sg0` = `PIDRIVE USB_MEDIA` ok)  
**FW:** 0.4.46-dev L3 (MSC antwortet) · **HTTP/Pump:** nicht erreichbar → C2/C4/C5/C6/C7/G1–G8 **blockiert**  
**Self-test:** PASS · `py_compile` PASS

---

## Blocker

| Check | Status |
|-------|--------|
| `/dev/sg0` SG_IO READ10 | ✅ |
| `http://192.168.178.88` | ❌ connection refused / not on LAN |
| Bridge / `msc.reads` / `audio_start` | ❌ braucht ESP-IP |
| Soft-RST / remount API | ❌ |

**Nächster Schritt Host:** Lab-ESP WLAN wieder online (Power-Cycle / AP), dann C2–C7 und `ALL`-Regression ohne `--offline`.

**Tool-Änderung:** `nbt_hu_sim.py --offline` — SG-only BENCH mit statischer L3-LBA-Map (fav0 81–16464). Kein Ersatz für Online-Läufe.

---

## C1 — ≥ 245 Reads/s? → **FAIL** (Lab langsamer als HU)

Kommando (3×):

```bash
sg disk -c 'python3 tools/nbt_hu_sim.py --golden BENCH --bench-sizes 4096 --bench-n 2000 --sg /dev/sg0 --offline --out …'
```

| Lauf | Artefakt | reads/s | ms_per_4k (wall) | sg_duration p50/p95 | start_to_start p50 |
|------|----------|---------|------------------|---------------------|--------------------|
| r1 | `lab88-c1-bench-4096-1124-r1/` | **204.1** | 4.90 | 4.0 / 5.0 | 4.74 |
| r2 | `lab88-c1-bench-4096-1124-r2/` | **204.8** | 4.88 | 4.0 / 5.0 | 4.71 |
| r3 | `lab88-c1-bench-4096-1124-r3/` | **204.9** | 4.88 | 4.0 / 5.0 | 4.73 |

**Abnahme ≥245:** nicht erreicht (~205 ≈ 82 % der HU-Grenze 250).

**Deutung:**
- Kernel/SG meldet **p50 = 4,0 ms** Transfer — Bus-nahe Grenze wie die HU.
- Host-seitig liegt **start-to-start p50 ≈ 4,7 ms** (~0,7 ms Userspace/Syscall zwischen READ10) → effektive Rate ~205 Reads/s.
- Sim-Zeiten mit `--period-ms 4.0` können die HU-Wallclock nicht 1:1 treffen, solange der Lab-Host nicht ≥245 erreicht. Relative Vergleiche (C2 Matrix, C5 Steigung) bleiben sinnvoll; absolute 8–10-s-Ramps für 8 MiB brauchen ~10 s hier statt ~8 s Feld.

`esp_readCount_delta`: null (offline).

---

## C3 — Größen-Sweep → **teilweise** (ohne ESP-Callback-Zähler)

Artefakt: `lab88-c3-sizesweep-1124/`

| READ10 size | reads/s | MBps | ms_per_4k | sg_duration p50 | Hinweis |
|-------------|---------|------|-----------|-----------------|---------|
| 512 | 1121.5 | 0.57 | 7.13 | 1.0 | hoher CBW/CSW-Overhead pro B |
| 4096 | 207.3 | 0.85 | 4.82 | 4.0 | wie C1 |
| 16384 | 54.6 | 0.89 | 4.58 | 16.0 | 16/4 = **4,0 ms je 4 KiB** |
| 65536 | 13.9 | 0.91 | 4.48 | 63.0 | 63/16 ≈ **3,9 ms je 4 KiB** |

**Auswertung (ohne ESP `readCount`, hypothetisch EP_BUFSIZE=4096):** Dauer skaliert linear mit Chunks zu 4 KiB → Callback-Granularität **vermutlich 4 KiB**. Bestätigung braucht Online-C3 (`esp_readCount_delta / reads`).

---

## C2, C4, C5, C6, C7 — **nicht gelaufen**

Grund: ESP-HTTP down. Keine Play-Phase, kein Producer, kein Remount, kein Replay-Abgleich mit Status.

---

## Empfehlung

1. **Lab-ESP WLAN** wiederherstellen; dann sofort:
   - `python3 tools/nbt_hu_sim.py --golden ALL --sg /dev/sg0` (Regression nach Tool-Änderungen)
   - C1 **online** (mit `esp_readCount_delta`) — erwarten weiter ~205 host-seitig, ESP-Delta ≈ 2000
   - C2-Matrix (Play vs Idle) für R15 / 5,1 ms
   - C3 online für Callback-Faktor
   - C4/C5/C6/C7 wie Auftrag
2. Bis dahin: Sim-Kalibrierung nur relativ; Feld-Ramps bleiben Referenz für absolute Zeiten.
3. Optional später: BENCH in C/Userspace-Batch oder O_DIRECT-Queue, um die 0,7 ms Lücke zu schließen (kein Stall-Blocker).

---

## Artefakte

```
docs/betrieb/artifacts-2026-10-07-lab/
  C1-C7-ERGEBNIS.md          ← dieser Bericht
  lab88-c1-bench-4096-1124-r{1,2,3}/
  lab88-c3-sizesweep-1124/
```

Je Ordner: `REPORT.json`, `bench.json`, `reads.jsonl`, `RUN.log`.
