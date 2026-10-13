# Korrektur zu feld-s1-morgen und den Statusberichten vom 07.10.

**Stand:** 2026-10-07 · Bezug: [`GESAMTBERICHT-FELD-S1-MORGEN.md`](GESAMTBERICHT-FELD-S1-MORGEN.md), [`F1-F2-AUSWERTUNG.md`](F1-F2-AUSWERTUNG.md), Statusbericht Mistral + GPT (2026-10-07)
**Quelle der Nachrechnung:** [`status-poll.jsonl`](status-poll.jsonl) (1 Hz, Rohdaten inkl. Fehlerzeilen bei RST)

Drei Aussagen aus Bericht und Peer-Reviews halten der Prüfung an den Rohdaten nicht stand.

---

## K1 — „BOB überlebt den RST im HU-Cache“ ist ein Poll-Artefakt

**Behauptet:**
- F1-F2-AUSWERTUNG: „F2c RST → BOB: `fav2=524288` früh, rc flach“, Label `cache_hit_like`.
- Mistral: daraus ein HU-Cache-Budget (512 KiB passt, 8 MiB nicht) und die Regel „Live-Slot > HU-Cache-Budget“.
- GPT: „BOB zeigt mindestens einen klaren cache-hit-like-RST-Fall“.

**Tatsächlich:** Nach einem ESP-RST stehen alle ESP-Zähler auf 0. Steht im **ersten** gültigen Poll nach dem RST (Uptime 2–3 s) schon eine vollständige Datei mit `maxSeq` = Dateigröße, dann hat die HU sie **in diesen 2–3 s frisch per USB gelesen**. Die Poll-Lücke während des RST (Connection refused) hat den Burst verdeckt. Das 3-s-Fenster von `d_readCount` in `play-transitions.json` beginnt erst danach.

| RST | erster Poll | Uptime | `readCount` | sofort vollständig gelesen | `fav0` |
|-----|-------------|--------|-------------|----------------------------|--------|
| 07:46 | 07:47:02 | 3 s | 167 | `fav2` (BOB) 524.288 / maxSeq 524.288 | 32.768 / maxSeq 4.096 |
| 07:51:50 | 07:51:50 | 3 s | 243 | `fav0` (Rock) läuft schon: 872.448 | Rampe |
| 07:52:48 | 07:52:48 | 3 s | 167 | `fav2` (BOB) 524.288 / 524.288 | 32.768 / 4.096 |
| 07:53:54 | 07:53:54 | 3 s | 167 | `fav1` (Bayern) 524.288 / 524.288 | 32.768 / 4.096 |
| 07:55:09 | 07:55:09 | 2 s | 202 | `fav0` (Rock) läuft schon: 704.512 | Rampe |
| 07:56:58 | 07:56:58 | 2 s | 167 | `fav2` (BOB) 524.288 / 524.288 | 32.768 / 4.096 |

**Ergebnis:**
- In **6 von 6** RSTs liest die HU direkt nach der Neu-Enumeration eine Datei frisch per USB, ohne Bedienung. Die Serial ist dabei gleich (PD0089).
- `readCount = 167` ist in 4 Fällen exakt gleich: 128 Reads für die 512-KiB-Datei, 8 Stichproben auf `fav0`, 31 Metadaten-Reads.
- Für einen HU-Cache, der einen RST überlebt, gibt es in dieser Session **keinen Beleg**.
- Das Bild „klein = Cache, groß = Re-Read“ entsteht nur dadurch, dass eine 512-KiB-Datei in < 1 s vor dem ersten Poll fertig ist, Rock (8 MiB, ~10 s) aber nicht.

**Folge:**
- F2c lautet richtig: **HU liest nach jedem RST neu** [B].
- Die Regel „Live-Slot > HU-Cache-Budget“ hat keine Datengrundlage und wird nicht übernommen.
- Q4 (Cache-Größe) bleibt eine offene Frage. Sie ist kein Planbaustein für den Stall-Pfad.

## K2 — Der „Marker-8-MiB-Tonversuch“ ist mit 0.4.46 nicht durchführbar

**Behauptet:** Mistral und GPT empfehlen als „decisive test“ die schon generierte Datei `lab-prep/marker-8mib.bin` (`tools/nbt_marker_file.py`), mit hörbaren Sektionen in fav0.

**Tatsächlich:**
1. `nbt_marker_file.py` schreibt pro Sektion ein Tag (`Mk01`…) plus `0x55`-Füllung, optional mit `kSil`-Sync (`FF FB 30 64`) alle 156 B. Das ist **kein hörbarer Inhalt**, bestenfalls Stille.
2. Das Tool sagt selbst: „custom MSC image support. Does NOT flash or change ESP geometry.“ In FW 0.4.46 füllt der ESP Nicht-Live-Slots immer mit `Mp3Silence::fill`; es gibt keinen Pfad, eine externe Datei auszuliefern.
3. Die Marker-Datei ist daher ein Lab-Diagnosemittel für Offsets, kein Feldtest für F1.

**Ersatz für F1 ohne FW:**
- USB-Stick mit echter MP3 und gesprochenen Markern, siehe [`../FELDPROTOKOLL-NAECHSTER-TERMIN.md`](../FELDPROTOKOLL-NAECHSTER-TERMIN.md).
- Dazu als zweiter Hinweis die LBA-Lesereihenfolge per `msc.reads` (Bridge `--no-audio`).

## K3 — Lab-Anker G4 („Next-Prefetch ≈ 1,1 s nach Read-EOF“) passt nicht zu s1-morgen

In s1-morgen hängt der Next-Track-Prefetch an der **Wiedergabezeit**, nicht am Read-EOF:

| laufender Titel | Wiedergabe-Ende (Operator) | Prefetch nächster Titel | Vorlauf |
|-----------------|----------------------------|-------------------------|---------|
| BOB (nach RST 07:46) | 07:48:25 „BOB fertig → Bayern“ | Bayern 07:48:10–11 | ~15 s |
| Bayern | ~07:49:52 „tippt fertig genau am Ende“ | Rock 07:49:38 | ~14 s |
| Bayern (Boot 0, manuell gewählt 07:42:48) | ~07:44:15 (gerechnet: +87 s) | Rock 07:44:08 | ~7 s |

Nach dem Read-EOF von Rock (07:49:51, 07:53:12, 07:54:09, 07:57:21) folgt **kein** Prefetch.

**Folge:**
- G4 bleibt als Lab-Regression des alten Modells gültig, ist aber **kein** Feldmodell mehr.
- Im Kalibrierblatt wird der Anker auf „Prefetch ≈ 15 s vor Wiedergabe-Ende“ umgestellt, Status [S] (2 Fälle, 1 Ausreißer).

---

## Zusätzliche Muster aus derselben Session

Diese Muster sind in [`../../../fahrzeug/HU-Technical-Facts.md`](../../../fahrzeug/HU-Technical-Facts.md) als R15–R21 eingetragen:

- **Lesetakt:** 250 Reads/s (4,0 ms, 1,02 MB/s) ohne ESP-Play-Erkennung (Boot 0, 2, 5); 195 Reads/s (5,1 ms, 0,80 MB/s), sobald `playingUid=fav0` gesetzt ist (Boot 1, 3, 4, 6).
- **Erster sequenzieller Lauf** bei Rock-Auswahl: immer 368.640 B (5 von 5). Danach 2–3 s Fragmente (`maxSeq` hängt bei 392–632 KiB), dann ein Lauf bis zum Ende (5.201.920 B in 3 von 4 Fällen).
- **Summe** `fav0` nach RST + Rampe: 4-mal exakt 8.179.712 B. 51 Blöcke zu 4 KiB werden nicht gelesen.
- **Keine Meta-Reads** in den Rampen: In jeder Sekunde gilt `readCount`-Zuwachs × 4096 = Zuwachs der `fav0`-Bytes. Die `maxSeq`-Brüche sind also Sprünge innerhalb der Datei.
- **Pause bei Autoplay:** Bei Autoplay-Wechseln auf Rock (Boot 0 bei 4.194.304 B, Boot 1 bei 3.985.408 B) setzt das Lesen 2–3 s aus. Bei angetippter Auswahl nicht.
