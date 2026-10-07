# Arrival — Feld s2 (Q8 + F1)

**Protokoll:** [`../FELDPROTOKOLL-NAECHSTER-TERMIN.md`](../FELDPROTOKOLL-NAECHSTER-TERMIN.md)  
**FW:** 0.4.46-dev Freeze — **kein Stall-OTA**  
**ESP:** `.89` · L3

## Vor dem Auto (Laptop/Pi)

```bash
# F1-Stick bauen (auf Pi mit espeak-ng für Sprache; sonst Beep-Fallback)
cd /home/martin/projects/pidrive
sudo apt-get install -y espeak-ng   # falls fehlt
python3 tools/feld_f1_make_stick.py --out-dir /mnt/stick --sizes 5mb,100mb
# Kurzsmoke: --sizes 30s --dry-blocks 3
```

USB-1.1-Hub + Stick mit `F1-*.mp3` einpacken.

## Am Auto (Reihenfolge)

| # | Aktion |
|---|--------|
| 1 | NTP / Uhr: `timedatectl` |
| 2 | Video+Sekundenuhr **vor** erster Auswahl starten |
| 3 | `./run-bridge-noaudio.sh` — prüfen: `[msc.reads]` erscheint bei HU-Reads; `ov` notieren |
| 4 | `./run-status-poll.sh 3600` |
| 5 | `./run-f1-log.sh` / OPERATOR-LIVE |
| 6 | Teile **A→C** (ESP), dann Stick umstecken für **E** (F1) |
| 7 | Nach jedem Teil: `./snap-msc-reads.sh A` (oder B/C/…) |
| 8 | Nach Hause: `./run-q8.sh path/msc_reads-A.jsonl` · `./run-ingest.sh` |

## Lesetakt-Gegenprobe (Lab C2)

Mit Bridge `--no-audio` kann der Takt vom nackten s1-morgen abweichen. Pro Phase `readCount`-Steigung:

| Zustand | s1-morgen Soll |
|---------|----------------|
| kein Play | ~250 Reads/s |
| `playingUid` gesetzt | ~195 Reads/s |

## Stall-Go

Nur wenn **F1 entschieden** und **Q8/R10** (Teil A) geklärt — siehe Protokoll-Entscheidungstabellen.
