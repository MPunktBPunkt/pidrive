# MSC / BMW — aktueller Stand (Lesereihenfolge)

**Stand:** 2026-10-04 · Lab AV **A+B PASS** (Fingerprint am Host-dd im Live-Fenster) · Feld-AV/Ohr offen · C′-Retry-Tools ready · FW `0.4.45-dev`  
**Phase:** MSC-Lieferung im Lab belegt · Feld = HU-Read × Fenster × Inhalt × Ton (Cursor-Hypothese) · C′ getrennt

Dies ist der **einzige Einstieg**, wenn du wissen willst, wo wir stehen und warum.

---

## 1. Jetzt lesen (normativ)

| # | Dokument | Rolle |
|---|----------|--------|
| 0 | [`artifacts-2026-10-04-lab/UEBERGABE-FELD-MORGEN-AV-C-PRIME-2026-10-04.md`](artifacts-2026-10-04-lab/UEBERGABE-FELD-MORGEN-AV-C-PRIME-2026-10-04.md) | **Übergabe morgen** — Doppelauftrag C′ + AV |
| 0a | [`artifacts-2026-10-04-lab/lab88-av-mpeg-2035/GESAMTBERICHT-AV-MPEG-AT-HOST.md`](artifacts-2026-10-04-lab/lab88-av-mpeg-2035/GESAMTBERICHT-AV-MPEG-AT-HOST.md) | Lab AV A+B PASS |
| 0b | [`artifacts-2026-10-04-lab/lab88-av-mpeg-2035/KRITIK-MISTRAL-GPT-AV-AB.md`](artifacts-2026-10-04-lab/lab88-av-mpeg-2035/KRITIK-MISTRAL-GPT-AV-AB.md) | GPT-Grenzen vs. Mistral-Überzug |
| 1 | [`artifacts-2026-10-04-feld/feld-q3b-next-1738/GESAMTBERICHT-FELD-Q3B-1738.md`](artifacts-2026-10-04-feld/feld-q3b-next-1738/GESAMTBERICHT-FELD-Q3B-1738.md) | Feld 17:38 C' FAIL (Seed bei GO tot) |
| 1a | [`artifacts-2026-10-04-feld/feld-q3b-next-1738/KRITIK-MISTRAL-GPT-1738.md`](artifacts-2026-10-04-feld/feld-q3b-next-1738/KRITIK-MISTRAL-GPT-1738.md) | Rohspur-Korrektur Mistral/GPT |
| 2 | [`artifacts-2026-10-04-feld/feld-q3b-next-1732/GESAMTBERICHT-FELD-Q3B-1732.md`](artifacts-2026-10-04-feld/feld-q3b-next-1732/GESAMTBERICHT-FELD-Q3B-1732.md) | 17:32 Seed an HU (`bytesServed` +8 MiB) |
| 3 | [`artifacts-2026-10-04-lab/lab88-seed-survive-2029/GESAMTBERICHT-SEED-SURVIVE.md`](artifacts-2026-10-04-lab/lab88-seed-survive-2029/GESAMTBERICHT-SEED-SURVIVE.md) | Seed-Gate Lab PASS |
| 4 | [`PLAN-NACH-M3-AE-2026-10-03.md`](PLAN-NACH-M3-AE-2026-10-03.md) | Freeze |

---

## 2. Ampel

| Thema | Stand |
|-------|--------|
| P1 Body-Next | EVIDENCED (17:34 + 17:47 LED+Trace; auch Tür 17:55) |
| Feld-Oracle B | **PASS** |
| Feld-Oracle C' | **PASS** bei 17:32 (+8 MiB); **FAIL** bei 17:38 (`active=False` schon bei GO / Reboot) |
| AV / Ohr | Feld **FAIL** · Lab A+B **PASS** (Fingerprint/`liveBytes>0` im **gezielt** gelesenen Fenster; ≠ Decoder/Ohr) |
| Detect | Cold=`not_from_head`; nur Log |
| Sequenz-GO | gesperrt bis hörbarer AV |
| Freeze | hält |

---

## 3. Nächste Schritte

1. **Feld morgen — zwei getrennte Läufe:** (a) C′-Retry mit Gate/Watchdog; (b) AV mit Seed **aus**, echter Stream — Ziel `liveBytes>0` + Ton.  
2. **AV Feld:** gleichen Nachweis wie Lab B unter HU-Reads (Fenster/`hostAbsCursor` vs absBase..absEnd).  
3. Detect erst nach Hörbeweis. Freeze hält.

```
Lab A+B PASS — MPEG-Bytes am Host-dd im Live-Fenster
Feld-Stille: Cursor/Fenster = Hypothese bis HU-Korrelation
Morgen: C′ (Seed/Gate) und AV (Seed aus) getrennt; GO erst nach Ohr
Freeze hält
```
