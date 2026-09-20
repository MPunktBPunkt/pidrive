# Boot: USB-Geräte verzögert freigeben (ESP / RTL-SDR)

**Stand:** 2026-09-20 · Pi hat **kein BIOS** — `config.txt`, cmdline, udev, systemd.

## Zwei verschiedene Probleme

| Situation | Bedeutung |
|-----------|-----------|
| Stick **nach** Boot stecken → ok | Einsteck-Impuls / Hotplug oft unkritisch |
| Stick **schon beim Einschalten** → Pi kommt nicht | Last + USB-Enumeration ab t=0 (nicht nur Anlaufstrom) |

Software (`authorized=0`) allein hat den Kaltstart-Hang **nicht** zuverlässig verhindert.
Deshalb zusätzlich: Kernel **IGNORE-Quirk** (`:k`) für ESP/RTL beim Boot, Freigabe ~10 s später.

## Strategie

| Was | Wann |
|-----|------|
| WLAN | sofort (SSH) |
| ESP / RTL / QinHeng | cmdline `usbcore.quirks=…:k` → Kernel ignoriert → nach ~10 s Quirks leeren + Hub-Rebind |
| Bluetooth | nach USB-Release |
| `pump_bridge` | nur mit `/dev/ttyACM0` |

## Wenn es trotzdem hängt

Dann ist es sehr wahrscheinlich **5V-/Controller-Physik** (Hub speist Ports ab Netz-an).
Software kann Ports nicht „aus“ schalten, bevor der Kernel läuft.

Pragmatisch:
1. **RTL/ESP erst stecken, wenn Web/SSH da ist** (~30–40 s), oder  
2. Hub mit **Port-Power** (`uhubctl`, Genesys oft) — Ports soft-an nach Boot, oder  
3. Stärkere/kürzere Versorgung Pi + Hub getrennt prüfen

## Dateien

- `scripts/usb-boot-quirks-install.sh` → `cmdline.txt`
- `udev/80-pidrive-defer-usb.rules`
- `scripts/usb-release.sh`
- `systemd/pidrive-usb-release.service`

## Test Kaltstart mit Stick

```bash
sudo bash scripts/usb-boot-quirks-install.sh   # einmalig
sudo reboot   # Stick + Hub schon an
# nach ~40s SSH:
lsusb
journalctl -u pidrive-usb-release -b
vcgencmd get_throttled
```
