# Lab · Station Play/Stop-Untermenü · 2026-10-11

**ESP:** `.88` · FW **0.4.46-dev** Freeze · Host `.187` · Bridge `--station-submenu fav2` @32k  
**Spec:** [`STATION-PLAY-STOP-MENU-SPEC-2026-10-11.md`](../../../planung/STATION-PLAY-STOP-MENU-SPEC-2026-10-11.md)

## Ein Satz

**PASS:** Play-Arm (`pump:arm:fav2`) startet Prefill ohne Live-Read; nach Ringfüllung liefert Head-Read auf `Radio BOB!` ID3+Live-Bytes — **ohne OTG-Replug**, **0 Soft-Resets**.

## Ergebnis

| Check | Ist |
|-------|-----|
| MSC-Map | `Radio BOB!` · `Play Radio BOB!` · `Stop` · `Menue` |
| Arm | `lab/play` → Bridge `[audio] ARM fav2 → prefill` · 1× `audio_start` |
| Prefill | `stream_active` · absEnd/ring ≈ 44 KiB @32k |
| Live head-read 64 KiB | ID3 ja · nonzero ≈ 62 KiB · `live_like` |
| Soft-Reset | nein (Serial stabil in-run) |
| Stop | ausgeführt |

## Menü-Geometrie

Slot0 = großer FAT-File → **Live zuerst**, Play/Stop als kurze Nav-Stubs. Sonst landet Live auf ~4–8 KiB und ist unbrauchbar.

## Lab vs. Feld

| | Lab | Feld |
|--|-----|------|
| Arm-Trigger | SoftAP `lab/play` (= `play_uid`) | HU tippt **Play** (nach `indexSettled`) |
| Live | Host `dd` ab Live-LBA | HU tippt **Radio BOB** |
| msc-lock | aus (Map wechseln) | an, einmal mit Submenu sealen |
| Remount-mit-Stream | weiter `remount_skip` | nicht nötig wenn Live-Tip reicht |

## Bridge-Änderungen (`esphub` `pump_bridge.py`)

- `--station-submenu UID`
- `play_uid=pump:arm:<uid>` → Prefill, kein Nav-Stop
- erneuter Tip auf dieselbe Live-`uid` → **kein** Re-`audio_start` (Ring bleibt)

## Artefakte

`run.py` · `summary.json` · `series.json` · `bridge.log` · `live-head.bin`

## Offen

- Echter MSC-Tip auf Play nach Remount (indexSettled) als eigener Probe  
- Mehrere Sender über **Menue**-Seiten im Auto  
- Stall/Dauerstrom unverändert Freeze
