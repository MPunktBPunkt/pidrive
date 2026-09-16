# Golden Master — Menübaum

**Stand:** v0.11.127 · 2026-09-15

`menu_tree.json` ist der normalisierte Snapshot des vollständigen PiDrive-Menübaums.
Er wird von `pidrivectl menu verify` gegen den aktuellen Baum geprüft.

## Befehle

```bash
pidrivectl menu snapshot          # schreibt nur wenn noch keine Datei existiert
pidrivectl menu snapshot --accept # ersetzt Snapshot + CHANGES.md-Eintrag
pidrivectl menu verify            # Exit 1 bei Verlusten oder Action-Änderungen
pidrivectl menu lint              # statische Prüfungen
```

## Maskierungsregeln (dynamische Labels)

| Muster | Ersetzung |
|--------|-----------|
| `IP: …` | `IP: <IP>` |
| `Ausgang: …` | `Ausgang: <OUTPUT>` |
| `Bluetooth: …` | `Bluetooth: <BT_STATE>` |
| `Status: aktiv/inaktiv` | `Status: <SPOTIFY_STATE>` |
| `> Name` / `* Name` (BT-Geräte) | `<BT_PREFIX>Name` |
| `Geraet: …` | `Geraet: <BT_DEVICE>` |
| `Letztes: …` | `Letztes: <BT_LAST>` |
| `SSID: …` | `SSID: <WIFI_SSID>` |
| `Ordner: …` | `Ordner: <LIB_FOLDER>` |
| `Alle: …` | `Alle: <LIB_NAME>` |
| `★ …` / Favoriten-Präfix | `<FAV_PREFIX>…` |

## Bekannte Lint-Warnungen

Keine (Stand 2026-09-16): doppelte Station-IDs behoben (Config-`id`), leere Actions und
`path_id#N`-Kollisionen sind Lint-**Fehler**.
