# F1 Feld — Stick ohne Hub (Abend 2026-10-07)

**Umgebung:** Stick Lexar `F1STICK` direkt an HU (USB-2-Hub: Stick **und** ESP **nicht** erkannt)  
**Dateien:** `F1-5MB_128k.mp3` und `F1-100MB_128k.mp3` — **gleiches Verhalten**  
**Video:** vorhanden (Operator)

## Beobachtung

1. Erster Einsteck / Antippen: Stimme zählt **`0 → 10 → 20 → …`** (Start vorn).
2. Ausstecken bei ~**10**, ESP dazwischen (u. a. Rock), ESP wieder ab, Stick rein.
3. Weiterzählen ab ~**20** — **Position am Stick/Datei gemerkt**, nicht Reset auf 0.
4. Mit **beiden** Dateien gleich.

## Deutung (Protokoll-Tabellen)

| Frage | Befund |
|-------|--------|
| F1 Spielen während Lesen? | **inkrementell** — Marker hörbar, Start bei 0 beim ersten Zugriff |
| Startposition nach Re-Plug / Medienwechsel? | **≠ 0** — Resume an gespeichertem **P** (wie R16 / Q8 `r16_resume_like`) |
| Hub USB-1.1 | entfällt — HU erkennt Medien nur **ohne** Hub |

## Stall-Go

- F1: eher **Go für Stall-Pfad** (inkrementell), sobald Timing-Video ausgewertet (t bis erstes „0“).
- R10/P: **nicht** geklärt im Sinne „frische Auswahl = Offset 0“ — P überlebt Stick↔ESP; Quelle von P weiter offen.

## Artefakte

- Videos (Handy)  
- Pi-Notiz: `feld-s2-prep/f1-OPERATOR.txt` / `f1-car-notes.jsonl`  
- Q8 Vormittag: `s2-20261007-172123/ERGEBNIS.md`
