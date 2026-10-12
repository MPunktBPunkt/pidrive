# Lab · Remount unter Stream-Last · 2026-10-09

**ESP:** `.88` · FW **0.4.46-dev** (Freeze) · Host `.187`  
**Frage:** Hängt Soft-Reset / weiße LED an TCP/Stream-Last beim Remount — oder eher am physischen OTG/VBUS (Feld-Beobachtung vorm Abend)?

## Ein Satz

API-Remount rebootet den Lab-ESP **nicht** (Idle, Peer-only, Play→Stop→Remount @48k/@32k: **0 Soft-Resets**). Während aktivem Stream **skippt** die FW Remount absichtlich (`msc.remount_skip`). Feld-Resets bleiben Versorgungs-/VBUS-Kandidat.

## Ergebnis

| Arm | n | Remount vor | Soft-Resets | Stream |
|-----|---|-------------|-------------|--------|
| Idle (kein Peer) | 10 | 7 HTTP-OK + 3 Timeout (Serial trotzdem ↑ PD0360→PD0370) | **0** | aus |
| Peer-only 48k (Bridge, kein `lab/play`) | 10 | 8 | **0** | aus, Peer `.187` |
| Remount bei `stream_active` | 15 Versuche | **skip** (`msc.remount_skip`) | **0** | an |
| Play→Stop→Remount 48k | 10 | 9/10 | **0** | kurz an (absEnd ~15–21 KiB), dann Stop |
| Play→Stop→Remount 32k | 5 | 5/5 | **0** | kurz an (~13–16 KiB), dann Stop |

Uptime durchgängig ~21 h → PD0401; freeHeap-Min ~101 KiB.

## FW-Hinweis

[`UsbMscGadget::remountMedia`](file:///home/martin/projects/esphub/esp32.pidrive/src/msc/UsbMscGadget.cpp): bei `stream_->active()` sofort return + Event `msc.remount_skip` / `streaming`. Lab kann OTG-während-Stream **nicht** per API nachstellen; physisches VBUS im Auto bleibt die andere Klasse.

## Deutung für Feld-Abend

1. **Softwarepfad/TCP allein** erklärt die Auto-Resets **nicht** (Lab 0 Soft-Resets unter Peer + nach Live-Stream).
2. Deine Beobachtung „ohne Peer OTG ok / mit Stream OTG Reset“ bleibt **plausibel über Stromlast + VBUS-Umschalten** (Q11), nicht über Soft-Panic.
3. Nächster Feldgewinn: UART `rst:` beim nächsten Klasse-B-Steck; wenig Stecken unter Stream.

## Artefakte

| Datei | Inhalt |
|-------|--------|
| `run-stream-remount.py` | Idle + erste Load-Versuche |
| `run-load-play-stop-remount.py` | PSR-Arme |
| `idle.jsonl` / `idle-summary.json` | Idle |
| `load48k-peer-only*.json*` | Peer ohne Play |
| `load48k-psr*` / `load32k-psr*` | Play→Stop→Remount |
| `psr-summary.json` / `summary.json` | Aggregate |
| `run.log` / `run-psr.log` | Konsolen |

## Nicht gemacht

- Physisches OTG / `authorized` (RO) / UART Brownout  
- Ohr @32k an der HU  
- Stall / OTA  
