# Feld-Session 2026-10-05 Morgen (Auto, PD0064)

**FW:** `0.4.45-dev` · Serial **PD0064** · Abbruch ~07:53 (Arbeit)

## Lauf 1 — C′ (Seed)
- RST 07:44 → Prepare `feld-q3b-next-0744` → **GATE PASS**
- Watchdog **PASS** 07:45:33: `bytesServed` 0 → 1 511 424 (danach ~3,3 MiB)
- Operator: Menü Favoriten/Quellen/Stop (nicht Rock/Bayern/BOB); 07:45 Quellen; LED; 07:47 Quellen-Ende LED blink; 07:49 Stop Autoplay, kein Ton (erwartet)
- Seed überlebte Settle (≠ 1738 Reboot-Tod)

## Lauf 2 — AV (Seed aus)
- RST 07:50 → Seed clear, Pump up
- Menü bleibt Favoriten/Quellen/Stop; Bridge `frozen_reject` vs. Lock Rock/Bayern/BOB
- 07:52 Quellen + LED; 07:53 Stop + LED
- Correlate: durchgängig **stream=off, liveBytes=0** — nur kalte File-Reads (Quellen/Stop je ~512 KiB)
- **AV/Ohr offen** — kein Live-MPEG-Fenster erreicht

## Artefakte
- `feld-q3b-next-0744/` — C′ PASS
- `feld-av-0750/` — AV negativ / Menü-Lock-Hindernis

## Nächstes Feld
1. Menü auf Sender-Seite (Rock/Bayern/BOB) bringen — Lock vs. Favoriten/Quellen/Stop klären
2. AV mit `stream.active` + `liveBytes>0` + Ohr; Seed aus
