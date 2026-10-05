# Feld Abend AV — 2026-10-05 ~15:30–15:51

**FW:** `0.4.45-dev` · Auto `.89` · Serials **PD0065→PD0069** · Seed **aus** · Bridge `.105` `--msc-lock`  
**Artefakte:** dieser Ordner · EAR: [`../FELD-ABEND-EAR-2026-10-05.md`](../FELD-ABEND-EAR-2026-10-05.md)

## Ergebnis (Ampel)

| Check | Ergebnis |
|-------|----------|
| C′ wiederholt? | **nein** (korrekt) |
| Gate Sender-Slots | **PASS** (mehrfach) |
| Erstes Session-`MSC_MAP_FROZEN` geloggt | **PASS** — Rock/Bayern/BOB/Menue |
| AV / Ohr hörbar | **FAIL** |
| Klassifikation | Gate **A PASS** · AV **B FAIL Fenster/Arm** |

**Ein Satz:** Meta/Lock ist abends behoben; hörbares MPEG am HU nicht erreicht — einmal Producer+Fenster-Miss, sonst oft kein Stream-Arm trotz Sender-Seite.

## 1. Gate (Baustelle A)

**Ankunft:** Alte Bridge-Instanz seit 4.10. frozen auf Meta (`frozen_reject` n≈2700+) gegen Rock — gleiche Falle wie Morgen/Lab D.

**Recovery:** Bridge-Prozess kill + frisch starten (kein USB nötig) → sofort  
`MSC_MAP_FROZEN [Rock Antenne,Rock Antenne Bayern,Radio BOB!,Menue]`  
+ `slotMap` gleich. Siehe [`GATE-PASS.txt`](GATE-PASS.txt), [`bridge-gate.txt`](bridge-gate.txt).

Weitere Siegel nach RST/OTG (PD0067–PD0069) ebenfalls Rock — **Gate-Beweislücke „erstes Feld-FROZEN“ geschlossen**.

Operator 15:33 Unplug+RST wegen HU-Morgen-Cache: ok, Gate blieb Sender.

## 2. AV-Läufe (Baustelle B)

### 2.1 Positiv-Beleg Producer (15:41 Bayern)

Nach BOB→Bayern-Next:

- `play=Rock Antenne Bayern` / `fav1`
- Bridge: `audio_start` + ffmpeg Rock-Antenne-Bayern
- `stream.active=true`
- **Ohr: kein Ton**, LED beim Wechsel

Correlate-1540 / Status:

| Größe | Wert |
|-------|------|
| hostAbsCursor | 253952 |
| absBase..absEnd | wandernd; Host oft außerhalb |
| streamBytes | 253952 |
| underruns | 253952 |
| liveBytes | **0** |
| host_in_window | **false** |

→ **FAIL Fenster (B):** Producer an, Host-Cursor/Underrun, kein Live im Fenster.

Artefakte: [`status-1541-bayern-stream-active-no-audio.json`](status-1541-bayern-stream-active-no-audio.json), [`correlate-1540/`](correlate-1540/), [`OPERATOR-1541-bayern-led-no-audio.txt`](OPERATOR-1541-bayern-led-no-audio.txt).

### 2.2 Arm fehlt (mehrere Versuche)

| Zeit | Aktion | stream.active | Ohr / LED |
|------|--------|---------------|-----------|
| 15:34–35 | BOB Autoplay, Rock | false | kein Ton; Rock LED kurz (cold) |
| 15:38 | Bayern (schon gelesen) | false | kein LED-Blink |
| 15:40 | RST + BOB | false | UI „läuft“, kein Ton |
| 15:43–45 | OTG Rock PD0068 | false | wartet auf Ton; cold Rock ~MiB |
| 15:46–47 | BOB tippen | false | kein Ton, keine LED |
| 15:48–49 | Remount PD0069 → Bayern tippen | false | kein Ton |
| 15:51 | Bayern→Rock Next | false | **LED** vor Bayern-Ende / Rock-Start (= cold_body) |

Typisch: `cold_body_burst … ev=not_from_head` auf fav0/fav1, **kein** `play_uid`/`audio_start` für den getippten Slot.

## 3. Was belegt / was nicht

**Belegt:**

1. Frische Bridge oder Unplug heilt Meta-Erstsiegel im Feld (wie Lab).  
2. Erstes Feld-`MSC_MAP_FROZEN` Rock dokumentiert.  
3. Nach Gate: AV-Fail ist **nicht** Meta — Fenster/Arm (B).  
4. Mindestens ein Feld-Lauf mit Live-ffmpeg + `stream.active` ohne Ohr (`liveBytes=0`).

**Nicht belegt / nicht behaupten:**

- „Alle AV-Probleme erklärt“  
- Detect-Policy-Änderung nötig vor weiterem Hörfenster-Versuch  
- Sequenz-GO freigegeben

## 4. Nächste Schritte (nach Freeze)

1. Baustelle B: warum `hostAbs` außerhalb / nur Underrun; warum oft kein Arm nach Tip trotz Sender-Slots.  
2. Detect/Arm unverändert bis reproduzierbarer Hörbeweis.  
3. Freeze hält (Ring/PSRAM/Pacing/Detect/Lock-Code).

```
Gate Abend PASS (FROZEN Rock geloggt)
AV Ohr FAIL (Fenster einmal; Arm oft fehlend)
Freeze hält
```
