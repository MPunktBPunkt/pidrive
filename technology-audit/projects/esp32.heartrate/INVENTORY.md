# esp32.heartrate — Technologie-Inventar

Audit-Lauf: 2026-10-08 · Commit `72acae4`

| Kategorie | Technologie | Konfidenz | Belege |
|-----------|-------------|-----------|--------|
| `embedded` | ESP32 (D1 Mini) + ESP32-S3, PlatformIO Arduino | hoch | `platformio.ini`, Envs `heartrate` / `heartrate-s3` |
| `bt-media` | BLE Central, HR Service 0x180D, NimBLE | hoch | `src/ble/BleCentral.cpp`, `HrParser.cpp`, README |
| `bt-peripheral` | HR-Relay GATT Server 0x180D / 0x2A37 (nur S3) | hoch | `src/ble/HrServer.cpp`, `-DHR_RELAY=1`, `docs/PFLICHTENHEFT-v0.3-RELAY.md` |
| `web-ui` | HTTP REST + eingebettete UI + SSE `/events` | hoch | `src/web/UiPages.h`, README API-Tabelle |
| `network` | WiFi, mDNS `hr-XXXXXX.local`, Hub HTTP | hoch | `HubClient.cpp`, README Quickstart |
| `config` | WiFiManager Hotspot, ConfigStore (NVS) | hoch | `ConfigStore.cpp`, lib_deps WiFiManager |
| `storage` | LittleFS Session-Archiv (64 Sessions) | hoch | `SessionArchive.cpp`, README |
| `embedded` | RR-Pipeline, Beat-Timeline, Quality-Labels | hoch | `BeatTimeline.cpp`, `SessionSeries.cpp`, PFLICHTENHEFT v0.2 |
| `network` | Web-OTA `POST /ota-upload`, Hub-gesteuertes OTA | mittel | `HubClient.cpp` (`performOta`), README |
| `network` | Session-Export JSON/CSV → Hub | hoch | README Hub-IO, `POST /api/session/export/send` |
| `ci-test` | GitHub Actions: PlatformIO Matrix-Build | hoch | `.github/workflows/build.yml` |

## Priorisierte Sheets

| Priorität | Sheet | Reife |
|-----------|-------|-------|
| 1 | [ble-central-nimble-hrm](sheets/ble-central-nimble-hrm.yaml) | L2 |
| 2 | [ble-peripheral-hr-relay](sheets/ble-peripheral-hr-relay.yaml) | L2 |
| 3 | [web-sse-rest-ui](sheets/web-sse-rest-ui.yaml) | L2 |
| 4 | [esp-hub-integration](sheets/esp-hub-integration.yaml) | L2 |

## Nächste Schritte (L3)

- [ ] Feldnotizen Polar H9 + Relay mit Radcomputer verlinken
- [ ] Continuity-KPIs vs. PFLICHTENHEFT Abnahmekriterien abgleichen
- [ ] Cross-Link zu PiDrive BLE/AVRCP (anderes Profil, gleiche NimBLE-Erfahrung)
