# Menü-Ergonomie (Skip-Only)

**Stand:** v0.11.127 · 2026-09-15

Kennzahl: minimale Tastendrücke (`down`/`enter`, kein `back`) vom Wurzelmenü
bis zum Ziel. „Zurueck“-Einträge zählen als normale Knoten.

## Vorher-Stand (Baseline vor M4)

| Kennzahl | Wert |
|----------|------|
| Blätter | 171 |
| Median-Kosten | 15 |
| Mittel | 16.1 |
| Max-Kosten | 40 |
| Min-Kosten | 2 |
| Blätter mit Kosten > 20 | 41 |
| Unerreichbar (info) | 16 |

### Top 10 teuerste Ziele

| Kosten | Tiefe | Pfad | Label |
|--------|-------|------|-------|
| 40 | 4 | `root/sources/dab/dab_stations/dab_0xd30a` | antenne1 |
| 38 | 4 | `root/sources/dab/dab_stations/dab_0x100f` | bigFM |
| 37 | 4 | `root/sources/dab/dab_stations/dab_0x140a` | Radio Seefunk |
| 36 | 4 | `root/sources/dab/dab_stations/dab_0xd70d` | Radio Ton |
| 35 | 4 | `root/sources/dab/dab_stations/dab_0xd30e` | ROCK FM |
| 34 | 4 | `root/sources/dab/dab_stations/dab_0xd308` | RADIO REGENBOGEN |
| 33 | 4 | `root/sources/dab/dab_stations/dab_0xd40d` | HITRADIO OHR |
| 32 | 4 | `root/sources/dab/dab_stations/dab_0xda08` | DONAU 3 FM |
| 31 | 4 | `root/sources/dab/dab_stations/dab_0xd50c` | die neue welle |
| 31 | 4 | `root/sources/fm/fm_stations/fm_105_4` | B5 aktuell  105.4 MHz |

### Unerreichbare Info-Knoten (B5)

- `root/connections/wifi_netze/wifi_hint` — Zuerst scannen
- `root/connections/wifi_status` — SSID: <WIFI_SSID>
- `root/sources/scanner/uhf/uhf_info` — 400.000 MHz
- `root/sources/scanner/vhf/vhf_info` — 136.000 MHz
- `root/sources/scanner/cb/cb_info` — kein Kanal aktiv
- `root/sources/scanner/lpd433/lpd433_info` — kein Kanal aktiv
- `root/connections/bt_last` — Letztes: <BT_LAST>
- `root/sources/scanner/freenet/freenet_info` — kein Kanal aktiv
- `root/connections/bt_status` — Geraet: <BT_DEVICE>
- `root/sources/scanner/pmr446/pmr446_info` — kein Kanal aktiv
- `root/connections/bt_state` — Bluetooth: <BT_STATE>
- `root/connections/bt_geraete/bt_hint` — Zuerst scannen
- `root/sources/spotify/spot_status` — Status: <SPOTIFY_STATE>
- `root/system/sys_ip` — IP: <IP>
- `root/audio_out/ao_status` — Ausgang: <OUTPUT>
- `root/favoriten/fav_empty` — Noch keine Favoriten

### Blätter mit Kosten > 20 (41)

- 40: `root/sources/dab/dab_stations/dab_0xd30a`
- 38: `root/sources/dab/dab_stations/dab_0x100f`
- 37: `root/sources/dab/dab_stations/dab_0x140a`
- 36: `root/sources/dab/dab_stations/dab_0xd70d`
- 35: `root/sources/dab/dab_stations/dab_0xd30e`
- 34: `root/sources/dab/dab_stations/dab_0xd308`
- 33: `root/sources/dab/dab_stations/dab_0xd40d`
- 32: `root/sources/dab/dab_stations/dab_0xda08`
- 31: `root/sources/dab/dab_stations/dab_0xd50c`
- 31: `root/sources/fm/fm_stations/fm_105_4`
- 30: `root/sources/dab/dab_stations/dab_0x130a`
- 30: `root/sources/fm/fm_stations/fm_105_2`
- 29: `root/sources/dab/dab_stations/dab_0x1702`
- 29: `root/sources/fm/fm_stations/fm_87_9`
- 29: `root/sources/webradio/web_stations/web_bayern_3`
- 28: `root/sources/fm/fm_stations/fm_102_3`
- 28: `root/sources/webradio/web_stations/web_radio_paradise`
- 27: `root/sources/dab/dab_stations/dab_0xd30b`
- 27: `root/sources/fm/fm_stations/fm_100_7`
- 27: `root/sources/webradio/web_stations/web_1000_rockhits_(laut.`
- 26: `root/sources/dab/dab_stations/dab_0x1014`
- 26: `root/sources/dab/dab_stations/dab_0x1014`
- 26: `root/sources/fm/fm_stations/fm_98_7`
- 26: `root/sources/webradio/web_stations/web_metal_(laut.fm)`
- 25: `root/sources/dab/dab_stations/dab_0x1b2e`
- 25: `root/sources/dab/dab_stations/dab_0x1b2e`
- 25: `root/sources/fm/fm_stations/fm_97_3`
- 25: `root/sources/webradio/web_stations/web_classic_rock_(laut.f`
- 24: `root/sources/dab/dab_stations/dab_0xd519`
- 24: `root/sources/fm/fm_stations/fm_96_7`
- … und 11 weitere

## Messung wiederholen

```bash
pidrivectl menu report
pidrivectl menu cost sources/dab/dab_stations/<id>
```

Nach M4 hier einen Abschnitt **Nachher** ergänzen (nicht überschreiben).
