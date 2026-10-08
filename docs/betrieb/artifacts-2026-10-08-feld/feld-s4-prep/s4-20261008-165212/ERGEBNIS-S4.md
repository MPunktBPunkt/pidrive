# Feld s4 — Tonfenster · Ergebnis 2026-10-08

**Lauf:** `s4-20261008-165212` · FW **0.4.46-dev** Freeze · Bridge 48k / 6000 B/s / Marker 1 s  
**Capture:** Auto-Pi `.105` · ESP `.89` · Serials `PD0108`…`PD0153` (Poll bis `PD0147`)  
**Lab-Gate:** L0–L3 PASS (`lab-abend-1556`)

## Kurzfassung

Hörbares Tonfenster existiert im Auto. Instrumentiert war **Live-s ≈ 8,26 s** in einer Ring-äquivalenten Episode (BOB, `PD0127` 17:11:39) — **gleich Lab L2**. Operator: **~5–6 s** Bild+Ton nach Replug **ohne ESP-Reset** bei **BOB, Rock Antenne und Bayern**. Differenz Ohr↔Instrument: wahrscheinlich HU-Anlauf/Format (nicht strikt E2E bewiesen). **Live-s ≠ immer 8,2 s** (z. B. #167 fav0 Live-s 17,68 bei Ring 48 KiB — Metrik Live-Bytes, nicht Hördauer). Stecken oft mit Reset (Klasse B); nutzbare Episoden = Klasse A. Resume-Mitte (`not_from_head`) und Cache blockieren viele Tips.

## Protokoll-Tabelle

| ID | gültig | Play-Detect | kein Reboot | Autoplay | Bild | Ton-s | Start 0/P | Bemerkung |
|----|--------|-------------|-------------|----------|------|-------|-----------|-----------|
| K1 BOB | ja (spät) | ja `fav2` | gemischt | ja | ja | ~5 s Ohr / **8,26 s** Live | oft P, dann Treffer | 17:13 SUCCESS; Live-Window #106 |
| K2 Bayern | ja (Ohr) | ja `fav1` 17:20 | gemischt | — | ja (Op.) | ~5–6 s Op. | P/`not_from_head` | Op. bestätigt; Log Stream; Replug teils Reset |
| K3 Rename | ja (Negativ) | — | — | — | — | — | **P bleibt** | Name allein setzt P nicht zurück |
| K4 | nicht sauber | — | — | — | — | — | — | Zeit/Reboots |
| K5 Reboots | — | — | **24** Uptime-Drops | — | — | — | — | 38 Serials in Poll |

Operator-Anker: **17:24 PD0153** Bild+Ton; **17:18** Antenne Bild+Ton; **17:13** BOB ~5 s.

## Mess-Highlights

- **Live-Window** `fav2` 17:11:39 `PD0127`: Ring 49152, Live-B 49589, **Live-s 8.26**, undΔ 471640, ID3~3059 → Ring = Lab.
- Play-Samples Status: `fav0` 84 · `fav1` 101 · `fav2` 16 (viele lab/play- und Reject-Phasen).
- Bridge-Rejects (Log): `not_from_head` 112 · `plug_window` 23 · `cooldown` 10 · `seq_short` 1.
- Autoplay-Switch geloggt: `fav2→fav0` (17:17), `fav0→fav1` (17:20).
- Q8: mehrere Episoden `r16_resume_like` / Mid-File (z. B. Bayern LBA ~17377).

## Erkenntnisse

1. **Tonfenster = Ring** (48 KiB @ 48k ≈ 8,2 s). Feld-Instrument und Lab stimmen; Ohr oft kürzer.
2. **R28:** Nicht nur BOB — Antenne mit Bild+Ton belegt.
3. **P-Schlüssel:** Display-Rename (`Rock Bayern 1008` / Cache-Bust-Namen) **reicht nicht**, HU liest weiter Mitte → `not_from_head`. Pfad/`STATIONS/0x.MP3`/Größe verdächtig.
4. **Cache:** Lange Phasen ohne USB-LED bei „Play“; später wieder Mid-Reads ohne Stream.
5. **Steck-Reboots (K5):** Dominantes Störfeld (~24 Drops / Session). Weiße LED ≈ frischer Boot/Scan. Erfolgreiche Tips oft bei **stabilem** Plug ohne Wackeln.
6. **Play-Detect:** Ohne Head-Sequenz kein `play_uid` → Stille trotz Tippen. Config-Tweak (`plugWindow=0`, `headSlop=64`) half begrenzt; Soft-Limit headSlop≤64.

## Artefakte

| Datei | Inhalt |
|-------|--------|
| `LIVE-WINDOW.txt` | Slot-/Live-s-Tabelle |
| `status-poll.jsonl` | 1713 Polls |
| `trace.jsonl` / `msc_reads.jsonl` | MSC |
| `bridge-audio.log` | play_uid / reject / ffmpeg |
| `marks.jsonl` | Operator-Marken |
| `q8/Q8-REPORT.json` | Resume-Muster |

Auswertung: `python3 tools/feld_live_window.py --run …/s4-20261008-165212`
