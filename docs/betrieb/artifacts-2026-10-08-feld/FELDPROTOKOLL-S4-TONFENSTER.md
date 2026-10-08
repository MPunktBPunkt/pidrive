# Feldprotokoll s4 — Tonfenster vermessen (ohne FW-Änderung)

Grundlage: [`ANALYSE-S3-TONFENSTER-2026-10-08.md`](ANALYSE-S3-TONFENSTER-2026-10-08.md) (R24/R25 in HU-Facts).
FW-Freeze bleibt: **kein OTA**. Nur Bridge-Parameter, Polls, Bedienung.

## Ziel und Zeitbudget

Das Lab klärt vorher Ringlänge, Bitrate-Leiter, Q12 und den Softwareanteil der Reboots. Im Auto bleiben nur HU-Fragen: **hörbares** Fenster, R28-Gegenprobe, P-Schlüssel und Reboot-Rate. Kernlauf: etwa 15–20 min.

Lab-Gate: [`AUFTRAG-LAB-ABEND-2026-10-08.md`](AUFTRAG-LAB-ABEND-2026-10-08.md). Ohne L0-PASS kein s4-Deployment.

## Vorbereitung zu Hause

1. Abgenommene `pump_bridge.py` nach `/home/pidrive/pump_bridge.py` deployen.
2. Auf dem Auto-Pi:

   ```bash
   cd ~/projects/pidrive/docs/betrieb/artifacts-2026-10-08-feld/feld-s4-prep
   chmod +x *.sh
   ./run-s4.sh 1800
   ```

   Standard: Audio, 48k, 6000 B/s, Zählton 1 s, Status/Trace/Events. Nur eine Bridge darf laufen.
3. Handyvideo auf HU-Display und Ton richten.
4. `./s4-check.sh` und `./mark.sh "…"` per SSH erreichbar halten.

## Gültigkeitsregel R28

Ein Schritt zählt nur, wenn:

1. nach dem Tap `playingUid` zum Sender passt,
2. die Uptime über Unplug und Plug weiterläuft,
3. die HU nach Replug denselben Sender spielt.

`s4-check.sh` vor Tap, nach Tap und nach Plug aufrufen. Bei Reboot, fehlendem Play-Detect oder anderer Autoplay-Wahl den Schritt als ungültig markieren und **einmal** wiederholen.

## Kernlauf

| ID | Aktion | Frage | Zeit |
|---|---|---|---|
| K1 | BOB tippen, 30 s; Replug; „von vorn“; zweimal. Jeweils Marken und Video | Wie viele 1-s-Zähltöne hört die HU: 5–6 oder die im Lab messbaren ~8,2 s? | 4 min |
| K2 | Bayern tippen, `playingUid=fav1` prüfen, 30 s; Replug; von vorn | R28: Bild und Ton auch ohne BOB? | 2–3 min |
| K3 | OTG ab; `./rename.sh fav2 "Radio BOB 1008"`; 2 s warten; OTG an; BOB starten, 30 s; Replug | Ist der Dateiname Teil des P-Schlüssels, beginnt die HU bei 0 statt P | 3–4 min |
| K4 | Name unverändert lassen, erneut Replug | Kontrollfall: dieselbe Identität setzt bei P fort | 2 min |
| K5 | passiv in K1–K4 | Reboot-Rate beim heutigen Zigarettenanzünder-Netzteil | 0 min |

Bei K3 muss das Bridge-Log den neuen `menu_set` zeigen, bevor OTG wieder angesteckt wird. Nach dem Lauf Override entfernen:

```bash
./rename.sh fav2 ""
```

## Optional nach Lab-Ergebnis

| ID | Wann | Aktion |
|---|---|---|
| O1 | Zeit übrig | Rock 30 s + Replug: zweite R28-Gegenprobe |
| O2 | L2 bestätigt 12,3 s bei 32k | Bridge mit `BRIDGE_ARGS='--bitrate 32k --target-bps 4000 --marker --marker-period 1'` neu starten; ein BOB-Lauf |
| O3 | L4 hatte 0 Software-Reboots | 10 Steckvorgänge mit Powerbank/kurzem Kabel (Versorgungs-A/B) |
| O4 | VBUS-Blocker im Lab geprüft | 10 Steckvorgänge mit VBUS-Blocker |
| O5 | Laptop dabei | UART-Bootlog 115200 ohne DTR/RTS; `rst:`-Grund eines Feld-Reboots sichern |

O3–O5 haben Vorrang vor O1/O2, wenn L4 den Softwarepfad entlastet.

## Marken

```bash
./mark.sh "K1 BOB tap"
./mark.sh "K1 unplug"
./mark.sh "K1 plug"
./mark.sh "K1 von vorn Tonbeginn"
./mark.sh "K1 Tonende"
```

Analog K2–K4. Aussagen nach Gehör immer durch Video absichern.

## Ergebnis

| ID | gültig | Play-Detect | kein Reboot | richtige Autoplay-Wahl | Bild | Zähltöne / Ton-s | Start 0 oder P | Bemerkung |
|---|---|---|---|---|---|---|---|---|
| K1a | | | | | | | | |
| K1b | | | | | | | | |
| K2 | | | | | | | | |
| K3 | | | | | | | | |
| K4 | | | | | | | | |

Auswertung: `python3 tools/feld_live_window.py --run <RUN>`. Das Lab-Ergebnis L2 danebenlegen: Ist der PC-Dump ~8,2 s, die HU aber nur 5–6 s hörbar, liegt der Verlust im HU-Anlauf/Formatwechsel und nicht im Ring.
