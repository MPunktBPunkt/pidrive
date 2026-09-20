# Boot: USB-Geräte verzögert freigeben (ESP / RTL-SDR)

**Stand:** 2026-09-20 · Pi hat **kein BIOS** für so etwas — Steuerung über
`/boot/firmware/config.txt`, udev und systemd.

## Problem

ESP und/oder RTL-SDR **von Anfang an** am Bus → Boot hängt oft / kein WLAN.
**Nachträglich** anstecken → ok. Verdacht: 5V-Last + USB-Enumeration parallel zu
WLAN/BT-Firmware.

## Strategie (umgesetzt)

| Was | Wann |
|-----|------|
| WLAN | **sofort** (SSH bleibt) |
| ESP / RTL / QinHeng-Serial | udev `authorized=0` beim Plug → nach **~10 s** freigeben |
| Bluetooth | erst **nach** USB-Release |
| `pidrive_pump_bridge` | nur wenn `/dev/ttyACM0` existiert (+ Hotplug-udev) |

**Nicht** WLAN/BT im Device-Tree dauerhaft abschalten (`disable-wifi` / `disable-bt`) —
dann kein Remote-Debug bis manuell wieder an.

## Dateien

- `udev/80-pidrive-defer-usb.rules`
- `scripts/usb-release.sh`
- `systemd/pidrive-usb-release.service`
- `systemd/bluetooth.service.d/defer-after-usb.conf`

## Optional in `config.txt` (Pi 4/5 Strombudget USB)

```
usb_max_current_enable=1
```

## Test

1. ESP + RTL am Hub **vor** Einschalten stecken  
2. Boot → SSH sollte in ~20 s da sein (ohne USB-Treiber für ESP/RTL)  
3. Nach ~10–15 s: `lsusb` zeigt Geräte, RTL/`ttyACM` nutzbar  
4. `journalctl -u pidrive-usb-release -b`
