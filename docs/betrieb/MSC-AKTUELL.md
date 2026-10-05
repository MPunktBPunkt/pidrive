# MSC / BMW — aktueller Stand (Lesereihenfolge)

**Stand:** 2026-10-05 Vormittag · Feld C′ **PASS** (Gate/Watchdog) · Feld AV blockiert (Menü-Seite Favoriten/Quellen/Stop, `liveBytes=0`) · Lab AV A+B PASS · FW `0.4.45-dev`  
**Phase:** C′ im Auto belegt · AV braucht Sender-Seite (Rock/Bayern/BOB) + Live-Stream · Freeze hält

Dies ist der **einzige Einstieg**, wenn du wissen willst, wo wir stehen und warum.

---

## 1. Jetzt lesen (normativ)

| # | Dokument | Rolle |
|---|----------|--------|
| 0 | [`artifacts-2026-10-05-feld/FELD-SESSION-2026-10-05-MORGEN.md`](artifacts-2026-10-05-feld/FELD-SESSION-2026-10-05-MORGEN.md) | **Feld heute** — C′ PASS, AV Menü-Hindernis |
| 0a | [`artifacts-2026-10-05-lab/LAB-NEXT-MENU-AV-2026-10-05.md`](artifacts-2026-10-05-lab/LAB-NEXT-MENU-AV-2026-10-05.md) | **Lab heute** — Menü-Seite + AV-Prep für Abend |
| 0b | [`artifacts-2026-10-04-lab/lab88-av-mpeg-2035/GESAMTBERICHT-AV-MPEG-AT-HOST.md`](artifacts-2026-10-04-lab/lab88-av-mpeg-2035/GESAMTBERICHT-AV-MPEG-AT-HOST.md) | Lab AV A+B PASS |
| 1 | [`artifacts-2026-10-05-feld/feld-q3b-next-0744/`](artifacts-2026-10-05-feld/feld-q3b-next-0744/) | C′ Artefakte (GATE+Watchdog PASS) |
| 2 | [`artifacts-2026-10-05-feld/feld-av-0750/`](artifacts-2026-10-05-feld/feld-av-0750/) | AV Correlate: stream off / live=0 |
| 3 | [`artifacts-2026-10-04-feld/feld-q3b-next-1738/GESAMTBERICHT-FELD-Q3B-1738.md`](artifacts-2026-10-04-feld/feld-q3b-next-1738/GESAMTBERICHT-FELD-Q3B-1738.md) | gestern C′ FAIL (Seed tot bei GO) |
| 4 | [`PLAN-NACH-M3-AE-2026-10-03.md`](PLAN-NACH-M3-AE-2026-10-03.md) | Freeze |

---

## 2. Ampel

| Thema | Stand |
|-------|--------|
| P1 Body-Next | EVIDENCED |
| Feld-Oracle B | **PASS** |
| Feld-Oracle C' | **PASS** 2026-10-05 07:45 (`bytesServed` +1,5 MiB, Seed überlebte Settle); gestern 1738 FAIL |
| AV / Ohr | Lab A+B **PASS** · Feld **blockiert** — HU auf Meta-Seite Favoriten/Quellen/Stop, kein `stream.active` |
| Menü-Lock | Bridge frozen auf Rock/Bayern/BOB; API/HU zeigen Favoriten/Quellen/Stop → `frozen_reject` |
| Detect | Cold=`not_from_head`; nur Log |
| Sequenz-GO | gesperrt bis hörbarer AV |
| Freeze | hält |

---

## 3. Nächste Schritte

1. **Lab (heute):** Menü-Seite klären — wie landet Session auf Favoriten/Quellen/Stop; Prozedur zurück zu Rock/Bayern/BOB (page / remount / reseal).  
2. **Feld Abend:** erst Sender-Seite sichtbar → AV mit Seed aus + Correlate + Ohr (`liveBytes>0`). C′ nicht wiederholen (schon PASS).  
3. Detect erst nach Hörbeweis. Freeze hält.

```
C′ Feld PASS (Gate hält)
AV Feld: Meta-Menü blockiert Live-Stream
Lab: Menü-Seite → Abend AV mit Rock/Bayern/BOB
Freeze hält
```
