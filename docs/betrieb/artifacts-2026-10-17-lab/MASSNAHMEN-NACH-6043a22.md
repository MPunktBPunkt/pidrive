# Maßnahmen nach Commit `6043a22` · 2026-10-17

**Auslöser:** Gesamturteil Lab-Nacht + Feld/hu-probe/Matrix (Review verdichtet, Messdaten getrennt von Schlussfolgerungen).  
**HEAD-Bezug:** `6043a22` und Nachfolger dieses Maßnahmen-Commits.

## 0. Ein Satz

Transport/Phasen (Menü→ID3→Audio) und Messmethode (SG_IO vs. Page-Cache) sind grün genug, um **Stall als HU-Messinstrument** im Lab zu fahren — P0-Feldblocker bleibt physischer OTG-Panic.

## 1. Verbindliche Methodik

| Regel | Inhalt |
|-------|--------|
| MSC-Wahrheit | ESP MessCapture / `bytesRead` / `op=40` — **nicht** „Host hat Bytes gesehen“ |
| Lab-Host-READ | nur **SG_IO** (`tools/sgio_read10.py`) oder O_DIRECT |
| Verboten als Beweis | `read()`/`dd` auf `/dev/sda` ohne ESP-Korrelation (Page-Cache-Falle, ID3-Kette) |
| Soft-Cycle | `stallEnable=false` (Freeze-Gate) |
| Stall-Leiter | Vorhersage-JSON **vor** jeder Stufe |

## 2. Maßnahmen (umsetzen / Status)

| ID | Maßnahme | Prio | Status | Artefakt / Tool |
|----|----------|------|--------|-----------------|
| M1 | `sgio_read10.py` als kanonisches Lab-Tool | P0 | ☑ | `tools/sgio_read10.py` |
| M2 | Q10 einmal kalibrieren (req blocks ↔ ESP) | P0 | ☑ **PASS** `q10-calib-01` all_match | `tools/lab_q10_calibrate.py` |
| M3 | Lab-Stall-Leiter Menü→ID3→Audio (0…15 s) | P0 | ☑ Tool + Smoke `stall-ladder-smoke-01`; Full 0…15 s noch offen | `tools/lab_stall_phase_ladder.py` |
| M4 | QD=1-Probe (240er offen halten) | P0 | in M3 Phase `audio` | Capture: zweite LBA während BUSY? |
| M5 | Overnight-Loop als **Smoke** markieren (n=1) | P0 Doku | ☑ | `overnight-loop-…/SMOKE.md` |
| M6 | Matrix: A3 Ursache nur Inference; ID3 Lab-Fakt; Methodik | P0 Doku | ☑ | `HU-PARAMETER-MATRIX-2026-10-16.md` |
| M7 | B4: Lab-`pread` 64er **nicht** als HU-Geometrie | P0 Doku | ☑ | diese Datei §3 |
| M8 | Panic/OTG UART+resetReason+VBUS A/B | P0 Feld | ☐ braucht Fahrzeug | Checkliste unten |
| M9 | F0 Identity/Cache isoliert | P1 | ☐ nach M8 | Serial / Vol-ID / Label |
| M10 | 128 kbit/s Gegenprobe | P1 | ☐ nach M8 | CBW-Dauer ~7,7 s |
| M11 | Größenleiter 256→… | P2 | ☐ | erst nach Transport+Cache |
| M12 | Root = Ordner Favoriten/Menue; Live unter Favoriten | P0 UX | ☑ FW `0.4.53-dev` Lab | `favoriten-layout-01/` |

## 3. Claims (Arbeitsstand)

| Claim | Bewertung |
|-------|-----------|
| Max READ10 = 240 / 120 KiB | **[S]** |
| 512‑KiB = `240,240,32,240,240,32` | **[S]** A7 — keine Wiederholung nötig |
| Lab-64er bei `pread` 64 KiB | **kein HU-Fakt** (Host/Blocklayer; B4 offen) |
| ID3 sticky 3200 B + PDSQ@3204 (Lab SG_IO) | **[B]** Lab |
| Page-Cache vs. echter MSC | **[B]** |
| 120 KiB @48 kbit/s ≈ 20,5 s | **Rechnung [B]**; „deshalb Menü-Freeze 20 s“ = **Inference** → Stall-Leiter |
| Timeout pro READ10 ≥20 s | **[A]** — direkt messen |
| E7 kumuliert ~65 s BUSY | **[B]**; ≠ einzelnes READ10 darf 65 s |
| OTG-Panic P0 | **[S]** Testfähigkeit |

## 4. Lab-Stall-Leiter (Soll)

Stufen: `0, 1000, 2000, 5000, 10000, 15000` ms (FW-Limit 15 s).

| Phase | Ziel | Frage |
|-------|------|-------|
| menu | LBA≈0 Meta | Wie lange Meta-BUSY ohne BOT-Reset / sichtbare Blockade? |
| id3 | fav0 Kopf | ID3 verzögert — HU-Reaktion? |
| audio | 240 Blöcke Body | QD=1? Timeout? Retries? HTTP/WLAN alive? |

Je Stufe loggen: retries, waitMs*, timeouts, botResets, Δbytes, host wall_ms, play, underruns, freeHeap.

## 5. Feld P0 — Panic-Checkliste (noch offen)

1. UART an Feld-ESP während physischem OTG  
2. `resetReason` / Panic-Tail / `sys.resetCount`  
3. Netzteil A/B, VBUS-Strom Min/Max  
4. Entscheidung: Stack/USB vs. Power/Brownout  
5. Erst dann Stall-Leiter **am NBT** (sonst HU ⊕ ESP vermischt)

## 6. Explizit nicht tun

- Weitere reine 512‑KiB-Wiederholungen (A7 genug)  
- 64er-Lab-READs ins HU-Modell  
- Ring blind vergrößern  
- F0 aus Soft-Cycle-Lab als BMW-Beweis  
- `dd`/`read()` als MSC-Wahrheit  

## 7. Nächster konkreter Lab-Schritt

```bash
# Q10
python3 tools/lab_q10_calibrate.py \
  --esp http://192.168.178.88 -o docs/betrieb/artifacts-2026-10-17-lab/q10-calib-01

# Stall-Smoke (kurz), dann volle Leiter
python3 tools/lab_stall_phase_ladder.py \
  --phases menu,id3,audio --ms 0,1000,2000 \
  -o docs/betrieb/artifacts-2026-10-17-lab/stall-ladder-smoke-01

python3 tools/lab_stall_phase_ladder.py \
  -o docs/betrieb/artifacts-2026-10-17-lab/stall-ladder-full-01
```
