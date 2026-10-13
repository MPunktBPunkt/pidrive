# Lab-Runbook: D-Startgate / HU-A1 / Identity

**Ziel:** Die langen, automatisierbaren Mechaniktests laufen im Lab. Der kurze
NBT-Termin entscheidet anschließend nur noch Resume-/Cachewirkung und das
D-Startgate. Das Runbook flasht keine Firmware und sendet kein RF.

## Topologie

- ESP32-S3 OTG und zweite USB-/UART-Buchse: Proxmox-Debian-PC.
- OTG-MSC: `/dev/sg0`, zugehöriges Ganzgerät z. B. `/dev/sdb`.
- UART: z. B. `/dev/ttyACM0`; nicht mit einem Client öffnen, der DTR/RTS beim
  Start toggelt.
- Pi und ESP: TCP wie im Auto.
- Alle Befehle im Root von `pidrive-main` auf dem Debian-PC ausführen.

Gerätenamen vor jedem Abend mit `lsscsi -g`, `lsblk` und `udevadm info`
bestätigen. Niemals `/dev/sdb` aus einem alten Lauf ungeprüft übernehmen.

## 1. Offline- und Preflight-Gate

```bash
python3 tools/nbt_hu_sim.py --self-test
python3 tools/lab_d_campaign.py --self-test
python3 tools/lab_d_campaign.py preflight \
  --esp http://192.168.178.88 --sg /dev/sg0 --uart /dev/ttyACM0
python3 -m pip install -r tools/requirements-lab.txt
python3 tools/lab_uart_reset_log.py --port /dev/ttyACM0 \
  --esp http://192.168.178.88 --seconds 120 --out artifacts/uart-q11
```

PASS verlangt eine stabile USB-Identity und zwei erfolgreiche OTG-Statuspunkte
um einen echten SG READ(10). Das Tool öffnet den UART absichtlich nicht:
Viele Terminalprogramme toggeln DTR/RTS und erzeugen damit genau den Reset, den
wir untersuchen wollen. `lab_uart_reset_log.py` setzt DTR/RTS bereits vor dem
Öffnen auf inaktiv und entfernt unter Linux `HUPCL`/`CRTSCTS`; sein PASS
bedeutet trotzdem nur „kein Reset während dieses Logger-Laufs“, nicht
„Stromversorgung bewiesen“. Die zugehörige Firmwareänderung veröffentlicht
`uptimeMs`, `resetReason` und `resetReasonCode`; dadurch wird ein Reboot im
Preflight und in der Dauerstrom-Zeitreihe sichtbar.

## 2. HU-A1: S6-Prefetch-Replay

Jeder Lauf beginnt mit einer eigenen, definierten Remount-Episode. Die drei
Klassen werden **getrennt** gefahren:

```bash
python3 tools/lab_d_campaign.py replay --selection no-read \
  --esp http://192.168.178.88 --esp-ip 192.168.178.88 --sg /dev/sg0 --device /dev/sdb

python3 tools/lab_d_campaign.py replay --selection mid \
  --esp http://192.168.178.88 --esp-ip 192.168.178.88 --sg /dev/sg0 --device /dev/sdb

python3 tools/lab_d_campaign.py replay --selection head \
  --esp http://192.168.178.88 --esp-ip 192.168.178.88 --sg /dev/sg0 --device /dev/sdb
```

Der Ablauf ist fest:

1. `fav1` live + Ring-Prefill,
2. `fav1` Head-Reads,
3. `fav0` non-live bis 8.294.400 B (S6: 98,88 %),
4. Marker,
5. `fav0` als no-read, Mid-Read oder Head-Read,
6. Byteklassifikation und Status-Endpunkt.

Wichtige Artefakte:

- `run-manifest.json`: Run-ID, Git-Commit, Host, Parameter und Ergebnis,
- `run.yaml`: kanonisches Ingest-Manifest mit OTG-/UART-Geräten und
  `dtr_rts: false`,
- `events.jsonl`: gemeinsame monotone Zeitachse,
- `status-poll.jsonl`: Status **während** des Dauerstroms,
- `reads.jsonl`: SG-Kommandos mit CDB, Blockzahl, Transferlänge, Residue,
  Sense/Host/Driver-Status und klassifiziertem Inhalt,
- `A1-REPORT.json`: beobachtete Klasse und `gate_green`,
- Boot-/Root-Sektor samt SHA-256, wenn `--device` gesetzt ist.

`gate_green=true` bedeutet im Lab ausschließlich: Head-Read, S7 armed und
LIVE-Bytes. Es ist noch kein NBT-Resume-P-Beweis.

## 3. Identity-Matrix bei P≫0

Zuerst den maschinenlesbaren Plan erzeugen:

```bash
python3 tools/lab_d_campaign.py identity-plan
```

Die heute zur Laufzeit sauber isolierbaren Dimensionen:

```bash
python3 tools/lab_d_campaign.py identity --dimension volume-id --device /dev/sdb
python3 tools/lab_d_campaign.py identity --dimension label --device /dev/sdb
python3 tools/lab_d_campaign.py identity --dimension serial --device /dev/sdb
```

Das Gate schlägt fehl, wenn neben der deklarierten Dimension ein weiteres
Identity-Feld driftet oder das reale Blockdevice nicht zum ESP-Status passt.

Dateigröße, Pfad und Startcluster brauchen getrennte Firmware-/Geometrie-Builds.
Sie werden im Plan ausdrücklich als `build-variant-required` geführt und nicht
durch Labels oder Dateinamen vorgetäuscht. Pro Feldlauf wird nur eine Variante
verwendet. **Identity-Rotation und Head-Force nie kombinieren.**

## 4. BOT-Evidenz richtig lesen

Die Arduino-MSC-Callbacks bleiben auf typischerweise 4 KiB begrenzt. Diese
Callbackgröße ist **keine** CDB-/READ(10)-Länge. `reads.jsonl` protokolliert
deshalb am SG-Kontrollhost zusätzlich:

- vollständige READ(10)-CDB,
- angeforderte Blockzahl und Transferlänge,
- SCSI-, Host- und Driver-Status,
- Residue und Sense-Daten.

Die ESP-Felder `msc.xfer` und `mscTrace` sind ergänzende Device-Sicht, aber kein
Ersatz für CBW/CDB/CSW. Ein echter NBT-BOT-Claim bleibt ohne transparenten
Capture im Fahrzeug `UNKNOWN`. `msc.transportEpoch` zählt sichtbare
Plug-/Remount-Episoden; weil Arduino USBMSC keinen BOT-Reset-Callback
bereitstellt, meldet die Firmware zusätzlich `botResetObservable=false`.
Der Transport-Epoch darf daher nicht als BOT-Reset-Zähler zitiert werden.

## 5. Abbruch- und Feld-Gates

- Bei Identity-Drift, SG-Fehler, UART-/ESP-Reset oder gemischten Runs abbrechen.
- D1–D3 erst nach reproduzierbarem Head/armed/LIVE-Start im Lab und kurzem F0.
- Resume-P, Cache-Hit/Eviction, NBT-Menüphase und Fahrzeug-VBUS/Masse werden
  nicht aus dem Debian-Lab abgeleitet.
- Offset→Audio-Timeline und `maxMs`-Feintuning folgen erst nach grünem
  D-Hauptpfad.
