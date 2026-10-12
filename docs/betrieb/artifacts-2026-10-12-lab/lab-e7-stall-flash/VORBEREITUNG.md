# Lab-Flash Stall-Build 0.4.47-dev · Vorbereitung 2026-10-12

**Ziel:** Lab-ESP `.88` mit Stall-fähiger L3-FW flashen. Defaults: `stallEnable=false` (= 0.4.46-Verhalten).  
**Nicht:** Feld `.89` / Auto-OTA.

## Build

```bash
cd ~/projects/esphub/esp32.pidrive
export PATH="$HOME/.platformio/penv/bin:$PATH"
pio run -e pidrive-s3-l3
cp .pio/build/pidrive-s3-l3/firmware.bin dist/pidrive.0.4.47-dev.ota.esp32s3.bin
sha256sum dist/pidrive.0.4.47-dev.ota.esp32s3.bin | tee dist/pidrive.0.4.47-dev.ota.esp32s3.sha256
```

## OTA Lab `.88`

```bash
curl -fsS --max-time 180 -F firmware=@dist/pidrive.0.4.47-dev.ota.esp32s3.bin \
  http://192.168.178.88/ota-upload
# warten ~15 s, dann:
curl -s http://192.168.178.88/api/status | python3 -c \
  "import sys,json; d=json.load(sys.stdin); print(d.get('version'), (d.get('msc') or {}).get('stall'))"
```

Soll: `version=0.4.47-dev`, `msc.stall.enable=false`.

## Danach

```bash
# Config-Leiter (noch ohne SG)
python3 tools/lab_e7_delay_ladder.py --mode A --stall-ready --esp http://192.168.178.88 --dry

# Volume-Label isolieren
python3 tools/lab_k3_volume_label.py --esp http://192.168.178.88 --label PIDRIVE2 --dry

# REPLUG L0 (Stall aus) dann Stufe B mit --sg
```

**Freeze Auto:** Stall im Feld weiter nur mit explizitem Go.
