# Feldbericht — Q3b Auto-Next nach RST — 17:38–17:55 · PD0060

**FW:** `0.4.45-dev` · Prefill Seed **B** ab LBA 761 · SoftAP  
**Artefakt:** `docs/betrieb/artifacts-2026-10-04-feld/feld-q3b-next-1738/`

---

## Ampel

| Prüfpunkt | Status | Beleg |
|-----------|--------|-------|
| Feld-Oracle B (HU Body-LBAs) | **PASS** | LED Prefetch; Trace LBA-Span inkl. 761 (609–825); `cold` 1→8 |
| Feld-Oracle C' (Seed an MSC) | **FAIL** | `bytesServed` blieb **0**; `bodySeed.active=False` nach RST |
| LED / Auto-Next | **PASS** | BOB→Bayern, Bayern→Rock; zusätzlich Türöffnen ~17:55 |
| Detect Cold | Log `not_from_head` | `play.reject` / `cold_body_burst` auf fav0 |
| AV / Ohr | **FAIL** | Operator: nirgends Ton |

---

## Zeitlinie

1. **17:38** Prepare: Seed B aktiv (`status-02-seeded`: `active=True`, `bytesServed=0`)  
2. **17:39–17:42** BOB→Bayern ohne frischen Seed-Hit; Bayern-Ende ohne LED (Warm/Cache)  
3. **17:43–17:44** Operator: Wechsel zu BOB + **zweimal RST** (erster RST ohne Wechsel) → RAM-Seed weg  
4. **17:45** BOB durch, LED vor Wechsel; API oft schon fav1  
5. **17:46–17:47** Bayern→Rock: LED am Ende Bayern **und** Beginn Rock; `cold` →6; Seed weiter 0  
6. **17:48** Feld-Ende: kein Ton; Operator ins Haus  
7. **17:55** BMW-Tür öffnen → LED erneut; `cold` 6→8; Diag `cold_body_burst lba=97..153`

---

## Deutung

1. **C'-FAIL ist Verfahrensfehler, kein Widerspruch zu 17:32:** SoftAP-Seed liegt nur im RAM. RST 17:43/17:44 löscht ihn; der nachfolgende Body-Burst ging über Live/Ring (`active=False`, `bytesServed=0`).  
2. **Oracle B hält:** HU liest weiter Body (LED + Trace + Cold-Zähler), inkl. Fenster um Prefill-LBA 761 und erneut beim Türöffnen.  
3. **AV unverändert offen:** Seed≠MP3; Diag weiter `not_from_head` / Prefetch-Rejects — hörbarer Pfad braucht echten Producer.  
4. **Nächster Lauf:** Seed **nach letztem RST** setzen, dann Auto-Next **ohne** weiteren Reset; Erfolgskriterium wieder `bytesServed` steigt im Burst.

Vorgänger 17:32 (`feld-q3b-next-1732`): C' PASS (+8 MiB) bei Seed-über-Live ohne Seed-zerstörenden RST vor dem Rock-Burst.

---

## Freeze

Ring/PSRAM/Pacing/Detect-Policy unverändert. Sequenz-GO weiter gesperrt bis hörbarer AV-Nachweis.
