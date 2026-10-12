# Feld s5 — Fenster @32k + Q11 · Ergebnis 2026-10-11

**Lauf:** `s5-20261011-184623` · FW **0.4.46-dev** Freeze · Bridge **32k / 4000 B/s** / Marker 1 s / msc-lock  
**Capture:** Auto-Pi `.105` · ESP `.89` · Serials **PD0197…PD0216** (19 Transitions in ~14 min)  
**Operator-Anker:** 18:45 PD0197 online → 19:00 Haus

## Kurzfassung

**Kein auswertbares Tonfenster @32k.** In der gesamten Session: **0×** `play_uid` / `audio_start` / `stream_active`, **absEnd_max = 0**, alle Live-Window-Episoden **Live-s = 0,0** (nur Stille). Stecken unter WLAN/Bridge-Last → fast durchgängig **Klasse B** (weiße LED / Serial-Sprung). Ohne UART kein `rst:`-Beweis (Q11 offen). Hypothese „unbelastet stabil, unter Last Reset“ **operatorisch bestätigt**, Lab-Ohr-Hypothese A/B (@32k länger?) **nicht testbar**.

## Protokoll-Tabelle

| ID | gültig | Ergebnis | Bemerkung |
|----|--------|----------|-----------|
| Q11 UART | nein | Reset häufig, Ursache unbekannt | kein DTR/RTS-UART-Log; nur weiße LED / Serial↑ |
| O2 BOB @32k | nein | kein Stream, kein Ohr-Fenster | Tips ohne Play-Detect; Replug → B |
| K2 Bayern | nicht versucht | — | Session in Resets stecken geblieben |
| K3/K4 Rename | nicht versucht | — | braucht Klasse-A + Freeze |
| K5 Reboots | ja (Zählung) | **19** Serial-Wechsel | PD0197→PD0216; Bridge `hello_ack` 41 / `reconnected` 13 |

## Mess-Highlights

| Metrik | Wert |
|--------|------|
| Status-Polls | 698 |
| `playingUid` Samples | **0** |
| `stream_active` Polls | **0** |
| Live-Window Episoden | 49 · **alle Live-B/Live-s = 0** @4000 B/s |
| Bridge `audio_start` / `ffmpeg` | **0 / 0** |
| Bridge Rejects | `not_from_head` **40** · `plug_window` **12** |
| MSC Reads (Capture) | 1483 Zeilen — HU liest, aber ohne Pump-Ring |
| Peer `.105` | oft ok (542 Polls), flappt bei jedem Boot |

Typische Read-Muster (Live-Window): Mid-File / Resume (`fav0` 336K…8188K mit 1949 Reads bei PD0209) und kurze Head-Scans (`fav2` 0…256K) — alles als **Mp3Silence**, weil kein Stream lief.

## Zeitlinie (Operator + Log)

1. **18:46** RUN START 32k · PD0197 · vorab: OTG×n ohne LED **bis WLAN**  
2. **18:47** BOB tip — kein Bild/Ton; ESP noch ohne `playingUid`  
3. **18:48** Replug → **weiße LED bleibt** (B) → Operator-RST → PD0199  
4. **18:50–18:52** „halb laufend“ / mehrfach Replug → wieder B; Operator: ohne Reset kein Erfolg  
5. **18:54** Replug optisch ok, **ohne Ton** → wieder weiß → wieder ok ohne Ton (= USB da, Ring leer)  
6. **18:55–18:57** Tips: kein `play_uid` (HU-Cache / Mid-Reads)  
7. **18:58–19:00** Cache-Bust OTG: blau→weiß→blau (= Boot PD0214); Tip → Reset PD0215; Abend  

## Erkenntnisse

1. **Last-Kopplung:** Stabiles OTG ohne weiße LED war vor TCP/Stream; mit Bridge/WLAN dominiert Klasse B. Das blockiert O2 bevor Bitrate überhaupt zählt.  
2. **Kein Stream ⇒ kein Fenster:** Instrument und Ohr sind hier nicht „kurz“, sondern **Null** — Hypothese A/B (@32k Hördauer) bleibt unentschieden.  
3. **Play-Detect / Cache:** Mehrfach Tip ohne `play_uid`; Capture zeigt trotzdem Slot-Reads und viele `not_from_head` — HU spielt/scannt Datei, startet aber keinen Pump-Stream.  
4. **Q11:** Reset-Häufigkeit belegt (19 Serials); Brownout vs. Soft-Reset vs. Panic **nicht** diskriminierbar ohne UART.  
5. **nächster Feldschritt:** Versorgung/Steckfestigkeit (Q11 mit UART) **vor** erneutem 32k-Ohrversuch; weniger Steckzyklen; Tip nur bei bestätigtem `playingUid`/`absEnd>0`.

## Artefakte

| Datei | Inhalt |
|-------|--------|
| `OPERATOR-LIVE.txt` / `marks.jsonl` | Operator-Marken |
| `LIVE-WINDOW.txt` + `live-window/` | 49 Episoden, Live-s durchgängig 0 |
| `status-poll.jsonl` | 698 Polls, Serial-Timeline |
| `trace.jsonl` / `msc_reads.jsonl` | MSC ohne Stream-Bytes |
| `bridge-audio.log` | Reconnects/Rejects, 0 audio_start |
| `q8/Q8-REPORT.json` | Resume-/Burst-Muster |

Auswertung: `python3 tools/feld_live_window.py --run …/s5-20261011-184623 --bps 4000`
