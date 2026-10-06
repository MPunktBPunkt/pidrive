# MSC / BMW — aktueller Stand (Lesereihenfolge)

**Stand:** 2026-10-06 Lab — **Bulk-drainTcp 0.4.46-dev auf .88:** Idle ~840 KB/s · async Hold-PASS inkl. 248 KiB @~275 KB/s · Feld noch 0.4.45  
**Phase:** Baustelle B — Bridge Prefill+Hold+lokale Hold-Schätzung; Feld-OTA 0.4.46 nach Abstimmung · Freeze Feld hält

Dies ist der **einzige Einstieg**, wenn du wissen willst, wo wir stehen und warum.

---

## 1. Jetzt lesen (normativ)

| # | Dokument | Rolle |
|---|----------|--------|
| 0 | [`artifacts-2026-10-05-feld/feld-av-1807/GESAMTBERICHT-FELD-AV-1807.md`](artifacts-2026-10-05-feld/feld-av-1807/GESAMTBERICHT-FELD-AV-1807.md) | **Feld 18:07** — RST→Head-Arm, Ring voll, live=0 / kein Ton |
| 0r | [`artifacts-2026-10-05-feld/KRITIK-REVIEW-MISTRAL-GPT-FELD-1807-87d2523.md`](artifacts-2026-10-05-feld/KRITIK-REVIEW-MISTRAL-GPT-FELD-1807-87d2523.md) | **Review Mistral+GPT** — RST-Trigger, 253952-Korrektur, P0 Lab |
| 0f5 | [`artifacts-2026-10-05-feld/feld-av-1755/GESAMTBERICHT-FELD-AV-1755.md`](artifacts-2026-10-05-feld/feld-av-1755/GESAMTBERICHT-FELD-AV-1755.md) | Feld 17:55 — ohne RST kein Arm |
| 0h | [`artifacts-2026-10-05-lab/lab88-head-trigger-1754/GESAMTBERICHT-HEAD-TRIGGER.md`](artifacts-2026-10-05-lab/lab88-head-trigger-1754/GESAMTBERICHT-HEAD-TRIGGER.md) | Lab Mid→Head armt |
| 0p | [`artifacts-2026-10-05-lab/lab88-prefill-arm-1750/GESAMTBERICHT-PREFILL-ARM.md`](artifacts-2026-10-05-lab/lab88-prefill-arm-1750/GESAMTBERICHT-PREFILL-ARM.md) | Lab Prefill-vor-Arm PASS |
| 0e2 | [`artifacts-2026-10-05-feld/feld-av-abend-1530/GESAMTBERICHT-FELD-AV-ABEND.md`](artifacts-2026-10-05-feld/feld-av-abend-1530/GESAMTBERICHT-FELD-AV-ABEND.md) | Feld Abend 15:30 — Gate PASS, AV/Ohr FAIL Fenster/Arm |
| 0L4 | [`artifacts-2026-10-05-lab/lab88-arm-diag-1635/GESAMTBERICHT-ARM-DIAG.md`](artifacts-2026-10-05-lab/lab88-arm-diag-1635/GESAMTBERICHT-ARM-DIAG.md) | Lab Arm-Diagnose: Mid≠Arm, Head-Arm bei ring=0 |
| 0L3 | [`artifacts-2026-10-05-lab/lab88-hu-mimic-1617/GESAMTBERICHT-HU-MIMIC-1541.md`](artifacts-2026-10-05-lab/lab88-hu-mimic-1617/GESAMTBERICHT-HU-MIMIC-1541.md) | Lab HU-Mimic 15:41 Fenster-Outrun |
| 0L2 | [`artifacts-2026-10-05-lab/STREAM-COUNTER-SEMANTIK.md`](artifacts-2026-10-05-lab/STREAM-COUNTER-SEMANTIK.md) | StreamBuffer: underruns / hostAbs / liveBytes |
| 0L5 | [`artifacts-2026-10-05-lab/LAB-NEXT-ARM-TIMELINE-2026-10-05.md`](artifacts-2026-10-05-lab/LAB-NEXT-ARM-TIMELINE-2026-10-05.md) | **P0 Lab:** Arm-Timeline + RST-Matrix (`m3_lab_arm_timeline.py`) |
| 0L6 | [`artifacts-2026-10-05-lab/GESAMTBERICHT-ARM-TIMELINE-MATRIX-1945.md`](artifacts-2026-10-05-lab/GESAMTBERICHT-ARM-TIMELINE-MATRIX-1945.md) | **Lab Matrix:** 253952 = 62×4KiB Underrun (PASS) |
| 0L7 | [`artifacts-2026-10-05-lab/GESAMTBERICHT-ARM-WEICHE-2035.md`](artifacts-2026-10-05-lab/GESAMTBERICHT-ARM-WEICHE-2035.md) | **Lab Weiche:** Prefill-Sweep + Free vs Gate |
| 0L8 | [`artifacts-2026-10-05-lab/GESAMTBERICHT-ARM-FOLGE-2045.md`](artifacts-2026-10-05-lab/GESAMTBERICHT-ARM-FOLGE-2045.md) | **Lab Folge:** Pace-Raten + Fenster-voraus-Repro |
| 0L9 | [`artifacts-2026-10-05-lab/GESAMTBERICHT-CURSOR-HOLD-2110.md`](artifacts-2026-10-05-lab/GESAMTBERICHT-CURSOR-HOLD-2110.md) | **Lab Cursor-Hold PASS** (gegen 2050 / Host-Pause) |
| 0L10 | [`artifacts-2026-10-05-lab/GESAMTBERICHT-ASYNC-PRODUCER-2140.md`](artifacts-2026-10-05-lab/GESAMTBERICHT-ASYNC-PRODUCER-2140.md) | **Lab Async:** Free=18:07 · Hold behind=0 · Pace unter MSC-Last offen |
| 0L11 | [`artifacts-2026-10-05-lab/GESAMTBERICHT-PUMP-IDLE-BURST-REALISM.md`](artifacts-2026-10-05-lab/GESAMTBERICHT-PUMP-IDLE-BURST-REALISM.md) | **Lab Idle+Burst:** Pump-Ceiling ~70 KB/s · Prefill≥Burst async PASS |
| 0L12 | [`artifacts-2026-10-06-lab/lab88-async-064741-burst-then-slow/NOTE-BURST-THEN-SLOW.md`](artifacts-2026-10-06-lab/lab88-async-064741-burst-then-slow/NOTE-BURST-THEN-SLOW.md) | Burst-then-Slow: und=0, behind≠0 (kein formaler PASS) |
| 0L13 | [`artifacts-2026-10-06-lab/GESAMTBERICHT-BULK-DRAINTCP-046.md`](artifacts-2026-10-06-lab/GESAMTBERICHT-BULK-DRAINTCP-046.md) | **Lab Bulk-drainTcp:** Idle ~840 KB/s · maxpump-hold PASS |
| 0k7 | [`artifacts-2026-10-06-lab/KRITIK-REVIEW-MISTRAL-GPT-CLAUDE-IDLE-BURST-c99ac36.md`](artifacts-2026-10-06-lab/KRITIK-REVIEW-MISTRAL-GPT-CLAUDE-IDLE-BURST-c99ac36.md) | **Review Mistral+GPT+Claude** zu c99ac36 — Maßnahmen |
| 0k6 | [`artifacts-2026-10-05-lab/KRITIK-REVIEW-MISTRAL-CLAUDE-ASYNC-eb91d4e.md`](artifacts-2026-10-05-lab/KRITIK-REVIEW-MISTRAL-CLAUDE-ASYNC-eb91d4e.md) | Review Mistral+Claude zu eb91d4e (Rate-Korrektur) |
| 0k4 | [`artifacts-2026-10-05-lab/KRITIK-REVIEW-MISTRAL-GPT-ARM-TIMELINE-8d4f028.md`](artifacts-2026-10-05-lab/KRITIK-REVIEW-MISTRAL-GPT-ARM-TIMELINE-8d4f028.md) | Review Mistral+GPT zu 8d4f028 |
| 0k5 | [`artifacts-2026-10-05-lab/KRITIK-REVIEW-MISTRAL-GPT-WEICHE-a99a830.md`](artifacts-2026-10-05-lab/KRITIK-REVIEW-MISTRAL-GPT-WEICHE-a99a830.md) | Review Mistral+GPT zu Weiche a99a830 |
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
| AV / Ohr | Lab Bulk-Pump ~840 KB/s · async Hold-PASS (248 KiB) 🟢 · Feld-Ton 🔴 (Feld noch 0.4.45) |
| Lab Menü-Seite | **PASS** — Lock hält Sender-Slots; Meta ohne Producer; `page_home`/Remount dokumentiert |
| Menü-Lock | Lab+**Feld Abend**: Meta-Erstsiegel / stale Bridge geheilt durch **frischen Bridge-Prozess**; erstes Feld-`MSC_MAP_FROZEN` Rock **archiviert** |
| Detect | Cold=mid Reject; **Head-Arm im Feld nach RST** belegt; Cooldown 5 s |
| Sequenz-GO | gesperrt bis hörbarer AV |
| Freeze | hält |

---

## 3. Nächste Schritte

1. **Feld (P0):** OTA `0.4.46-dev` (Bulk-drainTcp) nach Abstimmung → RST → Bridge → Gate → 1 Sender → Correlate + Ohr.  
2. **Bridge:** Prefill + Hold mit lokaler absEnd-Schätzung (wie Lab-Tool); PASS `live>0 ∧ und=0 ∧ behind=0`.  
3. Freeze Feld hält bis OTA-Go; Lab .88 bereits `0.4.46-dev`.

```
Bulk-drainTcp: Idle ~840 KB/s (war ~70)
maxpump-hold 248 KiB PASS (pump≈host)
Nächstes: Feld-OTA 0.4.46 + Ton
```
