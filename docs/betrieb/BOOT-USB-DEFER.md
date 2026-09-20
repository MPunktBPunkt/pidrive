# Boot & USB (ESP / RTL-SDR)

**Stand:** 2026-09-20 · Pi hat **kein BIOS** — `config.txt`, udev, systemd.

## Betriebsregel (Feldtest)

**Keinen USB-Hub verwenden** für RTL-SDR / ESP am PiDrive.

| Aufbau | Kaltstart |
|--------|-----------|
| RTL (+ ggf. ESP-Serial) **direkt** am Pi-Port | ok (~30–35 s bis SSH) |
| Geräte über **USB-Hub** (auch aktiv) ab Power-on | Boot hängt oft; Hub abziehen → Boot läuft weiter |
| Geräte **nach** erfolgreichem Boot stecken | ok |

Der Hang mit Hub ist ein **USB-Enumerations-/Bus-Problem**, nicht nur Einsteck-Anlaufstrom
(Pi-Versorgung bleibt, Hub ab → Boot setzt fort).

## Was Software noch macht

| Was | Wann |
|-----|------|
| WLAN | sofort (SSH) |
| ESP / RTL | udev `authorized=0`, Freigabe ~10–12 s (`pidrive-usb-release`) |
| Bluetooth | nach USB-Release |
| `pump_bridge` | nur mit `/dev/ttyACM0`; Start `--no-block` (kein Boot-Deadlock) |

`usbcore.quirks=…:k` hat den **Hub-Kaltstart** nicht gerettet — nicht nötig / wieder entfernen.

## Optional `config.txt`

```
usb_max_current_enable=1
```

## Empfohlener Steckplan

1. Pi einschalten **ohne** Hub  
2. RTL-Stick (und ESP-UART) **direkt** in die Pi-USB-A-Buchsen  
3. ESP-OTG erst wenn System steht, falls nötig  

Docs-Index: Boot-Speed siehe [`BOOT-SPEED.md`](BOOT-SPEED.md).
