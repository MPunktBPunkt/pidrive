# Übergabe — Feld s4 + Lab · für die nächste KI · 2026-10-08

**HEAD:** `pidrive` **a90c0f0** (`origin/main`) · **FW Freeze 0.4.46-dev — kein OTA**  
**Feldlauf:** `feld-s4-prep/s4-20261008-165212` · ESP `.89` · Auto-Pi `.105` · Bridge 48k / 6000 B/s / Marker 1 s  
**Quellen:** [`GESAMTBERICHT-FELD-S4`](GESAMTBERICHT-FELD-S4-TONFENSTER-2026-10-08.md) · [`ERGEBNIS-S4`](feld-s4-prep/s4-20261008-165212/ERGEBNIS-S4.md) · [`LIVE-WINDOW.txt`](feld-s4-prep/s4-20261008-165212/LIVE-WINDOW.txt) · [`ERGEBNIS-LAB-ABEND`](../artifacts-2026-10-08-lab/lab-abend-1556/ERGEBNIS-LAB-ABEND.md) · [`ERGEBNIS-LAB-NACH-S4`](../artifacts-2026-10-08-lab/lab-abend-nach-s4-1741/ERGEBNIS-LAB-NACH-S4.md) · Kritik Mistral: [`KRITIK-MISTRAL-S4-2026-10-08.md`](KRITIK-MISTRAL-S4-2026-10-08.md)

---

## 0. Operator-Kern (verbindlich)

1. **OTG ab/an ohne ESP-Reset** ist die nutzbare Klasse. Weiße LED / frischer Boot = Episode für Resume/Tonfenster oft verloren.  
2. **Bild + Ton ~5–6 s** nach solchem Replug bei **Radio BOB**, **Rock Antenne** und **Rock Antenne Bayern**.  
3. Umsetzung (Lab L0–L3, Tools, s4-Prep) war durch; s4 + Lab-Nachlauf L4-Ersatz sind dokumentiert und auf `main`.

Zwei Episodenklassen immer trennen:

| Klasse | Bedeutung |
|--------|-----------|
| **A** Replug, Uptime/Serial stabil | HU-/Cache-/Resume-/Tonfenster-Aussage gültig |
| **B** Replug mit ESP-Reset | nur für Reset-/Versorgungsfrage; P/Tonfenster eingeschränkt |

---

## 1. Unabhängiger Befundstand

### Gesichert / sehr stark

| Aussage | Beleg |
|---------|--------|
| ESP liefert virtuelles Medium; HU liest nach Replug | s4 Status/Trace/msc |
| Replug **kann** ohne ESP-Reset laufen | Operator + Marks (z. B. 17:13 „no crash on plug“) |
| Bild+Ton BOB | 17:13 SUCCESS |
| Bild+Ton Rock Antenne | 17:18, 17:24 PD0153 |
| Bild+Ton Bayern | **Operator** (verbindlich); Log: `play_uid=fav1` 17:20 Stream startete — Ohr-Ton separat als Operator [B] |
| Saubere ~8,2 s-Live-Episode = 48 KiB-Ring | LIVE-WINDOW #106 `PD0127` fav2 17:11:39: Ring 49152, Live-B 49589, **Live-s 8.26**, undΔ 471640 |
| Lab L2 Dump ~8,25 s Live dann Stille | lab-abend-1556 |
| Lab L1 REPLUG Live ~8,3 s | 9/9 PASS |
| Dateiname allein ≠ P-Schlüssel | K3 Rename/Cache-Bust, weiter Mid-File / `not_from_head` |
| Mid-File → Play-Detect `not_from_head` | Feld 112× + Lab L3 Q12 |
| Lab REPLUG×10: **0** Uptime-Drops | lab-abend-nach-s4-1741 — reiner SG-Replug rebootet Lab-ESP nicht |

### Eingeschränkt / korrigiert gegenüber Kurzfassung „Ring = immer 8,2 s“

- **LIVE-WINDOW #167** `17:18:25 PD0137 fav0`: Live-B **106054**, Live-s **17.68**, Ring trotzdem 49152, undΔ ~8 M.  
  → `Live-s` = instrumentierte Live-Bytes/bps in der Episode, **nicht** „HU hat 17 s gehört“ und **nicht** „Ring fasst 17 s“.  
  → **8,2 s ist bestätigt für die Ring-äquivalente Episode**, aber **keine** bewiesene globale HU-Obergrenze.
- Ohr ~5–6 s vs Instrument ~8,2 s: Fehler **nach** Ring-Erzeugung wahrscheinlich (HU-Anlauf/Format). End-to-End „HU hat alle Bytes und Decoder verwirft Anfang“ ist **nicht** strikt bewiesen → Formulierung: *stärkste Erklärung*, nicht „nachweislich nur HU“.

### Offen

| Thema | Status |
|-------|--------|
| P-Schlüssel exakt (Pfad / Größe / Kombi / Track-ID) | Hypothese |
| Q10 = 4 KiB je READ10 | Kandidat [S], Sniffer fehlt |
| Q11 Reset-Grund Feld | UART `rst:` fehlt; Versorgung **priorisiert**, nicht bewiesen |
| E7 / Stall / Lead-Bytes | Spec only, Freeze |
| sysfs `authorized` / VBUS-Zyklen im Lab-Host | RO — nicht gefahren |

---

## 2. Kurz: Lab-Gate

- **L0–L3** PASS (`lab-abend-1556`): Bridge/Marker, REPLUG-Leiter, Dump ~8,25 s, Q12=`not_from_head`.  
- **L4 VBUS/authorized:** auf diesem Host unmöglich (sysfs RO). Ersatz REPLUG×10 → 0 Drops.  
- Viele REPLUG-FAIL wegen `ring_full_pre=False` ohne Dauer-Bridge — Infrastruktur, kein ESP-Reset.

---

## 3. Auftrag an die nächste KI (Priorität)

**Freeze halten — kein OTA / kein Stall-Flash ohne explizites Go.**

**Lab-Gate (08.10. Abend): geschlossen** für Ringfenster, Bitrate-Leiter, Q10-4 KiB, Klasse-A-Remount, K3-FAT, Mid-Reject. UART/`authorized` im Lab-CT nicht verfügbar.  
**Gesamtbericht Lab:** [`../artifacts-2026-10-08-lab/GESAMTBERICHT-LAB-ABEND-NACH-S4-2026-10-08.md`](../artifacts-2026-10-08-lab/GESAMTBERICHT-LAB-ABEND-NACH-S4-2026-10-08.md)  
**Weiter = Feld s5:** [`feld-s5-prep/`](feld-s5-prep/) · [`FELDPROTOKOLL-S5-FENSTER-Q11.md`](FELDPROTOKOLL-S5-FENSTER-Q11.md) · Default Bridge **32k**.

### P0 — Feld: Reset-Ursache (Q11)

1. UART-Bootlog **ohne** DTR/RTS.  
2. Ein kontrollierter OTG-Zyklus; `rst:` / Brownout / Panic sichern.  
3. Optional Netzteil-A/B, VBUS-Blocker (O3/O4).  
4. Session-Disziplin: wenig Stecken → mehr Klasse-A-Episoden.

### P1 — P-Schlüssel (eine Variable pro Versuch)

1. gleicher Pfad, andere Größe  
2. anderer Pfad, gleiche Größe  
3. dann Track-ID/Kombi  

Klasse A (kein ESP-Reset) Pflicht.

### P2 — Q10 Sniffer

READ10-Länge und 19‑ms-Kopfpause; 4 KiB bleibt Kandidat.

### P3 — Stall / E7

Erst nach P0/P1-Eingrenzung; Spec: `STALL-BUILD-SPEC-2026-10-08.md`. Reset-Telemetrie im Spec wäre auch ohne Stall wertvoll.

### Lab parallel

- REPLUG mit Prefill: erledigt `lab-abend-nach-s4-1837` — **5/5 PASS**, live_s 8,28–8,41 s, **0** Drops ([`ERGEBNIS`](../artifacts-2026-10-08-lab/lab-abend-nach-s4-1837/ERGEBNIS.md)).  
- Bitrate-Leiter ohne FW: 32k ≈12,6 s · 24k ≈16,6 s (`lab-fenster-32k-1917`, `lab-fenster-24k-1919`).  
- Fortsetzung 19:40: Q10-Sniff **4 KiB**, Klasse-A Remount×5 **0** Drops, authorized weiter RO — [`lab-abend-fortsetzung-1940/ERGEBNIS`](../artifacts-2026-10-08-lab/lab-abend-fortsetzung-1940/ERGEBNIS.md). Tool: `tools/lab_q10_read_sniff.py`; Sim: `live_s_at_bps` / `--replug-bps`.  
- Fortsetzung 20:05: K3 Name-Override+Remount **PASS**, Mid-SG Reject vs Head-REPLUG **PASS**, 32k×3 **12,5–12,6 s** — [`lab-abend-fortsetzung-2005/ERGEBNIS`](../artifacts-2026-10-08-lab/lab-abend-fortsetzung-2005/ERGEBNIS.md); Tool `tools/lab_fenster_bitrate.py`.  
- Fortsetzung 20:22: K3 **FAT** `Radio BOB LAB 1008.mp3` sichtbar (`lab_fat_list.py`), 24k×3 **16,7–16,8 s**, UART im Lab-CT **fehlt** — [`lab-abend-fortsetzung-2022/ERGEBNIS`](../artifacts-2026-10-08-lab/lab-abend-fortsetzung-2022/ERGEBNIS.md).  
- Regression 20:35: 32k **12,61 s** + Mid-Reject + playDetect-Snapshot — [`lab-abend-fortsetzung-2035/ERGEBNIS`](../artifacts-2026-10-08-lab/lab-abend-fortsetzung-2035/ERGEBNIS.md).  
- **s5-Prep bereit:** [`feld-s5-prep/`](feld-s5-prep/) (`run-s5.sh`, `GO.md`, `ANKUNFT.md`).

- authorized/VBUS nur mit Host-`uhubctl` (CT: sysfs RO).  
- `Live-s`-Metrik immer mit Ring/undΔ **und** `live_s_at_bps` zitieren (Mehrdeutigkeit #167).

---

## 4. Ein Satz für den Kontext

Lab kann Ringfenster und K3-FAT ohne FW verlängern/umbenennen; im Auto bleiben **Q11-Reset** und **Ohr @32k unter Klasse A** die Blocker. Stall weiter nur Spec.
