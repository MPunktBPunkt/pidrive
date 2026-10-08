# Auftrag Lab-Realität · 2026-10-08

Ziel: Das Lab (Lab-ESP .88, FW 0.4.46-dev, Geometrie L3, Lab-Pi als HU-Ersatz) so einstellen, dass es den **Feld-Replug aus s3** byte- und zeitgenau nachstellt. Danach lassen sich Varianten (Kommandogröße, Bitrate, Bremsen) im Lab vorprüfen, bevor das Auto dran ist.
**Ohne ESP-Firmware-Änderung.** Grundlage: [`ANALYSE-STREAM-WEG-2026-10-08.md`](ANALYSE-STREAM-WEG-2026-10-08.md), HU-Facts R24–R27, Q10.

**Aktuelle Ausführungsreihenfolge:** Für den heutigen, automatisierten Komplettlauf gilt
[`AUFTRAG-LAB-ABEND-2026-10-08.md`](AUFTRAG-LAB-ABEND-2026-10-08.md).
Dieses Dokument bleibt die Referenz für REPLUG-Befehle und M1/M2-Sollwerte.

Werkzeuge (neu, lokal nicht ausgeführt — erst `--self-test` auf dem Lab-Pi):

| Werkzeug | Neu |
|---|---|
| `pidrive/tools/nbt_hu_sim.py` | `--golden REPLUG`, `--replug-cmd-kib 4/16/64`, `--head-pause-ms`, `--replug-prefill-s`, `--replug-id3-bytes`, `--producer-burst`, `--cmd-timeout-ms`, `--dump-slot`; REPORT mit `undDelta`, `abs_cross_fw`, `identity_diff`, `live_span`, `sg_ms_per_4k` |
| `esp32.pidrive/tools/pump_bridge.py` | `--target-bps`, `--re-local`, `--marker-period` (Zählton), `--name-override-file` (P-Schlüssel-Test) |

## 0. Vorbereitung

```bash
cd ~/projects/pidrive
python3 tools/nbt_hu_sim.py --self-test          # muss "self-test PASS" melden
curl -s http://192.168.178.88/api/status | python3 -m json.tool | grep -E '"version"|lba0|lba1|uid'
```

- FW 0.4.46-dev, L3: `fav2` = LBA 17489…18512 (512 KiB). Abweichung → LBAs unten anpassen.
- Feld-Bridge auf dem Lab-Pi **stoppen** (Simulator und Bridge teilen sich sonst Pump-Port 9090).

## 1. REPLUG-Nachbau (Simulator-Producer, PDSQ-Stempel)

Der Simulator spielt den Producer selbst (6000 B/s, `burst 1.0` wie im Feld), wartet 12 s (Ring voll), liest dann `fav2` wie die HU nach dem Replug.

```bash
for K in 4 16 64; do
  sudo python3 tools/nbt_hu_sim.py --golden REPLUG --sg /dev/sg0 \
    --replug-cmd-kib $K --head-pause-ms 19 --period-ms 5.1 \
    --replug-prefill-s 12 --replug-id3-bytes 3300 --dump-slot \
    --out docs/betrieb/artifacts-2026-10-08-lab/replug-${K}k
done
```

Parallel (zweites Terminal) den ESP-Trace mitschneiden, um das Callback-Muster je Kommandogröße zu sehen:

```bash
python3 tools/feld_trace_poll.py --esp http://192.168.178.88 --hz 4 \
  --out docs/betrieb/artifacts-2026-10-08-lab/replug-trace.jsonl --seconds 300
```

### Sollwerte (aus Feld s3, M1/M2)

| Größe (REPORT.json → `REPLUG`) | Feld s3 | Soll Lab (4 KiB) | Bemerkung |
|---|---|---|---|
| `bytes` / `commands` | 524 288 / 128 Callbacks | 524 288 / 128 | 16 KiB: 1 + 32, 64 KiB: 1 + 8 Kommandos |
| `read_ms` | 651–665 | 640–700 | 4 KiB + 19 ms + 127 × 5,1 ms ≈ 672 |
| `sg_ms_per_4k.p50` | 5,0–5,1 (Abstand) | 4,0–5,6 | Lab N1: 5,0 ms bei laufendem Stream |
| `ring_pre` | 49 152 | ≥ 48 128 (`ring_full_pre`) | sonst `--replug-prefill-s` erhöhen |
| `live_bytes_file` | 49 2xx–49 6xx | 49 152 + Zuwachs (≤ 450 B) | „Live“ = Ring + Zuwachs bis Überholen |
| `live_s_at_48k` | 8,2 | 8,2–8,3 | |
| `undDelta` | 470 616–471 640 | ≈ 471 3xx (= `expect_undDelta` ± 4096) | hängt an ID3-Länge; Feld-ID3 3,1–3,5 KB |
| `identity_diff` | 0 ± Poll | 0 ± 4096 (`identity_ok`) | `hostAbs_nach − undΔ` gegen PDSQ-Ende |
| `live_span.seq_gaps` | — | 0 | Lücken = Ring hat während des Reads überschrieben |
| `id3Len_dump` vs. `id3Len_fw` | — | gleich | prüft den Kopf |

**Auswertung Kommandogröße (Q10-Referenz):** Im Trace zeigt jeder 16-/64-KiB-Kommando 4 bzw. 16 Callbacks im ~4,8-ms-Takt und dazwischen eine längere Lücke (CSW → neues CBW). Feld s3 (R26) hatte unregelmäßige 6-ms-Abstände ohne 16er-Raster. Das Lab-Muster, das dem Feld-Trace am nächsten kommt, ist der beste Kandidat für Q10 — **kein Beweis**, der kommt nur per Sniffer.

**Varianten (je ein Lauf, `--replug-cmd-kib 4`):**

- `--producer-burst 1.45` → Ring füllt schneller, `live_bytes_file` gleich, aber `seq_gaps` prüfen.
- `--replug-prefill-s 4` → Ring halb voll: `live_s_at_48k` ≈ 4 s (Erklärung „nur zuletzt getappter Sender“).
- `--cmd-timeout-ms 1000` → heute ohne Wirkung (ESP antwortet in ms); wird relevant mit Stall-Build.

## 2. Dump am PC hören (echtes Audio statt PDSQ)

Der PDSQ-Dump aus Schritt 1 ist kein hörbares MP3. Für den Hörvergleich die **echte Bridge** an den Lab-ESP hängen und den Slot mit `dd` lesen — genau der Feldablauf s3 (Tap startet den Stream, Replug liest ihn).

```bash
# Terminal A: Bridge gegen Lab-ESP, Feldrate erzwingen, Zählton 1 s
python3 tools/pump_bridge.py --transport tcp --host 192.168.178.88 \
  --bitrate 48k --target-bps 6000 --marker --marker-period 1
# Terminal B: "Tap" = fav2-Body lesen (startet play_uid → Bridge → ffmpeg), dann warten
for i in 1 2 3 4; do
  sudo dd if=/dev/sda of=/dev/null bs=512 skip=$((17489 + 8*i)) count=8 iflag=direct 2>/dev/null
done
sleep 15
# "Replug" = fav2 komplett ab 0; bs=4096 → 4-KiB-Kommandos (Startsektor über die Byte-Angabe)
sudo dd if=/dev/sda of=slot-fav2.bin bs=4096 count=128 iflag=direct,skip_bytes skip=$((17489*512))
```

Alternative ohne Block-Device: `/api/lab/play` + `/api/lab/overlay_read?off=…&n=8192` (Feldprotokoll s4, Lab-Auftrag 1) — verschiebt ebenfalls den Host-Cursor, misst aber nicht den USB-Pfad.
`lba0` = 17489 ist nicht durch 8 teilbar, deshalb `skip_bytes`. Block-Device prüfen (`lsblk`), nicht die Systemplatte erwischen. Startet die Bridge nach den vier Body-Reads nicht (`[audio] ffmpeg …` fehlt im Log), Play-Detect-Schwellen in `/api/config` prüfen (`playMinSeqBytes`).

Am PC:

```bash
ffmpeg -v error -i slot-fav2.bin -f null - 2> decode-errors.txt   # Fehler/Formatwechsel
ffprobe -v error -show_frames -select_streams a slot-fav2.bin | grep -E "sample_rate|channels" | uniq -c
ffplay -autoexit slot-fav2.bin                                     # anhören, Zähltöne zählen
```

Erwartung: ~8,2 s Ton mit Zählton (Tonhöhe steigt je Piep, jeder 10. Piep lang), danach Stille. Der Wechsel 22,05 kHz mono (Live, `FF F3`) → 48 kHz stereo (Stille, `FF FB`) ist im `ffprobe` sichtbar.
**Frage an den PC-Test:** Wie viele Zähltöne sind hörbar? 8 → der PC-Decoder spielt den vollen Ring, die 5–6 s im Auto liegen an der HU (Anlauf/Formatwechsel). < 8 → das Problem steckt schon im Datenstrom.

## 3. Lokale Datei in Echtzeit (Producer wie ein Sender)

Lokale Dateien liefen bisher ohne `-re` mit ~8,8 kB/s (Token-Bucket 9000 B/s); im Feld kommt ein Sender mit 6000 B/s.

```bash
python3 tools/pump_bridge.py --transport tcp --host 192.168.178.88 \
  --bitrate 48k --re-local --marker --marker-period 1
```

Prüfen: `absEnd` wächst um 6000 ± 200 B/s (`curl …/api/status` zweimal im Abstand von 10 s). Danach Schritt 2 mit einer lokalen Datei wiederholen.

## 4. Bitrate-Leiter am PC (Vorbereitung s4)

Schritt 2 mit `--bitrate 32k` und `--bitrate 96k` (dazu `--target-bps` = Bitrate/8). Soll: 12,3 s bzw. 4,1 s Ton im Dump. Bestätigt die Tabelle 3.3 der Stream-Analyse ohne Auto.

## 5. Ergebnis ablegen

`docs/betrieb/artifacts-2026-10-08-lab/ERGEBNIS-LAB-REALITAET.md`: Tabelle Sollwerte ↔ Ist je Kommandogröße, Trace-Muster je Größe, gezählte Töne PC je Bitrate, Abweichungen. Bei PASS der 4-KiB-Variante ist `--golden REPLUG` die Lab-Referenz für den Stall-Build ([`STALL-BUILD-SPEC`](../../planung/STALL-BUILD-SPEC-2026-10-08.md)).
