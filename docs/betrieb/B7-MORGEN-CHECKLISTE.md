# B7 — Checkliste (M1; L0 nur Lab)

**FW Auto:** `0.4.36-dev` · **Tool:** `tools/feld_150s_slot_pass.py`  
**Aufträge:** [AUFTRAG-B7-HU-REREAD.md](../auftraege/AUFTRAG-B7-HU-REREAD.md) · [AUFTRAG-MSC-HOST-READ-NACHWEIS.md](../auftraege/AUFTRAG-MSC-HOST-READ-NACHWEIS.md)

## Vor dem Auto

```bash
cd ~/projects/pidrive
./tools/feld_prepare_homecoming.sh
```

M0: nur bei `readOverflow` / lückenhaftem Burst-Trace — Drops **Anzahl + LBA** notieren. Sonst skip.

**Lab parallel ok:** L0-Geometrie auf `.88` bauen; **kein** L0-OTA auf `.89` vor Ende von B7-A/B/C.

## B7-A — ≥150 s Baseline (Live vor Select)

1. OTG frisch, Uhr + `usbSerial`.  
2. Live-MP3 bereit.  
3. Tool:

```bash
python3 tools/feld_150s_slot_pass.py --uid fav1 --note "HH:MM OTG PDxxxx B7-A"
```

4. ENTER → sofort fav1 → ≥150 s.  
5. EAR: Ton-Start/Ende + **UI-Position** (iDrive-Zeit falls sichtbar).  
6. `OK` vs `UID≠`; Read-Flat trotzdem notieren.  
7. Wann letzter `readCount`-Anstieg? (Scan vs. Play)

**Erwartung:** keine Play-Reads → Baseline, kein Fail.

## B7-B — Armed-Replug

1. Stream armed → OTG Replug → Datei.  
2. `streamBytesΔ` + Ohr-Dauer.  
3. Note `B7-B`.

**Erwartung:** ≤ ~8 s Live (48 KiB-Ring-Deckel) — kein Misserfolg.

## B7-C — Wechsel / Ordner

fav0→fav1→fav2 + Ordner; Uhr, Ohr, `readCount`/`playingUid`.  
Hartes Payload-Urteil nur mit Read-Klassen (M0); sonst Meta-only.

## Danach

Artefakte `docs/betrieb/artifacts-YYYY-MM-DD-b7/` · Feldbericht §11.11.  
Nächster Auto-Schritt nach Baseline: **L0-OTA** → statische L-Leiter (nicht Ring, nicht BT).

## Nicht tun

- Kein Ring-/L0-OTA während Hörfenster  
- Kein Live als Variable der späteren L-Messung  
- Kein zweites Status-Poll-Tool parallel
