# Kritik Mistral/GPT — Lab AV A+B / Übergabe morgen

**Rohspur:** `REPORT.json`, `sample-live-off147456.bin`, `sample-head-post.bin` · Commit `545d5c2`

## Kurzurteil

**GPT ist die bessere Kalibrierung.** Mistral hat Trigger + Doppelauftrag richtig, überzieht aber im Fazit die Beweisreichweite. Die GPT-Beweisgrenzen (Fenster gezielt gewählt, Fingerprint ≠ Decoder, Cursor-Hypothese) sind verbindlich zu übernehmen.

## Was beide richtig haben

| Aussage | Bewertung |
|---------|-----------|
| Auto-Next = gezielter Read-Trigger (~87 s Nominal) | **Ja** — Feld mehrfach (LED+Trace/Cold) |
| Türöffnen ≠ Design-Trigger | **Ja** — nur beobachtet |
| Detect-Log ≠ Read | **Ja** |
| Lab A: Ring voll, `underruns=0` | **Ja** — `size=49152` |
| Lab B: Sync-Kandidaten + ID3, `liveBytes=24576` | **Ja** — Binärprobe bestätigt (`fffb` ab Off 6; Head `ID3`) |
| C′ und AV getrennt abnehmen | **Ja** |
| Fünf Feldfragen (fileOff × Fenster × Inhalt × Ton) | **Ja** (GPT) |
| Freeze / Sequenz-GO gesperrt | **Ja** |

## Wo Mistral überzieht

1. **„Technische Lieferfähigkeit vollständig nachgewiesen“** — zu absolut. Nachgewiesen ist: unter Lab-Pump + **gezielt ins Live-Fenster gelegtem** Host-dd liefert MSC MPEG-*kompatible* Bytes. Nicht nachgewiesen: HU-Burst, beliebige LBAs, Decoder/Ohr.  
2. **„Echtes, dekodierbares MPEG“** — Fingerprint/Sync ≠ Frame-Validierung ≠ Decoder-Test (GPT korrekt; Mistral widerspricht sich teils selbst).  
3. **Flowchart F→G (C′-Retry → AV C+D):** C′ ist **Seed-Diagnose**, nicht Voraussetzung für AV. Reihenfolge „morgen zwei Läufe“ ok; kausal nicht verketten.  
4. **„Beide Grundvoraussetzungen erfüllt“** nur gültig mit GPT-Grenzen: Trigger belegt · Lab-Lieferung belegt · **Verbindung im Auto offen**.

## Wo GPT präzise ist (übernehmen)

- Cursor/Fenster = **Arbeitshypothese**, nicht abschließende Rückführung der Feld-Stille.  
- Host-Read war **ins Fenster gelegt** (`fileOff=147456` ∈ 135168…184320; `hostAbsCursor=142848` ebenfalls).  
- Stufe C braucht Korrelation an **HU**-LBAs über den Burst, nicht nur eine Lab-Position.  
- Kein Gesamt-PASS aus C′+AV ohne Hörtest.

## Nuance zur Telemetrie

Während Stage-A-Poll: `streamBytes=0` / `live=0` bei vollem Ring — erwartbar, solange kein Host-Serve. `liveBytes=24576` erst **nach** dd (Stage B). Ring-Voll ≠ bereits ausgeliefert.

## Maßnahmen (unverändert, geschärft)

1. **Morgen Lauf 1 — C′:** RST fertig → Seed → Gate (`active`+uptime) → Watchdog → Auto-Next ohne RST → `bytesServed↑` + Trace.  
2. **Morgen Lauf 2 — AV:** Seed **aus** · echter Producer · HU-LBA/`fileOff` × `absBase..absEnd`/`hostAbsCursor` · `liveBytes`/`underruns` · Byte-Fingerprint · Ohr/Film.  
3. **Getrennt bewerten**; Sequenz-GO nur nach hörbarem AV.  
4. Optional: Boot-Reason 17:38:35→39 — blockiert Retry nicht, wenn Gate greift.  
5. Keine Freeze-/Detect-Änderung aus Lab A+B.
