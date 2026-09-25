# Lab: Menü über WLAN (ohne Auto)

**Stand:** 2026-09-25 · PiDrive v0.11.169+  
**Ziel:** Während ESP/Pi im Auto unhandlich sind, Menü und ESP-Diagnose vom Schreibtisch bedienen.

---

## 1. PiDrive-Menü im Browser (iDrive-Baum)

Voraussetzung: Core läuft (`pidrive_core`), WebUI erreichbar.

| | |
|--|--|
| URL | `http://<pi-ip>:8080/menu` |
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
5. In PiDrive: `usb_esp_host` / `usb_esp_port` (Default-Beispiel `192.168.178.89:80`) für Status-Poll.

```bash
# vom Pi / Lab-PC
curl -sS http://192.168.178.89/api/status | python3 -m json.tool | head
curl -sS http://192.168.178.89/api/menu | python3 -m json.tool | head
```

**Wichtig:** Live-Menü vom Pi → ESP-Slots braucht weiterhin **UART + `pump_bridge.py`**. WLAN ersetzt SoftAP-Diagnose, nicht PUMP.

---

## 4. Was wofür?

| Ziel | Werkzeug |
|------|----------|
| Voller Menübaum / Sender starten ohne BMW | Pi **`/menu`** oder `pidrivectl menu` |
| 4-Slot-MSC wie Radio-Listing | ESP SoftAP `192.168.4.1` Menü-Tab |
| Play-Detection / Events ohne Pi | ESP SoftAP + OTG an Lab-Host (siehe Phase-0-Lab) |
| Live Pi-Menü auf ESP-Slots | Pi + ESP per UART + `pump_bridge` |

---

## 5. Typische Stolpersteine

- SoftAP verbunden, aber Seite lädt nicht → IP fest `192.168.4.1`, kein Captive nötig.  
- STA an, SoftAP weg → Config: SoftAP wieder 1; FW stellt SoftAP nach WiFiManager oft wieder her.  
- `/menu` leer → Core down oder `menu_age` hoch; `systemctl status pidrive_core`.  
- ESP-Menü ≠ Pi-Baum → erwartet: ESP zeigt nur aktuelle MSC-Seite.
