# Feld 60s — Auto 2026-10-02 ~15:36–15:48 — Verdict

**FW:** 0.4.36-dev · **ESP:** 192.168.178.89 · **Pi Bridge:** 192.168.178.105 → PUMP TCP :9090  
**Guard-Fix:** deployed (switch/ignore rapid via started_at)

## Zentrale Frage (§15.3)

Liest die BMW NBT während Wiedergabe kontinuierlich Live-MSC-Daten?

**Antwort (Feld, dieser Nachmittag): Nein — Burst dann Cache.**

## Evidenz

| Pass / Fenster | UID | Ohr | Metrik |
|----------------|-----|-----|--------|
| fav2-153656 | fav2 BOB | (später) Cover + kurze Sekunden Ton | 60s: readsΔ=0, streamBytesΔ=0 |
| replug-1538-burst | fav0→fav1 | — | Live-Burst bis sb≈981KiB / reads=421, dann Stillstand |
| fav1-153911 | fav1 Bayern | Cover + kurze Sekunden | 60s: sb flat 980992, reads flat |
| Replug 15:41 / 15:44 | — | BOB & Rock Antenne / Bayern: Bild+kurze Ton | Bridge/PUMP flaky (reconnect loops); ESP `/api/status` ok |
| fav1-bayern-1546 | ESP zeigt fav2 | Bayern kurz gehört | 60s poll: rc=421 sb=167936 **unverändert**, live_samples=0/55; Bridge forwarded audio weiter |

## Nebenbefunde

- `play.reject seq_short` (u.a. fav0 prefetch) + hoher `playRejectCount` (~392)
- Viele Bridge-Reconnects (`hello_ack=missing` bursts) bei STA — Link-Rauschen, Messung über ESP HTTP `/api/status` robuster als PUMP allein
- Formaler fav0-60s-Tool-Pass **fehlgeschlagen** (CLI/Outage 15:42); Ohr trotzdem: Rock Antenne Bild+kurze Sekunden (wie fav1/fav2)
- Lab-Dryrun `fav0-145621` zeigt Tool kann Dauer-Reads sehen — BMW-Feld nicht

## Fazit für Architektur

HU konsumiert nach Auswahl einen kurzen MSC-Burst (Cover/ID3/Anfang), speichert/cached, liest den Live-Stream-Bereich **nicht** kontinuierlich nach. Dauerhaftes Live-Streaming über MSC-Readahead ist damit **kein** belastbarer Feld-Pfad ohne weiteres HU-/Protokoll-Umdenken.

| `replug-1550-note` | OTG ~15:50 | gleiches Kurzton/Cover-Verhalten | Bestätigung §11.10; User Ende Session |
