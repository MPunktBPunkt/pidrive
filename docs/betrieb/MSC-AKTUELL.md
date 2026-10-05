# MSC / BMW — aktueller Stand (Lesereihenfolge)

**Stand:** 2026-10-05 Lab Arm-Diagnose · Fenster-Outrun + Head-Arm bei ring=0 belegt · FW `0.4.45-dev`  
**Phase:** Baustelle B — Prefill-vor-Arm als Lab-Gegenmittel; Feldlauf mit `--dense` als Nächstes · Freeze hält

Dies ist der **einzige Einstieg**, wenn du wissen willst, wo wir stehen und warum.

---

## 1. Jetzt lesen (normativ)

| # | Dokument | Rolle |
|---|----------|--------|
| 0 | [`artifacts-2026-10-05-feld/feld-av-abend-1530/GESAMTBERICHT-FELD-AV-ABEND.md`](artifacts-2026-10-05-feld/feld-av-abend-1530/GESAMTBERICHT-FELD-AV-ABEND.md) | **Feld Abend** — Gate PASS, AV/Ohr FAIL Fenster/Arm |
| 0L4 | [`artifacts-2026-10-05-lab/lab88-arm-diag-1635/GESAMTBERICHT-ARM-DIAG.md`](artifacts-2026-10-05-lab/lab88-arm-diag-1635/GESAMTBERICHT-ARM-DIAG.md) | Lab Arm-Diagnose: Mid≠Arm, Head-Arm bei ring=0 |
| 0L3 | [`artifacts-2026-10-05-lab/lab88-hu-mimic-1617/GESAMTBERICHT-HU-MIMIC-1541.md`](artifacts-2026-10-05-lab/lab88-hu-mimic-1617/GESAMTBERICHT-HU-MIMIC-1541.md) | Lab HU-Mimic 15:41 Fenster-Outrun |
| 0L2 | [`artifacts-2026-10-05-lab/STREAM-COUNTER-SEMANTIK.md`](artifacts-2026-10-05-lab/STREAM-COUNTER-SEMANTIK.md) | StreamBuffer: underruns / hostAbs / liveBytes |
| 0s | [`artifacts-2026-10-05-feld/FELD-SESSION-2026-10-05-ABEND.md`](artifacts-2026-10-05-feld/FELD-SESSION-2026-10-05-ABEND.md) | Abend-Kurzsession |
| 0m | [`artifacts-2026-10-05-feld/FELD-SESSION-2026-10-05-MORGEN.md`](artifacts-2026-10-05-feld/FELD-SESSION-2026-10-05-MORGEN.md) | Morgen — C′ PASS, AV Meta-Hindernis |
| 0e | [`artifacts-2026-10-05-feld/FELD-ABEND-EAR-2026-10-05.md`](artifacts-2026-10-05-feld/FELD-ABEND-EAR-2026-10-05.md) | Abend-EAR (ausgeführt) |
| 0k | [`artifacts-2026-10-05-lab/KRITIK-GPT54-GESAMTBERICHT-2026-10-05.md`](artifacts-2026-10-05-lab/KRITIK-GPT54-GESAMTBERICHT-2026-10-05.md) | Kritik GPT-5.4 → Maßnahmen |
| 0k3 | [`artifacts-2026-10-05-lab/KRITIK-MISTRAL-LAB-FOLLOWUP-305b55f.md`](artifacts-2026-10-05-lab/KRITIK-MISTRAL-LAB-FOLLOWUP-305b55f.md) | Kritik Mistral 305b55f (lokal verifiziert) |
| 0k2 | [`artifacts-2026-10-05-lab/KRITIK-MISTRAL-GPT-KONSOLIDIERT-2026-10-05.md`](artifacts-2026-10-05-lab/KRITIK-MISTRAL-GPT-KONSOLIDIERT-2026-10-05.md) | Konsolidiert: Gate-Wortlaut schärfen |
| 0L | [`artifacts-2026-10-05-lab/lab88-lock-after-rst-1022/GESAMTBERICHT-LOCK-AFTER-RST.md`](artifacts-2026-10-05-lab/lab88-lock-after-rst-1022/GESAMTBERICHT-LOCK-AFTER-RST.md) | Lab: Meta-Erstsiegel-Mechanismus (**Feldmorgen stark erklärt**, Seal-Log Feld fehlt) |
| 0a | [`artifacts-2026-10-05-lab/lab88-menu-page-0816/GESAMTBERICHT-MENU-PAGE-AV-PREP.md`](artifacts-2026-10-05-lab/lab88-menu-page-0816/GESAMTBERICHT-MENU-PAGE-AV-PREP.md) | **Lab Menü-Seite PASS** + Abend-EAR |
| 0a1 | [`artifacts-2026-10-05-lab/lab88-correlate-meta-sender-0855/GESAMTBERICHT-CORRELATE-META-SENDER.md`](artifacts-2026-10-05-lab/lab88-correlate-meta-sender-0855/GESAMTBERICHT-CORRELATE-META-SENDER.md) | Correlate Meta=Negativ / Sender=Positiv **PASS** |
| 0a2 | [`artifacts-2026-10-05-lab/LAB-NEXT-MENU-AV-2026-10-05.md`](artifacts-2026-10-05-lab/LAB-NEXT-MENU-AV-2026-10-05.md) | Lab-Auftrag (Plan, erledigt) |
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
| AV / Ohr | Lab A+B **PASS** · Feld Abend: Gate **PASS**, Ohr **FAIL** — einmal `stream.active`+ffmpeg mit `liveBytes=0` (Fenster); sonst oft kein Arm |
| Lab Menü-Seite | **PASS** — Lock hält Sender-Slots; Meta ohne Producer; `page_home`/Remount dokumentiert |
| Menü-Lock | Lab+**Feld Abend**: Meta-Erstsiegel / stale Bridge geheilt durch **frischen Bridge-Prozess**; erstes Feld-`MSC_MAP_FROZEN` Rock **archiviert** |
| Detect | Cold=`not_from_head`; nur Log |
| Sequenz-GO | gesperrt bis hörbarer AV |
| Freeze | hält |

---

## 3. Nächste Schritte

1. **Feld (kurz):** frische Bridge → Gate + FROZEN archivieren → ein Sender → `--dense` Correlate + Ohr. Messen: `ring_size`/`hostAbs`/`live` **beim Arm**.  
2. Lab-Gegenmittel bleibt Messziel: Prefill/Fill **vor** HU-Head-Sequenz (nicht Detect-Umbau).  
3. Freeze hält. Gate-Recovery: Bridge neu / Unplug.

```
Fenster-Outrun Lab ✓
Head-Arm @ ring=0 Lab ✓
Feld: dense Correlate + Prefill-Frage
Freeze hält
```
