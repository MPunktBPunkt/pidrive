# Feld s6 — Q11-Licht / E7 Stall am NBT · Ergebnis 2026-10-12

**Zeit:** ~16:48–17:14 · Auto-Pi `.105` · ESP `.89`  
**FW:** Start Freeze **`0.4.46-dev`** → Go OTA **`0.4.48-dev`** (16:58) · Stall E7-A2 `maxMs=1000` chunk 4096  
**Ende:** `stallEnable=false` wieder gesetzt (Vorhersagbarkeit nächster Kaltstart)  
**Artefakt:** `s6-20261012-feld-e7/` · `marks.jsonl` · `OPERATOR-LIVE.txt`

## Kurzurteil

| Frage | Ergebnis |
|-------|----------|
| Ringfenster ohne Stall | **~6 s** (mehrfach, BOB/Bayern, Klasse A) |
| E7 Busy-Pacing am NBT | **JA — belegt** (~65 s Musik+ID3 bis Dateiende, ≫6–8 s) |
| Stall-Nebenwirkungen | Menü/Dateien träge (~20 s); UI „eingefroren“; Stationswechsel zickig |
| Rock Antenne (fav0, L3 8 MiB) | oft **stumm** (Resume/Start); kein vergleichbarer Dauerstrom in dieser Session |
| Q11 / weiße LED | gemischt: A ohne LED möglich; B mit LED weiterhin |

**Architektur:** TinyUSB `return 0` + `vTaskDelay` entkoppelt HU-Burst vom Producer **auch im BMW**. PSRAM als Primärlösung für Dauerstrom ist damit **nicht** mehr der Default-Pfad.

---

## Phase 1 — Freeze 0.4.46 (vor Stall)

| Zeit | Episode | Klasse | Ohr |
|------|---------|--------|-----|
| 16:50 | OTG → `PD0220`, Bild+Ton | **A** (keine weiße LED) | **~6 s** |
| 16:52 | Autoplay→Bayern, OTG | **B** (weiße LED) | verwerfen |
| 16:55 | Rock Antenne Bayern | | **~6 s** |
| 16:55 | iDrive OFF, ESP noch Strom | | secure |
| 16:56 | iDrive ON, Bayern erneut | | **~6 s** (ESP `PD0224` ohne neuen Boot) |

**Fazit Phase 1:** ~6 s = klassisches Ringfenster, stationsübergreifend. Klasse A erreichbar (s5-Blocker nicht absolut).

---

## Phase 2 — Go Stall 0.4.48

| Zeit | Ereignis |
|------|----------|
| 16:58 | OTA `0.4.48-dev`, dann Stall an `maxMs=1000` |
| 17:00 | Play-Detect-NVS war `playPlugWindowMs=0` → Defaults restauriert |
| 17:01–02 | Rock Antenne: Dateien langsam; Bild + **~8 s** Ton (noch Ring-artig) |
| 17:03–04 | OTG → Bayern-Intent; Boot `PD0227`; Dateien **~20 s**; erst nur BOB wählbar |
| 17:06 | **Langer Dauerton** mit kurzen Unterbrechungen |
| 17:09 | Operator: **~65 s** Musik + ID3 bis **Fileende**; danach Autoplay Rock Antenne **ohne Ton** |
| 17:13 | OTG A (keine weiße LED): Rock Antenne Resume/Start **stumm**; Tip Bayern „eingefroren“, dann Bayern wieder **Dauer bis EOF**; Rock **kein** Dauer |

### Stall-Telemetrie (Session-Ende, kumuliert)

| Feld | Wert |
|------|------|
| `stall.cmds` | 2399 |
| `stall.retries` | 147865 |
| `stall.timeouts` | 80 |
| `waitMsMax` | 1001 (= maxMs) |
| `waitHist` | viel &lt;100 ms, dazu 500–1000 ms-Buckets |

Kurze Hörlücken ≈ Silence-Fallback nach `maxMs` (timeouts).

### Slot-Kontext (L3)

| Slot | Name | Größe | Bemerkung Session |
|------|------|-------|-------------------|
| fav0 | Rock Antenne | **8 MiB** | oft Mid-File / stumm |
| fav1 | Rock Antenne Bayern | 512 KiB | **E7-Dauer bis EOF** (~65 s) |
| fav2 | Radio BOB! | 512 KiB | Baseline ~6 s vor Stall |

---

## Epistemik

| Claim | Status |
|-------|--------|
| NBT akzeptiert wiederholte BUSY-Retries über Minuten hinweg | **FACT (C)** — Hörbeleg ~65 s bis EOF |
| Ohne Stall bleibt ~6 s Ringfenster | **FACT (C)** |
| Stall verlangsamt Menü/Enumeration spürbar | **FACT (C)** — ~20 s bis Dateien |
| Alle Stationen gleich gut unter Stall | **REJECTED / offen** — Bayern ja, Rock Antenne in Session nein |
| Autoplay/Next ohne frischen Kopf liefert Ton | **REJECTED** in dieser Session |
| Q11 Brownout vs Soft-Reset | weiter **UNKNOWN** (kein UART-Log) |

---

## Offene Punkte / nächster Feldblock

1. **Rock Antenne (8 MiB):** warum kein Dauerstrom (Play-Detect Mid-File, Stall-Scope, Prefetch)?  
2. **`maxMs`↑** (2000/5000) gegen kurze Unterbrechungen testen.  
3. Menü-Latenz unter Stall budgetieren / Stall nicht auf Meta-LBAs.  
4. Autoplay → nächster Slot: Lead-Bytes / Head-Snap.  
5. UART Q11 bei nächstem Klasse-B optional nachholen.  
6. Lab: L2 Partial erneut; Feld: Wiederholung E7 mit Telemetrie-Poll während der 65 s.

---

## Kontroll-Stichprobe nach Exit (17:15)

OTG neu (keine Stall-Schärfung): Operator **BOB · Bild + ~6 s Ton**.  
Status: `stall.enable=false`, Serial `PD0229`.  

→ **A/B bestätigt:** ohne Stall wieder klassisches Ringfenster; die ~65 s waren Stall/E7, nicht Zufall.

## Geräte-Ende

- FW bleibt **`0.4.48-dev`** auf `.89`  
- **`stallEnable=false`** (Exit + Kontrollstichprobe)  
- Serial zuletzt `PD0229`

## Verweise

- Lab PC-E7: [`../../artifacts-2026-10-12-lab/lab-e7-ladder/ERGEBNIS.md`](../../artifacts-2026-10-12-lab/lab-e7-ladder/ERGEBNIS.md)  
- Maßnahmen: [`../../../planung/MASSNAHMEN-E7-AUDIT-ABGLEICH-2026-10-12.md`](../../../planung/MASSNAHMEN-E7-AUDIT-ABGLEICH-2026-10-12.md)  
- Stall-Spec: [`../../../planung/STALL-BUILD-SPEC-2026-10-08.md`](../../../planung/STALL-BUILD-SPEC-2026-10-08.md)
