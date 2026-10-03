# Artefakte B7 — Auto 2026-10-03

**FW Auto (Ende):** `0.4.39-dev` FAT12 L0 4 MiB / 1 M-Slots · **ESP:** `.89` · Serial **PD0032** · **Bridge:** Pi `.105`  
**Lab `.88`:** früher `0.4.37` L0-Smoke

## Passes

| Ordner | Serial | Inhalt |
|--------|--------|--------|
| `replug-1231-noselect/` | PD0028 | OTG ~12:31 „keine Auswahl“ → HU Autoplay fav1→fav0→fav2 (Cover+Kurzton); später Cache-Playlist |
| `fav0-123818/` | **PD0029** | **B7-A** 150 s Rock Antenne (`0.4.36`): Stille, kein Cover; Mount-Scan + Cache; kein `playingUid` |
| `l0-replug-1246/` | PD0031? | OTA/Replug Zwischenstand Richtung L0 |
| `l0-039-replug-1253/` | **PD0032** | **0.4.39** Listing wieder da (3 Dateien); Deep-Prefetch ~3 MiB; Selects 12:56 LED kurz, kein Ton/Cover |
| `l0-039-bob-1257/` | PD0032 | 12:57 „Radio BOB!“ 30 s: Counter flat, `guess=0`, phase `quiet` |
| `l0-039-rock-1301/` | PD0032 | 13:01 Rock Antenne (HU **3. Stelle**) 30 s: **kein Ton, LED nicht blinkend**; Counter unverändert seit Prefetch |

## Slot-Namen vs. HU-Reihenfolge (0.4.39)

ESP `slotMap`: `fav0` Rock Antenne · `fav1` Rock Antenne Bayern · `fav2` Radio BOB!  
HU zeigt offenbar **umgekehrt** (BOB oben, Rock Antenne unten) — Select trifft trotzdem keinen Live-Read.

## Verdict (eng)

1. **Listing (L0/FAT12):** ok — 3 Stationen sichtbar.  
2. **Play:** HU prefetch’t mid-file (`play.reject` `not_from_head`/`plug_window`), geht in `quiet cache?`, spielt Stub **ohne** weitere MSC-Reads → **kein** `play.guess`, **kein** Live-Overlay, **kein** Ton/Cover.  
3. **LED quiet bei Select** = kein USB-Xfer → bestätigt Cache-Wiedergabe, kein Detect-Bug allein.

**Nächster Schritt (nicht Ring):** Play-Pfad öffnen — z. B. Detect auch bei fortlaufendem Mid-File nach Prefetch armieren **oder** Geometrie/Stub so, dass HU nicht die ganze Slot-Datei cachen kann und erneut from-head / sequentiell liest. L-Leiter erst wenn Play-Reads nachweisbar.

## Weiter (kurz)

1. Docs/Artefakte gepusht (dieser Ordner).  
2. FW-Idee: `playDetect` nach Prefetch-Cooldown Mid-Seq akzeptieren **oder** Slot-Größe/Stub so erhöhen, dass Cache nicht reicht.  
3. Feld erst wieder nach Lab-Smoke der Detect-/Geometrie-Änderung.
