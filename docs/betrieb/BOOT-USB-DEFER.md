# Boot & USB (ESP / RTL-SDR)

**Stand:** 2026-09-24 · Pi hat **kein BIOS** — `config.txt`, udev, systemd.

## Betriebsregel (Feldtest)

**Keinen USB-Hub verwenden** für RTL-SDR / ESP am PiDrive.

| Aufbau | Kaltstart |
|--------|-----------|
| RTL (+ ggf. ESP-Serial) **direkt** am Pi-Port | ok (~30–35 s bis SSH) |
| Geräte über **USB-Hub** (auch aktiv) ab Power-on | Boot hängt oft; Hub abziehen → Boot läuft weiter |
| Geräte **nach** erfolgreichem Boot stecken | ok (Hotplug-Release) |

Der Hang mit Hub ist ein **USB-Enumerations-/Bus-Problem**, nicht nur Einsteck-Anlaufstrom
(Pi-Versorgung bleibt, Hub ab → Boot setzt fort).

## Was Software macht

| Was | Wann |
|-----|------|
| WLAN | sofort (SSH) |
| ESP / RTL / QinHeng | udev `authorized=0` beim Add |
| Boot-Freigabe | ~12 s (`pidrive-usb-release`) |
| Hotplug-Freigabe | nach Boot-Release (`pidrive-usb-hotplug-release`, udev `SYSTEMD_WANTS`) |
| Bluetooth | nach Boot-USB-Release |
| `pump_bridge` | nur mit `/dev/ttyACM0`; Start `--no-block` (kein Boot-Deadlock) |

Ohne Hotplug-Service blieb ein Gerät, das **nach** dem einmaligen Boot-Release
gesteckt wurde, dauerhaft bei `authorized=0` → kein `cdc_acm` / kein `/dev/ttyACM0`.

`usbcore.quirks=…:k` hat den **Hub-Kaltstart** nicht gerettet — nicht nötig / wieder entfernen.

## Optional `config.txt`

```
usb_max_current_enable=1
```

## Empfohlener Steckplan

1. Pi einschalten **ohne** Hub  
2. RTL-Stick (und ESP-UART) **direkt** in die Pi-USB-A-Buchsen  
3. ESP-OTG erst wenn System steht, falls nötig  

## Manuell freigeben

```bash
sudo systemctl start pidrive-usb-hotplug-release.service
# oder:
sudo systemctl restart pidrive-usb-release.service
pidrivectl usb status
```

Docs-Index: Boot-Speed siehe [`BOOT-SPEED.md`](BOOT-SPEED.md).
