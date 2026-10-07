# F1/F2 Auswertung — feld-s1-morgen (2026-10-07)

Begleitend zu [`GESAMTBERICHT-FELD-S1-MORGEN.md`](GESAMTBERICHT-FELD-S1-MORGEN.md). Zahlen aus Poll + Dense-Watch.

## F1 Entscheidungsmatrix

| Beobachtung | Schluss |
|-------------|---------|
| Balken startet ≪ USB-EOF (Ramp noch offen) | inkrementell → Stall-Pfad |
| Balken startet erst ≈ nach Ramp-Ende | after_eof → Dateikette/Fallback |

**Ist heute:** Ramp Rock ~11–13 s gut gemessen; Balken-Start **nicht** operator-zeitgestempelt → Zelle offen.

## F2 Entscheidungsmatrix (Ist)

| Probe | Evidenz | Label |
|-------|---------|-------|
| F2a Abwahl/Cache Session | flat `readCount` nach EOF, Play weiter | cache_hit_like [S] |
| F2c RST → BOB | `fav2=524288` früh, rc flach (Boot1 07:47) | cache_hit_like [S] |
| F2c RST → Bayern | `d_rc`≥80, fav1→524288 | cold_burst [S] |
| F2c RST → Rock | immer ~8 MiB Ramp | cold_burst [B] reproduzierbar |
| F2d Serial-Wechsel | nicht getestet | offen |

## Repro-Skript (feld)

1. Bridge stop, Silence L3.  
2. Poll 1 Hz.  
3. RST → Autoplay oder Tippen BOB/Bayern/Rock.  
4. Erwartung: Rock immer Burst; BOB oft Cache nach RST.

## Peer-Review Fragen

1. Ist Eager-Rock nach RST hinreichend gegen „Cache-only Remount“ für Stall-Design?  
2. Soll Stall nur auf Live-Slot, wenn HU nach Remount 8 MiB neu zieht?  
3. Wie F1 mit nur Balken schließen (Video-Pflicht / LED als Proxy ungeeignet)?
