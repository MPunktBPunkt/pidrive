# Übergabe — Lab-Abend nach s4 → Feld s5 · für die nächste KI · 2026-10-08

**HEAD:** `pidrive` **cc2782f** (`origin/main`) · **FW Freeze 0.4.46-dev — kein OTA / kein Stall**  
**ESP Lab:** `.88` · **ESP Feld:** `.89` · Auto-Pi `.105`  
**Quellen:** [`GESAMTBERICHT-LAB-ABEND-NACH-S4`](../artifacts-2026-10-08-lab/GESAMTBERICHT-LAB-ABEND-NACH-S4-2026-10-08.md) · [`feld-s5-prep/`](feld-s5-prep/) · [`FELDPROTOKOLL-S5`](FELDPROTOKOLL-S5-FENSTER-Q11.md) · s4-Übergabe [`UEBERGABE-S4-NAECHSTE-KI`](UEBERGABE-S4-NAECHSTE-KI-2026-10-08.md)  
**Externe Reviews (diese Übergabe):** Mistral-Kurzfazit + GPT-Übergabebericht (unten zusammengeführt, an Artefakte angeglichen).

---

## 0. Gate

| Gate | Status |
|------|--------|
| Lab (Ring / Bitrate / Q10-Sim / Klasse-A / K3-FAT / Mid-Head) | **PASS** |
| Feld s5 | **GO** — Prep unter `feld-s5-prep/` |
| Stall / OTA / Ring-FW | **Freeze** |

**Ein Satz:** Das ~8‑s-Instrumentfenster ist über Bridge-Bitrate skalierbar (32k≈12,6 s); im Auto entscheiden jetzt Q11-Reset und die **Hördauer @32k** unter Klasse A — nicht eine weitere Lab-Runde.

---

## 1. Kernergebnisse Lab (Mistral + GPT, belegt)

| Aussage | Status | Beleg |
|---------|--------|--------|
| 48k ≈ 8,3–8,4 s | 🟢 | L4e / REPLUG Head |
| 32k ≈ 12,5–12,6 s @4000 B/s, 3/3 + Regression | 🟢 | fenster-32k, fortsetzung-2005/2035 |
| 24k ≈ 16,7–16,8 s @3000 B/s, 3/3 | 🟢 | fenster-24k, fortsetzung-2022 |
| Q10 READ10 = 4 KiB (Sim, 128×) | 🟢 Sim / 🟡 echte HU | `lab_q10_read_sniff.py` |
| Kopf-Pause Sim ~19 ms | 🟢 Sim | q10-sniff-fixed |
| Klasse-A Remount ×5, 0 Soft-Reset | 🟢 | fortsetzung-1940 |
| K3 Rename auf FAT (`… LAB 1008.mp3`) + Restore | 🟢 | fortsetzung-2022 |
| Rename setzt P zurück | 🔴 nicht bewiesen (s4 dagegen) | Feld |
| Mid → `not_from_head`/`plug_window` | 🟢 | fortsetzung-2005/2035 |
| Head + Prefill → Live | 🟢 | REPLUG |
| Q11 Reset-Ursache | 🔴 | UART fehlt im Lab-CT |
| Hördauer @32k an der HU | 🔴 | nur Feld |
| P-Größe | 🔴 | braucht FW |
| Stall | ⛔ Spec only | Freeze |

**Metrik:** Instrument-`live_s` immer mit Ring/undΔ und `live_s_at_bps` zitieren (32k→4000). Instrument ≠ Ohr.

---

## 2. Diskriminierender Feldtest (GPT)

| Ausgang @32k Klasse A | Deutung |
|----------------------|---------|
| **A** HU hört deutlich länger (~10–12 s) | Datenrate/Ringfenster war relevanter Faktor |
| **B** HU weiterhin ~5–6 s | Begrenzung nach USB/Ring (HU-Anlauf/Format/Verhalten) |
| **C** weiße LED / Boot | Episode nur für **Q11**, nicht für A/B |

So werden Reset, P-Zustand, USB-Lesen und Tonfenster nicht wieder zu einer Ursache vermischt.

---

## 3. Episodenklassen (verbindlich)

| Klasse | Bedingung | Verwendung |
|--------|-----------|------------|
| **A** | OTG ab/an, **keine** weiße LED, Uptime/Serial stabil | Tonfenster / P / O2 / K2 / K3 |
| **B** | weiße LED / Boot | nur Q11 |

---

## 4. Feld s5 — Reihenfolge (~20–25 min)

Prep: `docs/betrieb/artifacts-2026-10-08-feld/feld-s5-prep/`  
Default Bridge: **32k / 4000 B/s / marker / msc-lock** · `./run-s5.sh 1800`

1. **Q11** — UART **ohne** DTR/RTS; 1× OTG; `rst:`/Brownout sichern  
2. **O2** — Klasse-A, BOB, **Ohr** + Zähltöne @32k  
3. **K2** — Bayern Klasse-A  
4. **K3** — OTG ab → `./rename.sh fav2 "Radio BOB 1008"` → Freeze → OTG an → Start 0 oder P?  
5. **K4** — `./rename.sh fav2 ""` + neue Session  
6. **K5** — Reboots zählen  

Auswertung: `python3 tools/feld_live_window.py --run <RUN>` — Sekunden @32k ≈ live_bytes/4000.

---

## 5. Nicht anfassen

- OTA, Stall, Ringkapazität, Pump-Verhalten (Freeze)  
- P-Größe als Haupttest (höchstens notieren)  
- Klasse-B-Episoden als Tonfenster werten  

---

## 6. Neue Werkzeuge (Lab)

| Tool | Zweck |
|------|--------|
| `tools/lab_q10_read_sniff.py` | READ10 + Kopf-Pause aus `reads.jsonl` |
| `tools/lab_fenster_bitrate.py` | Prefill→REPLUG 24/32/48k |
| `tools/lab_fat_list.py` | FAT `STATIONS/`-Namen |
| `nbt_hu_sim --replug-bps` | `live_s_at_bps` |

---

## 7. Projektverlauf (kurz)

- **s3:** Ringmodell, Replug-Reads, Mid-File-Reject  
- **s4:** Auto Bild+Ton ~5–6 s Ohr / ~8,26 s Instrument; Steck-Resets (Klasse B) häufig  
- **Lab-Abend:** Bitrate-Leiter, Klasse-A-Methode, K3-FAT, s5-Prep  
- **s5:** Q11 + Ohr@32k unter Klasse A → Hypothese A/B/C  

---

## 8. Auftrag an die nächste KI

1. Freeze halten.  
2. Auto-Pi: `git pull` → `feld-s5-prep` starten.  
3. Strikt Klasse A/B trennen.  
4. Ergebnis als A / B / C formulieren (Abschnitt 2).  
5. Stall erst nach Eingrenzung Q11 + Ohr@32k (oder explizites Go).
