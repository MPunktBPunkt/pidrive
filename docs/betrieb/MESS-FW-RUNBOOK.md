# Mess-FW Runbook (`0.4.52-mess`)

Ziel: READ10-Kommandogröße (Q10), Lücken (`gap_us`), Busy-Retries und Soft-USB-Situationen messen — ohne physisches OTG-Ziehen.

## Soft-USB vs OTG-Power

| Aktion | API | Was passiert | VBUS |
|--------|-----|--------------|------|
| Soft USB detach/cycle | `POST /api/lab/usb` / situation `usb_cycle` | TinyUSB `tud_disconnect`/`tud_connect` (D+-Pull-up) | **nein** |
| Media remount | `POST /api/lab/remount` / `media_remount` | `MSC.mediaPresent` false→true, optional neue Serial | **nein** |
| Physisches OTG / Auto | Kabel / Host-Power | echter Power-Zyklus | **ja** |

## Flash

```bash
cd ~/projects/esphub/esp32.pidrive
pio run -e pidrive-s3-mess -t upload   # oder OTA
```

Version in `/api/status`: `0.4.52-mess`, `mess.build=mess`, `cmdCapture=true`.

## Host-Tool

```bash
ESP=http://192.168.178.88   # Lab
python3 tools/mess_hu_capture.py --esp "$ESP" status
python3 tools/mess_hu_capture.py --esp "$ESP" reset
python3 tools/mess_hu_capture.py --esp "$ESP" sit usb_cycle --hold-ms 600
python3 tools/mess_hu_capture.py --esp "$ESP" q10 --sit usb_cycle --wait 20 -o /tmp/q10.json
python3 tools/mess_hu_capture.py --esp "$ESP" dump -o /tmp/mess-cmds.json
```

## Situationen (`POST /api/lab/situation`)

| name | Wirkung |
|------|---------|
| `usb_cycle` | Stop Stream → Soft-Detach → Auto-Attach nach `holdMs` |
| `usb_detach` / `usb_attach` | Soft-Bus aus / an |
| `media_remount` | SCSI-Medium-Hide (wie Lab-Remount); `keepIdentity` optional |
| `stop` | Stream/Play stoppen |
| `stall_on` / `stall_off` | Stall-Config + optional `maxMs` / `scope` |
| `identity` | Remount mit neuer USB-Serial |
| `mark` | Marker in Capture-Ring (`mark` String) |
| `reset_capture` | Ring leeren |

## Capture-Felder (`msc.cmd` / `/api/lab/mess`)

Pro rekonstruiertem READ10/WRITE10: `t0_us`, `dur_us`, `gap_us`, `lba`, `bytes`, `blocks`, `chunks`, `busy`, `tag`.

`blocks` = gelieferte Bytes/512 nach `tud_msc_read10_complete_cb` — das ist der Q10-Pfad (nicht der 4‑KiB-Callback-Histogramm).

## Pump-Bridge

Bei verbundener Bridge erscheinen Events `op=msc.cmd` neben `msc.reads`.
