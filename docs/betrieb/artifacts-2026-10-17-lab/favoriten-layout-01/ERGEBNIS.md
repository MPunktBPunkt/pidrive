# Favoriten-Layout (Autoplay-Trennung) · Lab

**FW:** `0.4.53-dev` · ESP `.88` · OTA ☑  

## Soll

Erste HU-Seite = **nur Ordner** (wie Produktiv-PiDrive-Wurzel), Live-Dateien unter `Favoriten/` für Stall/ID3.

```
/ (Root)
├── Favoriten/     ← station MP3s (fav0…fav2)
└── Menue/         ← action stub (pump:page_next)
```

## Nachweis (CT100 FAT-List)

| Pfad | Namen |
|------|--------|
| `/` | `Favoriten`, `Menue` (keine Titel-MP3s) |
| `/Favoriten` | Rock Antenne, Rock Antenne Bayern, Radio BOB! |
| `/Menue` | Menue.mp3 |

API `slotMap.path`: `FAVORITEN/0x.MP3` / `MENUE/04.MP3`.

## Folge

- Autoplay-Futter nicht mehr auf der Root-Seite.
- Stall/ID3 gezielt auf Dateien unter Favoriten.
- Soft-Cycle-Geometrie (LBA-Cluster) unverändert — nur DIR-Namen/Pfade.
