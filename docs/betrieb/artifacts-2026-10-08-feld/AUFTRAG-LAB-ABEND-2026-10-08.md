# Auftrag Lab-Abend · 2026-10-08

Ziel: Das Lab übernimmt alle langen und automatisierbaren Prüfungen. Der Feldtest s4 bleibt auf HU-spezifische Fragen beschränkt.

**Aufbau:** Lab-ESP `.88`, FW 0.4.46-dev, L3. OTG und UART hängen am Proxmox-Debian-PC; die Bridge läuft auf dem Lab-Pi und verbindet sich per TCP.  
**Sollwerte:** [`AUFTRAG-LAB-REALITAET-2026-10-08.md`](AUFTRAG-LAB-REALITAET-2026-10-08.md).  
**Ausgabe:** `docs/betrieb/artifacts-2026-10-08-lab/lab-abend-<HHMM>/`, darin `ERGEBNIS-LAB-ABEND.md`, Logs und Dumps.

## Vorbereitungen

```bash
cd ~/projects/pidrive
OUT="docs/betrieb/artifacts-2026-10-08-lab/lab-abend-$(date +%H%M)"
mkdir -p "$OUT"
ESP=http://192.168.178.88
SG=/dev/sg0
ls -l "$SG"
curl -fsS "$ESP/api/status" | tee "$OUT/status-start.json"
```

Vor Schreib-/Lesezugriffen mit `lsblk -S` verifizieren, dass `$SG` und das zugehörige Blockgerät wirklich der ESP sind. Keine Systemplatte verwenden.

## L0 — Werkzeugabnahme (hartes Gate)

### L0.1 Simulator

```bash
python3 tools/nbt_hu_sim.py --self-test |& tee "$OUT/l0-self-test.log"
sudo python3 tools/nbt_hu_sim.py --golden ALL --sg "$SG" \
  --out "$OUT/l0-all" |& tee "$OUT/l0-all.log"
```

Soll: `self-test PASS`, danach alle G1–G5 PASS. Bei FAIL: **Stop**, Ursache im Lab beheben; keine neuen Werkzeuge ins Auto übernehmen.

### L0.2 Bridge

Auf dem Lab-Pi nur eine Bridge laufen lassen:

```bash
sudo systemctl stop pidrive_pump_bridge
python3 /home/pidrive/pump_bridge.py --transport tcp --host 192.168.178.88 \
  --bitrate 48k --target-bps 6000 --re-local \
  --marker --marker-period 1 |& tee /tmp/lab-bridge-l0.log
```

Prüfen:

1. ffmpeg startet und beendet sich nicht sofort.
2. `absEnd` wächst über 10 s um `60 000 ± 2 000` B.
3. Lokale Quelle zeigt im Bridge-Log `re`.
4. Marker steht als `marker=1s` im Log.

### L0.3 Namens-Override

Bei abgestecktem OTG:

```bash
cat >/tmp/pidrive-name-overrides.json <<'JSON'
{"fav2":"Radio BOB LAB 1008"}
JSON
```

Bridge mit `--name-override-file /tmp/pidrive-name-overrides.json` starten. Nach `menu_set` OTG wieder autorisieren und Root-Verzeichnis über SG/Blockgerät lesen. Soll: `Radio BOB LAB 1008` erscheint; `uid` und Slot-Geometrie bleiben unverändert. Datei anschließend leeren (`{}`) und Rückkehr zum Originalnamen prüfen.

## L1 — REPLUG-Referenz, je drei Wiederholungen

Parallel Trace starten:

```bash
python3 tools/feld_trace_poll.py --esp "$ESP" --hz 4 \
  --out "$OUT/l1-trace.jsonl" --seconds 1800 >"$OUT/l1-trace.log" 2>&1 &
TRACE_PID=$!
```

Dann:

```bash
for K in 4 16 64; do
  for R in 1 2 3; do
    sudo python3 tools/nbt_hu_sim.py --golden REPLUG --sg "$SG" \
      --replug-cmd-kib "$K" --head-pause-ms 19 --period-ms 5.1 \
      --producer-burst 1.0 --replug-prefill-s 12 --replug-id3-bytes 3300 \
      --dump-slot --out "$OUT/l1-${K}k-r${R}" \
      |& tee "$OUT/l1-${K}k-r${R}.log" || break 2
  done
done
kill "$TRACE_PID" 2>/dev/null || true
```

Abnahme:

- 4 KiB: 524 288 B, 128 Callbacks, Ring voll, `undDelta ≈ expect_undDelta`, M2-Identität ±4096 B.
- `sg_ms_per_4k.p50`: 5,0–5,1 ms Ziel, 4,0–5,6 ms zulässig.
- 16/64 KiB: im Trace Gruppen von 4/16 Callbacks prüfen. Kein entsprechendes Feldraster stärkt Q10 = 4 KiB, beweist es aber nicht.
- Alle drei Wiederholungen müssen dieselbe Klassifikation liefern.

## L2 — Echtes Audio, Dump und Bitrate-Leiter

Für jede Bitrate Bridge auf dem Lab-Pi neu starten, `target_bps = Bitrate/8`, Marker an. Beispiel 48k:

```bash
python3 /home/pidrive/pump_bridge.py --transport tcp --host 192.168.178.88 \
  --bitrate 48k --target-bps 6000 --marker --marker-period 1
```

Producer per Body-Read auslösen, 15 s füllen lassen, dann den 512-KiB-Slot ab Kopf lesen. LBAs vorher aus `/api/status` übernehmen; L3 fav2 beginnt bei 17489:

```bash
for i in 1 2 3 4; do
  sudo dd if=/dev/sdX of=/dev/null bs=512 skip=$((17489 + 8*i)) count=8 iflag=direct status=none
done
sleep 15
sudo dd if=/dev/sdX of="$OUT/l2-48k.bin" bs=4096 count=128 \
  iflag=direct,skip_bytes skip=$((17489*512)) status=progress
```

Für `24k 32k 48k 64k 96k` wiederholen, Target-B/s `3000 4000 6000 8000 12000`.

Automatische Auswertung:

```bash
for F in "$OUT"/l2-*.bin; do
  ffprobe -v error -select_streams a -show_frames \
    -show_entries frame=pkt_pos,pkt_size,best_effort_timestamp_time,sample_rate,channels \
    -of csv "$F" >"${F%.bin}-frames.csv"
  ffmpeg -v error -i "$F" -f null - 2>"${F%.bin}-decode-errors.txt"
  ffmpeg -hide_banner -i "$F" -af silencedetect=n=-45dB:d=0.5 \
    -f null - 2>"${F%.bin}-silence.txt"
done
```

Sollfenster aus 48 KiB: 24k = 16,4 s; 32k = 12,3 s; 48k = 8,2 s; 64k = 6,1 s; 96k = 4,1 s. In `frames.csv` die Grenze 22,05 kHz mono (Live) → MPEG-1-Stille dokumentieren. Dumps aufheben und später am PC anhören.

## L3 — Play-Detect-Ablehnung Q12

### Nach RST

```bash
curl -fsS -X POST "$ESP/api/restart" -d '{}' || true
sleep 40
sudo python3 tools/nbt_hu_sim.py --golden GW --sg "$SG" \
  --gw-pos 245760 --gw-no-eof \
  --out "$OUT/l3-after-rst" |& tee "$OUT/l3-after-rst.log"
curl -fsS "$ESP/api/events" >"$OUT/l3-after-rst-events.json"
```

### Kontrolle ohne RST

```bash
sleep 40
sudo python3 tools/nbt_hu_sim.py --golden GW --sg "$SG" \
  --gw-pos 245760 --gw-no-eof \
  --out "$OUT/l3-no-rst" |& tee "$OUT/l3-no-rst.log"
curl -fsS "$ESP/api/events" >"$OUT/l3-no-rst-events.json"
```

Auswerten: `play.guess` oder `play.reject` samt Detail (`not_from_head`, Prefetch usw.), `playingUid`, Zahl und LBA der Reads. Q12 ist geklärt, wenn der Ablehnungsgrund reproduzierbar ist.

## L4 — Reboot-Stress, Softwareanteil Q11

Serielles Gerät ermitteln:

```bash
ls -l /dev/serial/by-id/
SER=/dev/serial/by-id/<ESP-UART>
```

**DTR/RTS nicht toggeln**, sonst erzeugt das Öffnen selbst einen Reset. Geeignet ist ein kleines pyserial-Logging mit `dtr=False`, `rts=False`; alternativ `stty -F "$SER" 115200 -hupcl -crtscts` und `cat "$SER"`. Erst Log starten, dann einmal kontrollieren, dass dadurch die Uptime nicht springt.

```bash
stty -F "$SER" 115200 raw -echo -hupcl -crtscts
stdbuf -oL cat "$SER" | ts '%Y-%m-%dT%H:%M:%.S' >"$OUT/l4-uart.log" &
UART_PID=$!
```

OTG-Gerät eindeutig über `udevadm info` bestimmen. Nicht versehentlich die UART-Buchse deautorisieren:

```bash
OTG_DEV=1-2   # vor Ausführung ersetzen und prüfen
for I in $(seq 1 200); do
  echo 0 | sudo tee "/sys/bus/usb/devices/$OTG_DEV/authorized" >/dev/null
  sleep 1
  echo 1 | sudo tee "/sys/bus/usb/devices/$OTG_DEV/authorized" >/dev/null
  sleep 3
  curl -fsS "$ESP/api/status" >>"$OUT/l4-status.jsonl" || true
done
kill "$UART_PID" 2>/dev/null || true
```

Parallel müssen TCP-Audio und Producer laufen. Auswertung:

```bash
grep -E 'rst:|Guru Meditation|Brownout|watchdog' "$OUT/l4-uart.log" \
  | tee "$OUT/l4-reset-lines.txt"
```

- 0 Reboots in 200 Zyklen: USB-Softwarepfad als Ursache unwahrscheinlich; Versorgungshypothese im Feld priorisieren.
- Panic/Watchdog: vollständigen Boot-/Backtraceblock sichern.
- `BROWN_OUT_RST`/`POWERON`: Versorgung, auch im Lab.

Falls `uhubctl` den OTG-Port einzeln schalten kann: zusätzlich 50 echte VBUS-Zyklen mit serieller Aufzeichnung; Ergebnis getrennt ausweisen.

## L5 — Langlauf über Nacht

Dauer 3–4 h. Producer 6000 B/s; Status 1 Hz. Alle 5 min einen REPLUG-Lauf (4 KiB) und danach Remount ausführen. Jeden Zyklus in einen eigenen Ordner schreiben.

```bash
END=$((SECONDS + 4*3600))
N=0
while (( SECONDS < END )); do
  N=$((N+1))
  sudo python3 tools/nbt_hu_sim.py --golden REPLUG --sg "$SG" \
    --replug-cmd-kib 4 --period-ms 5.1 --producer-burst 1.0 \
    --out "$OUT/l5-r$(printf '%03d' "$N")" \
    |& tee "$OUT/l5-r$(printf '%03d' "$N").log" || break
  sleep 300
done
```

Ziel: kein ESP-Reboot, kein Producer-Fehler, jeder Lauf vollständig, M2-Identität erfüllt. Heap-Drift nur bewerten, falls der aktuelle Status eine Heap-Metrik enthält; sonst „nicht messbar“ statt PASS notieren.

## Abbruchregeln

- L0 FAIL: keine weiteren neuen Werkzeuge und kein Deployment ins Auto.
- SG verschwindet wiederholt oder Linux meldet Reset: Lauf stoppen, Kernel-Log sichern.
- ESP-Reboot in L1/L2/L3: Episode ungültig, Reset-Grund sichern, einmal wiederholen.
- Zwei identische Infrastrukturfehler: nicht blind weiterlaufen; Befund dokumentieren.

## Ergebnisvorlage `ERGEBNIS-LAB-ABEND.md`

```markdown
# Ergebnis Lab-Abend

| Block | Ergebnis | Artefakt | Entscheidung fürs Feld |
|---|---|---|---|
| L0 Self-Test/ALL | | | |
| L0 Bridge/Override | | | |
| L1 REPLUG 4/16/64 | | | Q10-Kandidat: |
| L2 Dump 24–96k | | | PC-Fenster: |
| L3 Q12 | | | Reject-Grund: |
| L4 200 USB-Zyklen | | | Software/Versorgung: |
| L5 Langlauf | | | |

Reboots: ___ / ___; Reset-Gründe: ___
Offene Blocker vor s4: ___
Freigabe der Werkzeuge für s4: JA / NEIN
```
