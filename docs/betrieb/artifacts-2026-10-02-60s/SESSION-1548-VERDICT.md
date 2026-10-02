# Feld 60s — Auto 2026-10-02 ~15:36–15:50 — Verdict

**FW:** 0.4.36-dev · **ESP:** 192.168.178.89 · **Pi Bridge:** 192.168.178.105 → PUMP TCP :9090  
**Guard-Fix:** deployed (switch/ignore rapid via started_at)

## Zentrale Frage (§15.3)

Liest die BMW NBT während Wiedergabe kontinuierlich Live-MSC-Daten?

**Antwort (eng):** In den beobachteten 60 s-Fenstern **nein** — Muster **Mount-Scan + Cache**.  
**Nicht bewiesen:** dass die HU nach Verbrauch der gescannten Slot-Daten **niemals** erneut liest (dazu B7 / ≥150 s).

## Evidenz

| Pass / Fenster | UID | Ohr | Metrik |
|----------------|-----|-----|--------|
| fav2-153656 | fav2 BOB | Cover + kurze Sekunden Ton | 60s: readsΔ=0, streamBytesΔ=0 (**nach** Burst) |
| replug-1538-burst | fav0→fav1 | — | Burst bis reads=421; Folgestatus sb=980992, dann Stillstand |
| fav1-153911 | fav1 Bayern | Cover + kurze Sekunden | ab t=0 flat rc=421 sb=980992 |
| Replug 15:41 / 15:44 / 15:50 | — | BOB & Rock Antenne / Bayern: Bild+kurze Ton | Bestätigung Kurzton-Muster |
| fav1-bayern-1546 | ESP zeigt fav2 | Bayern gehört | **Reads flat** (gültig); **UID-Mismatch** → Play-Detection-Auswertung ungültig |

## Zähler (Code-geprüft 2026-10-02)

- `streamBytes` ≠ Summe `slotMap.maxSeq` (980992 vs 786432 im fav1-153911-Snapshot).  
- `streamBytes` = Live-Overlay-Bytes an Host; siehe `lab88-counter-semantics/COUNTER-SEMANTICS.md`.  
- `readOverflow` = Telemetrie-Queue-Drops; flat im Poll = Hypothese „nicht in diesem Fenster“, nicht fertige Ursachenzuordnung.  
- Kurzton/Cover mit Fragment/Cache **vereinbar**, Ring als Ursache **nicht bewiesen**.

## Fazit

MSC-Menü/ID3/Cover bleiben sinnvoll. Dauer-Live über MSC-Readahead ist für A2 **nicht** belegt. Nächster Schritt: [`AUFTRAG-B7-HU-REREAD.md`](../../auftraege/AUFTRAG-B7-HU-REREAD.md). Eigenes Probe-FW-Repo: **verworfen** (Lab-APIs + Harness reichen).
