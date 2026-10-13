# Kritik Mistral/GPT-Feldbericht 1738 — Rohspur-Abgleich

## Was stimmt

- C′ nicht pauschal geschlossen; 17:32 ist konfigurationsgebunden.
- LED/Cold = Read-Indikatoren, kein Inhalts-/AV-Beweis.
- Tür-Burst: Ursache nicht isoliert.
- AV-Formulierung: gültiges MPEG **an den gelesenen LBAs** (A→D), nicht nur „Producer“.
- Vermeidungsliste (Seed≠Audio, Detect nicht vor AV, Freeze) ist richtig.
- LBA-761-Claim: in `pidrive_msc_reads.jsonl` verifiziert (u.a. Span 609–825, exakt LBA 761).

## Was falsch / zu schwach ist

1. **Hauptursache C′-FAIL:** nicht primär RST 17:43/44.  
   `status-02-seeded` (17:38:35): `active=True`, uptime **5min 53s**.  
   `status-03-go` (17:38:39): `active=False`, uptime **3s**, `cold=1`.  
   Seed war vor Auto-Next tot; Operator-RST war Sekundärfehler.
2. GO-Monitor prüfte damals nur `bytesServed`, nicht `active` → stiller Blindflug.
3. „Bayern ohne LED = Warm/Cache“ ist Hypothese.
4. „Mit korrigierter RST-Prozedur direkt wiederholbar“ ist zu sicher, solange kein Seed-Gate/Watchdog den Reboot-Fall fängt.
5. SoftAP-8 KiB vs. `bytesServed`~8 MiB: Zähler zählt Seed-Auslieferung ab `fromOff`, nicht die Stichprobendatei.

## Abgeleitete Maßnahmen

Siehe `GESAMTBERICHT-FELD-Q3B-1738.md` §Maßnahmen — Priorität: Gate+Watchdog → C′-Retry → AV A→D.
