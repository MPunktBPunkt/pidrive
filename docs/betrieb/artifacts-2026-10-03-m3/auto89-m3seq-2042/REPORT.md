# Auto-M3seq Feld — 2026-10-03 ~20:42–21:02 (BMW NBT)

**Artefakte:** `docs/betrieb/artifacts-2026-10-03-m3/auto89-m3seq-2042/`  
**FW:** `0.4.42-dev` L3 · ESP `.89` · Bridge `.105` → `.89` **`--no-audio`**  
**Geometrie:** FAT16 16 MiB · fav0=8 MiB · fav1/fav2=512 KiB (Silence+PDMK)  
**Gültigkeit:** Bridge vor erstem Plug up; M0/Export für Hauptfenster `ov=0` (Ausnahme PD0048 Stecken: `ov=144`)

Evidenz: **D** Status/JSONL/Operatorzeiten · **I** A–E / Cache · **C** Counter-Semantik

---

## 1. Enger Befund

1. **Q1 Select (Rock, PD0042, ~20:43):** Idle `quiet rc=167` → Auswahl Rock → großer Read-Burst (`Δrc` ~+2000, `play_uid=fav0`) → danach **flach** bei `rc=2156` trotz `phase=play`.  
2. **Q2 Trackende / Auto-Next (PD0043):** BOB-UI-Balken, Bayern komplett durch, Autoplay→Rock — jeweils **`Δrc=0`**, `ov=0`, TCP up. Kein neuer `play_uid`.  
3. **Arm3 Remount (PD0045/46/47/48):** Unplug/Plug → Mount-Scan → `quiet`; anschließende Titelwahl (auch mehrfach) → **keine** neuen Reads, **keine** LED.  
4. **Kein Ton** erwartet (`audio=off` + Silence-Stubs). LED-Blinken nur bei erstem Rock-Select/`play.guess`.

**Klassifikation (I):** `A_then_E` auch nach Select und über Auto-Next; Remount liefert Scan-Reads, danach wieder Cache-Wiedergabe ohne MSC-Nachlese.

---

## 2. Ablauf (Operator + Messfenster)

| Zeit | Ereignis | Messlage (D) |
|------|----------|--------------|
| 20:42 | OTG / Session start | Bridge up, Menü zunächst Fav-Sender |
| 20:42–07 | Idle nach Mount | `PD0042` `quiet rc=167` |
| **20:43** | **Rock Antenne gewählt** | `quiet→play`, `play_uid=fav0`, großer `Δrc`, dann flat `rc=2156` |
| 20:45 | kein Ton; LED beim Wechsel | erwartet (`--no-audio`); Guess ok |
| 20:47 | „BOB“ / Fav1-Burst | Trace: **fav1-LBAs** (Bayern-Body) bis `lba=17481`; danach flat `rc=2284` |
| 20:49 | BOB-Balken läuft | **Δrc=0** (~25 s) — UI ohne Reads |
| 20:50 | Bayern komplett durch | `rc` weiter 2284 |
| 20:51 | Autoplay → Rock | **Δrc=0** |
| 20:53 | OTG neu | Unplug/Plug `PD0045`→`PD0046`, Scan→`quiet rc=2344` |
| 20:54 | Bayern gewählt (Korrektur) | **Δrc=0**, kein Guess |
| 20:56 | OTG neu `PD0047` | Scan→`quiet rc=2345` |
| 20:57 | Zurueck / Ausgang / Auto je gewählt | Menü-Namen von Pi-UI überschrieben (= Slot0/1/2); **Δrc=0** |
| 20:59 | OTG neu `PD0048` | TCP kurz down beim Stecken → **`ov=144`**; Scan→`quiet rc=2345` |
| 21:00 | alle Files mehrfach | flat, **keine LED** |
| 21:01–02 | OTG `PD0049`; Radio aus | ESP weiter plugged/`quiet rc=382` (leichter Scan); Abschalten = HU |

---

## 3. Auswertung nach Fragen

### Q1 — Select ohne Remount → neue Reads?
**Ja, einmalig beim ersten Rock-Select** (Audio-LBAs fav0, großer Burst). Danach flach.  
Zweiter „Select“ in derselben Mount-Session (BOB-UI / Bayern-Durchlauf) ohne zusätzliche Reads während UI-Play.

**NAV vs AUDIO (I):** Rock-Burst liegt in File-LBA fav0 (nicht nur DIR/FAT) — Select-Trigger für Nutzdaten **einmal** belegt.

### Q2 — Trackende / Auto-Next → neue Reads?
**Nein** (kalibriert gültig: TCP up, `ov=0` im PD0043-Fenster). Bayern ausklingen + Autoplay Rock → `Δrc=0`.

### Q3 — Frische?
**Nicht ausgeführt** (kein Payload-Wechsel-Protokoll).

### Arm3 — Remount
- **3a passiv:** nach Scan idle/`quiet` ohne Operator-Select.  
- **3b Select nach Scan:** keine Extra-Reads, keine LED — Prefetch im Scan reicht für HU-Cache.  
- Mehrere Replugs (`PD0046`…`PD0049`) reproduzieren Scan→quiet→Select-ohne-Reads.

---

## 4. Störfaktoren / Gültigkeit

| Thema | Wirkung |
|-------|---------|
| Bridge `--no-audio` | kein Live-Ton; M3seq absichtlich Read-fokussiert |
| Pi `pidrive_menu.json` überschreibt MSC-Namen | Anzeige „Zurueck/Ausgang/Auto“ statt Rock/BOB; **LBA-Bodies** bleiben Slot0/1/2 |
| PD0048 Stecken | TCP kurz down → `ov=144` — früher Scan-Export lückenhaft; Status-`rc` ok |
| Radio aus 21:02 | HU aus; ESP USB weiter up |

Nur ein `play_uid` in der gesamten Bridge-Session: **`fav0`**.

---

## 5. JSONL-Übersicht (gesamte Session-Datei)

| Region | Σn | Σbytes (Burst) |
|--------|-----|----------------|
| fav0 | 8072 | ~31,5 MiB (inkl. Remount-Wiederholungen) |
| fav1 | 394 | ~1,5 MiB |
| fav2 | 439 | ~1,7 MiB |
| meta | 157 | ~0,6 MiB |

---

## 6. Folge (I)

- Chunk/Live-Overlay ohne Host-Re-Read nach Sweep/Select **weiter unwahrscheinlich** für diesen NBT.  
- Remount allein erzeugt Scan, **kein** nachhaltiges Play-Read.  
- **Freeze** Ring/PSRAM/BT/Pacing unverändert.  
- Nächste Schritte optional: Q3 Frische nur mit festem Protokoll; Menü-Lock gegen Pi-UI-Überschreiben vor Feld.

## 7. Dateien

Status-Snapshots `status-02`…`status-22`, `status-99-final.json` · `pidrive_msc_reads.jsonl` · `pidrive_msc_diag.jsonl` · `pump_bridge_89_m3seq.log` · diese `REPORT.md` / `EAR.txt`
