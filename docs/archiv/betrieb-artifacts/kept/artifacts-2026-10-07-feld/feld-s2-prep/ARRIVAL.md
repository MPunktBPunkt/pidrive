# Arrival — Feld s2 (30 min)

**Protokoll:** [`../FELDPROTOKOLL-NAECHSTER-TERMIN.md`](../FELDPROTOKOLL-NAECHSTER-TERMIN.md) · Pocket: [`GO.md`](GO.md)
**FW:** 0.4.46-dev Freeze — **kein Stall-OTA**
**ESP:** `.89` · L3

## Vorher (zu Hause)

```bash
cd /home/martin/projects/pidrive
git pull   # Commit 0d671bf (oder: tar xf …/SYNC-TO-PI.tgz -C ~/projects/pidrive)
# Stick-MP3s liegen fertig unter feld-s2-prep/f1-stick/ (espeak-ng, BR=128k)
# USB-Stick mounten, dann:
./docs/betrieb/artifacts-2026-10-07-feld/feld-s2-prep/copy-f1-to-stick.sh /mnt/stick
# kurz anhören: Marker „0“, „10“…
chmod +x docs/betrieb/artifacts-2026-10-07-feld/feld-s2-prep/*.sh
```

Einpacken: Pi, USB-1.1-Hub, Stick mit `F1-5MB_128k.mp3` + `F1-100MB_128k.mp3`, Handy-Halter, ESP-Kabel.

## Am Auto

| Min | Terminal 1 | Terminal 2 / HU |
|-----|-----------|-----------------|
| 0 | Video + Sekundenuhr starten | — |
| 1 | `./run-s2.sh 2400` | — |
| 2 | Lebenszeichen prüfen (alle 10 s) | `./mark.sh "s2 start"` |
| 3–12 | läuft | A+C-Zyklus 3×: BOB 10 s → RST 15 s → Rock 60 s → RST 20 s |
| 12–21 | läuft | E: Hub + Stick, 100MB / 5MB / 100MB je 30 s, dann ESP zurück |
| 21–25 | läuft | B: Bayern bis Ende, Autoplay auf Rock, 60 s |
| 25–30 | Ctrl-C (Snap + Dienst-Neustart automatisch) | `./mark.sh "s2 ende"` |

RST: `curl -s -m 3 -X POST http://192.168.178.89/api/restart`
Vor jeder Bedienung: `./mark.sh "<Schritt>"`.

## Danach

```bash
RUN=$(ls -d s2-* | tail -n 1)
python3 /home/martin/projects/pidrive/tools/feld_q8_msc_order.py \
  --reads $RUN/msc_reads.jsonl --trace $RUN/trace.jsonl --out-dir $RUN/q8
```

## Stall-Go

Nur wenn **F1 entschieden** und **Q8/R10** geklärt — siehe Entscheidungstabellen im Protokoll.
