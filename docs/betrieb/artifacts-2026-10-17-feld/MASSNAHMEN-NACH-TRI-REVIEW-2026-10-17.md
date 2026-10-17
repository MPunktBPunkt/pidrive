# Maßnahmen nach Tri-Review (GPT + Mistral + Claude) · 2026-10-17

**HEAD-Bezug:** Feld `724e492` · Lab-Prep `6ee1b96` · Triage-Lab `claude-triage-lab-01`  
**Quellen:** GPT-Analyse, Mistral-Review, Claude-Hypothesen; Rohdaten `feld-ota-053/` nachgerechnet.

## Claude-Korrekturen (übernommen)

| # | Claude | Entscheidung |
|---|--------|--------------|
| C1 | B5 „Live = 4 KiB HU-Architektur“ zu stark | **Kein Matrix-Eintrag als HU-Architektur.** Callback-Takt = E5/R15; CBW = E11. Eager-`blocks=240` in `mess.json` bleibt CBW-Fakt. |
| C2 | fav1@16465 allein ≠ Favoriten-Beweis | **Zustimmung.** Zusatz: `mess.json` hat **DIR LBA 65+73** → neue Ordner-Cluster wurden gelesen (`feld-mess-dir-hits.json`). |
| C3 | Stall am NBT schon s6 (R29); playGuess vor Stall | **Zustimmung.** Stall-Leiter erst nach Play-Guess-Check (R30). |
| C4 | `software`→`power_on` = Reset dazwischen | **Zustimmung.** `plugCount=2`/`unplug=1` → Replug; Q11/UART beim nächsten Feld. |
| C5 | Ton-Dauer fehlt | **offen** — nächstes Feld: Marker/Uhr. Erwartung ohne Pacing ~8 s (R25). |
| C6 | underruns = Bytes | **bestätigt** (FW + R25/R27); Lab-Notiz `underruns-note.json`. |
| C7 | Ordner = NBT-Index / konstante BPB-ID | **Hypothese.** Lab: Volume-ID-Rotation funktioniert (Serial gehalten, SG_IO BPB vid neu). **Feldtest Q14:** nur `fatVolumeId` ändern, Ordner-UI beobachten. |

## Maßnahmen-Tabelle

| ID | Maßnahme | Prio | Wo | Status |
|----|----------|------|-----|--------|
| M20 | Klasse-A-Repro 3–5× auf 0.4.53 + **UART** + uptime/resetReason/plugCount | **P0** | Feld | ☑ Abend n≥3 Klasse A + Ton; UART ☐; danach wieder Panic (`feld-go-abend-01`) |
| M21 | Bei Repro: Ton-Dauer stoppen (Soll ~8 s ohne Stall / länger mit) | P0 | Feld | ☑ ~6–7 s ×3; Ring voll ≈8,2 s (`liveAvailMs=8192`) |
| M22 | Play-Guess-Pfad prüfen (`playGuessCount` / Head-READ) **vor** Stall-Leiter | P0 | Feld (+Lab) | Lab ☑; Feld ☑/☐ sporadisch (`msPlugToPlayGuess` ~17–22 s), nach Panic oft 0 |
| M23 | Stall-Leiter am NBT auf fav1 nur wenn M20 grün **und** M22 Guess greift | P0 | Feld | ☐ wartet (Guess labil) |
| M24 | Ordner: Feld **nur BPB-Volume-ID** rotieren (Serial gleich) — Cache-Hypothese (Grok) | P1 | Feld | ☑ Gate VID; Ordner unter Mediensuche → Hypothese allein **geschwächt** |
| M25 | Ordner: alternativ Serial/RemountGen bump (Identity) als A/B zu M24 | P1 | Feld | ☐ |
| M26 | underruns in Telemetrie-Doku als **Bytezähler** markieren (Status-API/Docs) | P1 | Lab/Docs | ☑ Notiz |
| M27 | hostAbsCursor > fileEnd im Erfolgslauf — Cursor-Modell kurz dokumentieren | P1 | Lab | ☐ |
| M28 | `nbt-flat` mess: Scan-Geometrie (8er/240er) als Eager-CBW-Hinweis behalten; nicht mit Callback-Takt vermischen | P2 | Docs | ☑ |
| M29 | B5 **nicht** als neue HU-Lesearchitektur in Matrix | P2 | Matrix | ☑ Ablehnung |

## Reihenfolge nächstes Feld

> **Aktualisiert:** siehe [`MASSNAHMEN-NACH-LIVELOCK-AUDIT-2026-10-17.md`](MASSNAHMEN-NACH-LIVELOCK-AUDIT-2026-10-17.md) — P0 = UART+Storm-Capture (M30), nicht 167/136.

```
UART an → 3–5× OTG Klasse-A (M20/M21)
    ├─ alle A → Panic → P1 historisch
    └─ wieder Weiß → M8 VBUS/UART (Q11)
Play-Guess beobachten (M22)
Optional: Volume-ID-only Remount (M24) → Ordner sichtbar?
Erst dann Stall-Leiter fav1 (M23)
```

## Nicht tun

- Panic als gefixt bezeichnen (n=1 + Replug-Reset dazwischen)
- Ordner-Layout umbauen vor M24/M25
- Stall-Leiter ohne Play-Guess / ohne Repro
- Callback-4 KiB als CBW-/HU-Architektur verkaufen
- 512‑KiB-Wiederholungen / Soft-Cycle×Stall mischen
