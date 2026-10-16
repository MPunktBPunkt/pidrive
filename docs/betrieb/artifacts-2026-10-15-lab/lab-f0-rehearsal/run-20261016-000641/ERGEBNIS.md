# F0 Lab-Rehearsal Overnight — `run-20261016-000641`

**Lauf:** 8 Loops × B0 + serial/label/volume-id · ESP `.88` · FW `0.4.51-dev` · `stallEnable=false`

## Ergebnis

| Dimension   | Pass | Fail | Bemerkung |
|-------------|------|------|-----------|
| serial      | 8/8  | 0    | `ensure_stream_quiet` hält Remount stabil |
| volume-id   | 8/8  | 0    | XOR-Flip ok über Nacht |
| label       | 3/8  | 5    | ab Loop 4: `ValueError: target label equals current label` |
| **gesamt**  | 19/24 | 5   | `all_pass=false` |

## Erkenntnis

Label-Mutation war `label[:10] + "X"`. Nach wiederholten Läufen entsteht ein **11-Zeichen-Label** (`PD0461XXXXX`); die nächste Mutation ist identisch → FAIL.

Serial/volume-id sind overnight-fest. Der Label-Fail ist **Tooling**, nicht FW-/MSC-Regression.

## Umsetzung

- `tools/lab_d_campaign.py`: `next_volume_label()` — Append-X bis Länge 11, danach Rotation des letzten Zeichens (A–Z/0–9)
- `feld-f0-prep/f0-identity.sh`: gleiche Logik für Feld-B2
- Self-test deckt 11-Zeichen-Stall und 40er-Kettenmutation ab
