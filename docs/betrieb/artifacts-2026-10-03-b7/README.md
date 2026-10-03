# Artefakte B7 — Auto 2026-10-03

**FW Auto:** `0.4.36-dev` · **ESP:** `.89` · **Bridge:** Pi `.105`  
**Lab `.88`:** parallel `0.4.37-dev` L0 (nicht Auto)

## Passes

| Ordner | Serial | Inhalt |
|--------|--------|--------|
| `replug-1231-noselect/` | PD0028 | OTG ~12:31 „keine Auswahl“ → HU Autoplay fav1→fav0→fav2 (Cover+Kurzton); später Cache-Playlist |
| `fav0-123818/` | **PD0029** | **B7-A** 150 s Rock Antenne: Stille, kein Cover, Fortschritt; kein `playingUid`; `rc` flat nach Mount; Playlist weiter silent (BOB→Bayern) |

## Verdict (eng)

Ist-Geometrie (~2 MiB / 512 KiB-Slots): **Mount-Scan + HU-Cache**. Keine fortlaufenden Play-Reads über 150 s. Play-Detection oft leer bei Cache-Wiedergabe. Kleine `rc`-Anstiege nur bei Trackwechseln (Stub-Nachlese), `streamBytes` nicht live.

**Nächster Schritt:** L0/`0.4.37` OTA Auto **nach** diesem Push (Geometrie/L-Leiter) — nicht Ring.
