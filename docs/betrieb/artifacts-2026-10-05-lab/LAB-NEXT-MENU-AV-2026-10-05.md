# Lab-Weiterarbeit — Menü-Seite + AV-Prep · 2026-10-05

**Kontext:** Feld morgen C′ **PASS**; AV scheiterte weil HU/API **Favoriten / Quellen / Stop / Mehr…** zeigten und `stream.active=false` / `liveBytes=0`. Bridge loggte `frozen_lock` gegen Rock/Bayern/BOB.

**ESP Lab:** `http://192.168.178.88` · FW `0.4.45-dev`  
**Feld Abend:** erst Sender-Seite, dann AV (C′ nicht wiederholen).

## Hypothese

Favoriten/Quellen/Stop ist die **Meta-/Page-Next-Seite** (bekannt aus FELDTEST / `pump:page_next`), nicht die gesiegelten Fav-Sender. Lock hält Rock-Siegel; Session liegt auf der anderen Seite → kein Live-Producer → LED = kalte Body-Reads.

## Lab-Aufträge (Reihenfolge)

1. **Repro Seite:** Bridge → `.88`, Menü Rock/Bayern/BOB vs. nach `page_next` Favoriten/Quellen/Stop; Status `slotMap` + `stream` dokumentieren.  
2. **Rückweg:** remount / page zurück / Lock release+reseal — welche Prozedur bringt Sender-Seite ohne Freeze-Bruch.  
3. **AV-Smoke:** auf Sender-Seite Producer an → `liveBytes>0` (Host-dd optional); Correlate-Skript gegen Meta-Seite = Negativkontrolle (wie Feld 07:52).  
4. **Abend-EAR:** 3–5 Zeilen Operator („Mehr… / Remount / Reseal …“) nach Lab-Ergebnis.

## Freeze

Ring/PSRAM/Pacing/Detect unverändert. Sequenz-GO weiter bis Hörtest.

## Artefakte

Unter `docs/betrieb/artifacts-2026-10-05-lab/` (dieser Ordner).
