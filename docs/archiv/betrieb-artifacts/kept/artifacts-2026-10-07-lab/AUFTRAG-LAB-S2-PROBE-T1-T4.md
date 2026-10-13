# Auftrag Lab: Probe für Feld s2 (T1–T4)

**Stand:** 2026-10-07 nachmittags · **Für:** Lab-Cursor (LXC mit ESP .88 auf Host .187, Pi für die Bridge)
**FW-Freeze:** keine ESP-Änderung. Nur Sim, Tools und Doku.
**Bezug:** Nachprüfung N1–N4 in [`C1-C7-ERGEBNIS.md`](C1-C7-ERGEBNIS.md), Feldablauf in [`../artifacts-2026-10-07-feld/FELDPROTOKOLL-NAECHSTER-TERMIN.md`](../artifacts-2026-10-07-feld/FELDPROTOKOLL-NAECHSTER-TERMIN.md).

Ziel: Im Feld bleiben nur 30 Minuten. Deshalb muss jedes Werkzeug vorher im Lab gelaufen sein, und die Auswertung muss mit Lab-Daten schon einmal durchgespielt sein.

Reihenfolge: T1 vor T4 (T4 nutzt den Trace-Poll). T2 und T3 sind unabhängig. Nach jedem Test mit Live-Pfad: Soft-RST (`/api/restart`) und ≥ 20 s warten.

---

## T1 — Deckt der Trace-Poll mit 4 Hz jeden Read ab?

**Frage:** Liefert `tools/feld_trace_poll.py` alle READ10 lückenlos? Bremst der Poll die Reads?

```bash
# Terminal 1 (Pi oder Host mit WLAN zum ESP)
python3 tools/feld_trace_poll.py --esp http://192.168.178.88 --hz 4 \
  --out T1/trace.jsonl --seconds 90 --print
# Terminal 2 (LXC)
python3 tools/nbt_hu_sim.py --golden G7 --period-ms 4.0 --out T1/sim
```

Danach den Lauf ohne Poll wiederholen (nur Terminal 2), als Vergleich für die SG-Dauer.

**Auswerten:**
- Trace-Zeilen mit `kind=file` im G7-Zeitraum gegen `reads.jsonl` des Sims und gegen `readCount`-Delta aus `T1/trace.jsonl.polls.jsonl`.
- Summe `lost` in der Polls-Datei.
- `sg_duration p50` mit Poll gegen ohne Poll.

**Abnahme:**
- Lücken 0 (oder < 0,5 % der Reads): Trace taugt für Q8 im Feld.
- `sg_duration p50` mit Poll ≤ ohne Poll + 0,1 ms: Der Poll verfälscht R15 nicht.
- WLAN fällt aus (ENODEV / Timeouts): mit `--hz 3` wiederholen und notieren. Das ist dann die Feld-Einstellung.

---

## T2 — C2-Zelle „armed, aber anderer Slot“

**Frage:** Kostet der Live-Pfad das 1 ms pro Read nur beim Lesen des Live-Slots oder bei jedem Read? Das entscheidet, ob die HU beim Index-Lesen anderer Dateien im Play-Zustand langsamer wird.

```bash
python3 tools/nbt_hu_sim.py --golden BENCH --live fav0 --bench-uid fav1 \
  --bench-sizes 4096 --bench-n 2000 --out T2/armed-fav0-read-fav1
python3 tools/nbt_hu_sim.py --golden BENCH --live fav0 --live-no-producer --bench-uid fav1 \
  --bench-sizes 4096 --bench-n 2000 --out T2/armed-noprod-fav0-read-fav1
```

Je 2× mit Soft-RST dazwischen.

**Abnahme:** In die C2-Tabelle eintragen (`sg_duration p50`):

| Zustand | Ergebnis |
|---------|----------|
| idle | 4,0 ms (C2) |
| armed fav0, Lesen fav0 | 5,0 ms (C2) |
| armed fav0, Lesen fav1 | ? |

- ≈ 4,0 ms: Die Kosten hängen am Live-Slot (Read-Pfad).
- ≈ 5,0 ms: Die Kosten hängen am Zustand (z. B. Producer-Task, Polling im Loop).

---

## T3 — C4b: feste Zuordnung bei Lesen außer der Reihe mit Live-Inhalt

**Frage:** Gilt `abs0 − off = const` auch für Rückwärts-Segmente, wenn der Producer mithält? Im C4-Lauf 1209 waren nur 12 von 1997 Reads LIVE, alle im sequenziellen Kopf.

Der Sim liest das R16-Fenster (F8 B120 B120 F360 B360 F968, 1,98 MB) gedrosselt auf ~1 Read / 700 ms. Das sind ~5,8 KB/s, also knapp langsamer als der Producer (erste ~60 s ~9 KB/s, danach ~6 KB/s bei 48 kbit/s). Ohne den Lauf bis EOF (neue Option `--gw-no-eof`):

```bash
python3 tools/nbt_hu_sim.py --golden GW --live fav0 --live-prefill-s 30 \
  --period-ms 700 --gw-no-eof --out T3/c4b
```

Laufzeit ~484 Reads × 0,7 s ≈ 6 min. Danach die Mapping-Tabelle wie in C4 erzeugen (Ohr: PDSQ-Stempel je Block).

**Abnahme:**
- ≥ 100 LIVE-Reads in Rückwärts-Segmenten.
- `abs0 − off` konstant über alle LIVE-Reads: Das beschreibt das **heutige** Verhalten der FW bei Lesen außer der Reihe. Abweichungen als Tabelle (Segment, Offset, abs0) ablegen; das ist die Testvorlage für die FW nach Go (Stufenplan 3.2).
- Weniger als 100 LIVE: `--period-ms 1000` und `--live-prefill-s 60` nehmen und wiederholen.

---

## T4 — Generalprobe des Feldablaufs s2

**Frage:** Laufen `run-s2.sh`, `mark.sh` und die Auswertung zusammen, und kommt das R16-Muster aus den Lab-Daten wieder heraus?

1. Auf dem Pi: `ESP_HOST=192.168.178.88 ./run-s2.sh 600` (Ordner `feld-s2-prep/`).
2. Zweites Terminal: `./mark.sh "T4 replay start"`.
3. LXC: Replay der Feld-Episode p1-run-a:
   ```bash
   python3 tools/nbt_hu_sim.py --golden REPLAY \
     --replay docs/betrieb/artifacts-2026-10-04-feld/p1-run-a/msc_reads.jsonl \
     --replay-ms-from 364034 --replay-ms-to 365907 --out T4/replay
   ```
4. `./mark.sh "T4 replay ende"`, dann Ctrl-C in `run-s2.sh`.
5. Auswertung:
   ```bash
   python3 tools/feld_q8_msc_order.py --self-test
   python3 tools/feld_q8_msc_order.py --reads <RUN>/msc_reads.jsonl --trace <RUN>/trace.jsonl --out-dir <RUN>/q8
   ```

**Abnahme:**
- Der Lauf-Ordner enthält `msc_reads.jsonl`, `trace.jsonl`, `trace.jsonl.polls.jsonl`, `status-poll.jsonl`, `bridge-noaudio.log`, `marks.jsonl`.
- `feld_q8_msc_order.py` zeigt das Muster `F8 B120 B120 F360 B360 F968`. Das gilt sowohl mit `--trace` als auch nur mit `--reads`; ohne Trace müssen beide Sprung-Bursts als `resolved` gemeldet werden.
- Die Marken liegen zeitlich korrekt um die Replay-Episode (über `wall` in den Polls).
- Nach Ctrl-C läuft `pidrive_pump_bridge` wieder.
- Laufzeit des Aufbaus bis zum ersten Lebenszeichen unter 1 min. Das ist das Budget im Feld.

---

## Rückmeldung

Kurzbericht `T1-T4-ERGEBNIS.md` neben diesem Auftrag:
- Tabelle T1–T4 (PASS/FAIL, Kennzahlen);
- die C2-Zelle aus T2;
- die C4b-Tabelle aus T3;
- die empfohlene Poll-Rate (4 oder 3 Hz) für das Feld.
