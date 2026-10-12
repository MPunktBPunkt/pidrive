# Lab-Flash Stall-Build 0.4.47-dev · Ergebnis 2026-10-12

**ESP:** `.88` · Env `pidrive-s3-l3` · OTA von `0.4.46-dev` → **`0.4.47-dev`**

## Ergebnis

| Check | Wert |
|-------|------|
| OTA | OK |
| `version` | `0.4.47-dev` |
| `msc.stall.enable` | **false** (Default) |
| `msc.stall` Telemetrie | vorhanden (`cmds/retries/partials/…`) |
| `volumeLabel` | `PD0409` (= gekoppelt an Serial, Override leer) |
| `config.stallEnable` | false |

SHA256: `1c3819f56807aca3688ba87edd8f3dc66320c2d51dd7748c17e890097a5ef001`  
Artefakt FW: `esp32.pidrive/dist/pidrive.0.4.47-dev.ota.esp32s3.bin`

## Nächste Lab-Schritte

1. `lab_e7_delay_ladder.py --mode A --stall-ready --esp http://192.168.178.88`
2. REPLUG L0 (Stall aus) gegen Golden
3. Stufe B mit `--sg` wenn Host-SG bereit
4. `lab_k3_volume_label.py` Label isolieren

**Feld `.89`:** nicht geflasht (Freeze).
