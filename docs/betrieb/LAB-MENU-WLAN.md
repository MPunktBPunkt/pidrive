# Lab: Menü über WLAN (ohne Auto)

**Stand:** 2026-09-26 · PiDrive v0.11.169+ · esp32.pidrive **0.4.15-dev**  
**Ziel:** Während ESP/Pi im Auto unhandlich sind, Menü und ESP-Diagnose vom Schreibtisch bedienen — inkl. **Live-PUMP über WLAN**.

---

## 1. PiDrive-Menü (ohne Nav-Tab)

Der frühere Nav-Eintrag **Menü** ist entfernt (kaum genutzt). Route bleibt für Bookmarks/CLI:

| | |
|--|--|
| URL | `http://<pi-ip>:8080/menu` (direkt) |
| ESP suchen | Nav **🚗 Car** → Suchen |
| Daten | `/tmp/pidrive_menu.json` via `GET /api/core` |
| Steuerung | `POST /api/cmd` → `up` / `down` / `enter` / `back` / `activate:<uid>` / `cat:<id>` |

**Bedienung**

- Pfeiltasten oder Buttons ▲▼ OK Back  
- Klick = Cursor setzen (mehrfach `up`/`down`), zweiter Klick / Doppelklick = Enter/Activate  
- Home = `goto:root`

**CLI-Alternative** (ohne Browser):

```bash
pidrivectl menu tree
pidrivectl menu goto root/favoriten
# bzw. Core-Cmds:
printf 'down\n' >> /tmp/pidrive_cmd
```

Das ist der **volle PiDrive-Baum** (wie AVRCP/MPRIS), nicht die 4 MSC-Slots am ESP.

---

## 2. ESP SoftAP (Handy / Laptop am ESP)

Firmware: [`esp32.pidrive`](https://github.com/MPunktBPunkt/esp32.pidrive) · Defaults in `ConfigStore`.

| | Default |
|--|--|
| SoftAP | **an** (`enableSoftAp=true`) |
| SSID | `pidrive-<letzte 6 Hex der MAC>` |
| Passwort | `pidrive12` (≥8 Zeichen) |
| URL | **`http://192.168.4.1/`** |
| STA / WiFiManager | **aus** (Boot wartet nicht auf Heim-WLAN) |
| PUMP TCP | **an** · Port **9090** (gleicher Framing wie UART) |

### Ablauf

1. ESP flashen, SoftAP suchen, verbinden.  
2. Browser: `http://192.168.4.1/`  
3. Tabs: **Remote / Auto-Test / Menü / Events / Config / OTA**  
4. Menü-Tab = **dieselben max. 4 MSC-Slots**, die der USB-Host sieht (Soft-Paging über „Mehr…“).

Ausführlich: [CAR-STANDALONE.md](https://github.com/MPunktBPunkt/esp32.pidrive/blob/main/docs/planung/CAR-STANDALONE.md) · [WEBUI.md](https://github.com/MPunktBPunkt/esp32.pidrive/blob/main/docs/planung/WEBUI.md)

---

## 3. ESP im Heim-WLAN (STA)

Nur wenn du SoftAP und Handy-AP umgehen willst:

1. SoftAP verbinden → Config-Tab.  
2. `STA / WiFiManager = 1` speichern (SoftAP kann parallel bleiben, `AP_STA`).  
3. WiFiManager-Portal bzw. Credentials setzen → ESP bekommt DHCP-IP.  
4. Optional mDNS: `pidrive-<MAC6>.local` wenn `enableMdns` an.  
5. In PiDrive: `usb_esp_host` / `usb_esp_port` (Default-Beispiel `192.168.178.89:80`) für Status-Poll; `usb_pump_tcp_port` = **9090**.

```bash
# vom Pi / Lab-PC
curl -sS http://192.168.178.89/api/status | python3 -m json.tool | head
curl -sS http://192.168.178.89/api/menu | python3 -m json.tool | head
```

---

## 4. Live-PUMP über WLAN (Menü + MP3)

Ab Firmware **0.4.15** und aktueller `pump_bridge.py`:

```bash
# SoftAP: Pi (oder Lab-PC) mit pidrive-… verbinden, dann:
python3 ~/pump_bridge.py --transport tcp --host 192.168.4.1 --tcp-port 9090

# STA: gleiche Settings-IP wie usb_esp_host
python3 ~/pump_bridge.py --transport tcp --host 192.168.178.89 --tcp-port 9090

# auto (systemd-Default): UART wenn /dev/ttyACM0 da, sonst TCP zu usb_esp_host
python3 ~/pump_bridge.py --transport auto
```

PiDrive-Settings:

| Key | Bedeutung |
|-----|-----------|
| `usb_pump_transport` | `auto` \| `uart` \| `tcp` |
| `usb_esp_host` | ESP SoftAP/STA-IP |
| `usb_pump_tcp_port` | Default `9090` |

`systemctl restart pidrive_pump_bridge` — Unit startet ohne UART-Condition.

**Framing:** identisch zu UART (line-JSON + Binär `0x01 0x55`/`0x56`).

---

## 5. Was wofür?

| Ziel | Werkzeug |
|------|----------|
| Voller Menübaum / Sender starten ohne BMW | Pi **`/menu`** oder `pidrivectl menu` |
| 4-Slot-MSC wie Radio-Listing | ESP SoftAP `192.168.4.1` Menü-Tab |
| Play-Detection / Events ohne Pi | ESP SoftAP + OTG an Lab-Host (siehe Phase-0-Lab) |
| Live Pi-Menü auf ESP-Slots **ohne UART** | `pump_bridge --transport tcp` → ESP `:9090` |
| ESP-IP finden (WebUI) | Tab **🚗 Car** → „Suchen“ (`/api/esp/discover`) |
| Live Pi-Menü mit Kabel | UART `/dev/ttyACM0` (weiterhin möglich) |

---

## 6. Typische Stolpersteine

- SoftAP verbunden, aber Seite lädt nicht → IP fest `192.168.4.1`, kein Captive nötig.  
- STA an, SoftAP weg → Config: SoftAP wieder 1; FW stellt SoftAP nach WiFiManager oft wieder her.  
- `/menu` leer → Core down oder `menu_age` hoch; `systemctl status pidrive_core`.  
- ESP-Menü ≠ Pi-Baum → erwartet: ESP zeigt nur aktuelle MSC-Seite.  
- Bridge verbindet nicht → FW ≥0.4.15, Config `PUMP TCP=1`, Port 9090 freigeben; `curl …/api/status` → `pumpTcp`/`pumpTcpPort`.  
- UART und TCP parallel → ein Client reicht; Responses gehen an den Link, der zuletzt gesprochen hat.
