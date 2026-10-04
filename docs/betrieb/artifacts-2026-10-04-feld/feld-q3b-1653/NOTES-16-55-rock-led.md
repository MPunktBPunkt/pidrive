# Feld Q3b — 16:55 Rock + LED (PD0060)

**FW:** `0.4.44-dev` · Prefill Seed **B** ab LBA 761 aktiv · kein Remount nach Seed

## Operator
- 16:55 Autoplay wechselt zu Rock Antenne, LED blinkt

## Messstand (sofort gesichert)

| Punkt | Befund |
|-------|--------|
| playingUid | `fav0` Rock Antenne |
| bodySeed | aktiv tag=B fromOff=348160 |
| cold_body_burst | mehrfach, u. a. große Spanne `lba=97..16457` / `7793..12841`, immer `ev=not_from_head` |
| HU Body-Reads | **ja** — Trace 16:55:45–57, body≥761 ≈5,0 MiB, LBA **761 und 1953** im Trace |
| Detect | Head-Pfad armierte Play (`msc.phase play` + `audio.start fav0`); Cold weiter `not_from_head` |
| AV-Metrik | `streamBytes=7876608` == `underruns` → **liveBytes=0** |
| play.guess (diag-count monitor) | Stream aktiv; Detect hat geschaltet über Warm/Head, nicht über Cold-Event |

## Deutung

1. **Feld-Oracle B (HU fordert Body):** vorläufig **PASS** — HU liest fav0-Body inkl. Prefill-Region.
2. **Feld-Oracle C (Seed B ausgeliefert):** **ungeklärt / gefährdet** — sobald Live-Stream auf fav0 aktiv ist, liefert `onRead` den **Ring** (hier nur Underrun/Silence), **nicht** `LabBodySeed`. Seed gilt nur im Non-Live-Zweig.
3. **AV:** Metrik sagt 0 Live-Bytes; Ohr-Bericht vom Operator noch offen.
4. **Detect:** Bias bestätigt — Cold loggt `not_from_head`, Play kommt über Head/`seq_short`→ok.

## Noch vom Operator
- Ton hörbar? Stille / Rauschen / erkennbares Signal?
- Film/UI-Timer vorhanden?

## Operator 16:57
- **Kein Ton** bis 16:57 → **AV FAIL** (Ohr)
- Metrik deckungsgleich: liveBytes=0

## Ampel dieser Session
| Prüfpunkt | Status |
|-----------|--------|
| P0/Menü | nicht neu provoziert; Namen stabil Rock/Bayern/BOB |
| P1 Body-Next | EVIDENCED (Burst+LED ~16:55) |
| Feld-Oracle B | PASS (HU liest ≥761 inkl. 1953) |
| Feld-Oracle C | FAIL/blocked — Live-Overlay statt Seed nach Detect |
| AV | **FAIL** |
| Detect | Cold=`not_from_head`; Play über Head; `cold_body_burst` log ok |
