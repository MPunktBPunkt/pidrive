# B7 — Checkliste (M1, ohne Geometrie-FW)

**FW:** `0.4.36-dev` belassen · **Tool:** `tools/feld_150s_slot_pass.py`  
**Aufträge:** [AUFTRAG-B7-HU-REREAD.md](../auftraege/AUFTRAG-B7-HU-REREAD.md) · Überordnung [AUFTRAG-MSC-HOST-READ-NACHWEIS.md](../auftraege/AUFTRAG-MSC-HOST-READ-NACHWEIS.md)

Vorbereitet 2026-10-02 Abend: Lab-Smoke OK · Pi hat OTA-Bin + Guard-Fix · Bridge vor Fahrt neu auf `.89`.

## Vor dem Auto (Laptop)

```bash
cd ~/projects/pidrive
./tools/feld_prepare_homecoming.sh
# wartet auf .89, prüft 0.4.36, Bridge → .89
```

Optional M0-Blick: nach Replug/`msc.quiet` einmal `readOverflow` und ob `msc_reads`-Trace den Burst trägt. Bei massiven Drops → Telemetrie-Fix **vor** strengem Architektururteil (Überordnung M0).

## B7-A — eine Station ≥150 s (Live vor Select)

1. OTG **frisch** ab/an, Uhrzeit + `usbSerial` notieren.  
2. Bridge/Quelle so weit, dass Live-MP3 **bereit** ist (nicht erst nach dem Burst starten).  
3. Tool starten **bevor** Senderwahl:

```bash
python3 tools/feld_150s_slot_pass.py --uid fav1 --note "HH:MM OTG PDxxxx B7-A"
```

4. ENTER → **sofort** fav1 wählen → ≥150 s hören.  
5. Stoppuhr in `EAR.txt`: Ton-Start / Ton-Ende (s nach Select).  
6. Console `OK` (nicht `UID≠`). Bei `UID≠`: Play-Detection ungültig, Read-Flat trotzdem notieren.  
7. In EAR: Scan vs. Play kurz trennen (wann letzter `readCount`-Anstieg?).

**Orientierung (nur Rechnung):** ~28 s / ~87 s — Marker im Log, keine Garantie.

## B7-B — Armed-Replug (getrennt)

1. Stream auf Ziel-UID armed (Bridge/`lab/play`), dann OTG Replug.  
2. Sofort dieselbe Datei wählen; Burst-Fenster + `streamBytesΔ` notieren.  
3. Eigenes Artefakt-Ordner-Note `B7-B`.

## B7-C — Wechsel / Ordner (nur wenn A UID-OK oder bewusst Meta-only)

Ohne Replug: Ordnerwechsel + fav0 → fav1 → fav2; pro Wechsel Uhrzeit, Ohr, `readCount`/`playingUid`.  
Directory-Reads **nicht** als Live-Audio werten.

## Danach

```bash
# Artefakte unter docs/betrieb/artifacts-YYYY-MM-DD-b7/
# Feldbericht §11.11 + Verweis auf AUFTRAG-MSC-HOST-READ-NACHWEIS
```

**Wenn keine Play-Nachlese:** nächster Schritt = **L0-Geometrie-Auftrag** in `esp32.pidrive` (Überordnung M2), **nicht** Ring-OTA und nicht sofort BT.

## Nicht tun

- Kein OTA / kein Ring / kein Remount-Spam während des Hörfensters  
- Kein L3/L4-FW parallel  
- Kein zweites Tool parallel auf dieselbe ESP-Status-URL (unnötig)
