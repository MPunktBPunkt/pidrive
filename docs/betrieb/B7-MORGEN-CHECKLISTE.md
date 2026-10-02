# B7 morgen — Checkliste (ohne FW-Änderung)

**FW:** `0.4.36-dev` belassen · **Tool:** `tools/feld_150s_slot_pass.py` · **Auftrag:** [AUFTRAG-B7-HU-REREAD.md](../auftraege/AUFTRAG-B7-HU-REREAD.md)

Vorbereitet 2026-10-02 Abend: Lab-Smoke OK · Pi hat OTA-Bin + Guard-Fix · Bridge zeigt aktuell noch auf `.89` (offline) → Homecoming neu.

## Vor dem Auto (Laptop)

```bash
cd ~/projects/pidrive
./tools/feld_prepare_homecoming.sh
# wartet auf .89, prüft 0.4.36, Bridge → .89
```

## Pass A — eine Station ≥150 s

1. OTG **frisch** ab/an, Uhrzeit + `usbSerial` notieren.  
2. Tool starten **bevor** Senderwahl:

```bash
python3 tools/feld_150s_slot_pass.py --uid fav1 --note "HH:MM OTG PDxxxx"
```

3. ENTER → **sofort** fav1 wählen → ≥150 s hören.  
4. Stoppuhr in `EAR.txt`: Ton-Start / Ton-Ende (s nach Select).  
5. Prüfen: Console zeigt `OK` (nicht `UID≠`). Bei `UID≠` Pass für Play-Detection ungültig, Read-Flat trotzdem notieren.

**Orientierung (nur Rechnung):** ~28 s / ~87 s — Marker im Log, keine Garantie.

## Pass B — Wechsel im selben Mount (nur wenn A UID-OK)

Ohne Replug nacheinander fav0 → fav1 → fav2; pro Wechsel Uhrzeit + was du hörst.  
Frage: neue `readCount` / `playingUid`?

## Danach

```bash
# Agent oder manuell:
git add docs/betrieb/artifacts-$(date +%Y-%m-%d)-b7/
# §11.11 im Feldbericht + push
```

## Nicht tun

- Kein OTA / kein Ring / kein Remount-Spam während des Hörfensters  
- Kein zweites Tool parallel auf dieselbe ESP-Status-URL (Polling-Kollision ok, aber unnötig)
