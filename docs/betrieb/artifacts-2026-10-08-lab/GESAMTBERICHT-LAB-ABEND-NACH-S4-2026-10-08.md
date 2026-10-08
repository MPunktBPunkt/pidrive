# Gesamtbericht Lab-Abend nach Feld s4 · 2026-10-08

**ESP Lab:** `.88` · FW **0.4.46-dev** (Freeze, kein OTA)  
**Kontext:** Nach Feld-s4 (Tonfenster ~5–6 s Ohr / 8,26 s Instrument) Lab fortgesetzt und Feld-s5 vorbereitet.

---

## 1. Ein Satz

Ohne Firmware-Flash lässt sich das Ringfenster über Bridge-Bitrate verlängern (32k≈12,6 s, 24k≈16,8 s), Klasse-A-Remount rebootet den Lab-ESP nicht, K3-Rename ist auf der FAT sichtbar — der nächste Blocker sitzt im Auto (Q11 Reset + Ohr @32k).

---

## 2. Was gesichert ist

| Thema | Ergebnis | Beleg |
|-------|----------|--------|
| Ring @48k | ~8,3–8,4 s live_bytes, identity_ok | L4e 5/5, REPLUG Head |
| Bitrate 32k | **12,5–12,6 s** @4000 B/s, 3/3 + Regression | `lab-fenster-32k-1917`, fortsetzung-2005/2035 |
| Bitrate 24k | **16,7–16,8 s** @3000 B/s, 3/3 | `lab-fenster-24k-1919`, fortsetzung-2022 |
| Q10 READ10 | **4 KiB** (128×), Kopf-Pause Sim ~19 ms | `lab_q10_read_sniff.py` |
| Klasse A Remount | ×5 Serial↑, **0** Soft-Resets | fortsetzung-1940 |
| Physisches OTG ohne weiße LED | passt zu Uptime-Stunden ohne `boot` | Operator + Status |
| Mid-File | `not_from_head` / `plug_window` | fortsetzung-2005/2035 |
| Head-from-0 nach Prefill | REPLUG PASS | durchgängig |
| K3 Name-Override | API + **FAT** `Radio BOB LAB 1008.mp3` | fortsetzung-2022 |
| K3 Restore | wieder `Radio BOB!.mp3` (Bridge-Neustart + Remount) | fat-restored-final |
| `authorized`/VBUS | RO im PVE-CT | L4f |
| UART Q11 im Lab | **kein** Seriellgerät | fortsetzung-2022 |

**Metrik:** `live_s_at_48k` immer 6000 B/s; echte Hördauer bei anderer Bitrate = `live_s_at_bps` (`--replug-bps`).

---

## 3. Neue Werkzeuge

| Tool | Zweck |
|------|--------|
| `tools/lab_q10_read_sniff.py` | READ10-Histogramm + Kopf-Pause aus `reads.jsonl` |
| `tools/lab_fenster_bitrate.py` | Prefill→REPLUG-Leiter (24/32/48k) |
| `tools/lab_fat_list.py` | FAT12 `STATIONS/`-Namen vom Medium |
| `nbt_hu_sim` | `live_s_at_bps` / `--replug-bps` |

---

## 4. Feld-Prep s5

Angelegt unter `docs/betrieb/artifacts-2026-10-08-feld/feld-s5-prep/`:

- Default Bridge **32k / 4000 B/s / marker / msc-lock**
- Pocket `GO.md`: Q11 → O2 Ohr → K2 Bayern → K3 Rename → K5 Reboots  
- Protokoll: `FELDPROTOKOLL-S5-FENSTER-Q11.md`

---

## 5. Was bewusst offen bleibt

| Offen | Warum nicht Lab |
|-------|-----------------|
| Q11 `rst:`/Brownout | UART fehlt im CT; Auto + Adapter |
| Ohr @32k an der HU | nur Feld |
| P-Schlüssel **Größe** | Slot-Größe nicht per menu_set |
| Host-USB-Sniffer HU | Lab nur Sim-4 KiB |
| Stall / größerer Ring | Freeze, Spec only |

---

## 6. Artefakt-Index (Abend)

| Ordner | Inhalt |
|--------|--------|
| `lab-fenster-32k-1917` / `24k-1919` | Bitrate-Leiter Einzelmessung |
| `lab-abend-fortsetzung-1940` | Q10, Klasse-A Remount, REPLUG |
| `lab-abend-fortsetzung-2005` | K3 API, Mid/Head, 32k×3 |
| `lab-abend-fortsetzung-2022` | K3 FAT, 24k×3, UART-Probe |
| `lab-abend-fortsetzung-2035` | Regression vor s5 |
| `feld-s5-prep/` | nächster Feldlauf |

---

## 7. Empfehlung

1. `feld-s5-prep` auf Auto-Pi syncen / `git pull`.  
2. UART ohne DTR/RTS, ein OTG → Reset-Grund.  
3. Wenig stecken (Klasse A), Ohr @32k, dann K3.  
4. Stall erst nach P0/P1.
