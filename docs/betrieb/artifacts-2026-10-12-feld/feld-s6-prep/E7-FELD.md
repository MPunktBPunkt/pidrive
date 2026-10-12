# E7 am NBT — nur mit explizitem Go

**Voraussetzung:** Q11/Klasse-A-Pfad in s6 belegt (wenigstens eine stabile Episode ohne weiße LED unter leichtem Stecken).  
**Lab-Referenz:** PC L1 `sg p50≈735 ms`, `undDelta=0` @6000 B/s — [`../../artifacts-2026-10-12-lab/lab-e7-ladder/ERGEBNIS.md`](../../artifacts-2026-10-12-lab/lab-e7-ladder/ERGEBNIS.md).

## Freeze ohne Go

Feld bleibt `0.4.46-dev`. Kein Stall.

## Mit Go — Flash

```bash
cd ~/pidrive/docs/betrieb/artifacts-2026-10-12-feld/feld-s6-prep
./ota-stall-048.sh          # lädt dist-Bin auf .89
./s6-check.sh post-ota      # version=0.4.48-dev, stall.enable=false
```

Soll: Verhalten wie 0.4.46 bis Stall eingeschaltet wird.

## Leiter (kurz, Auto)

| Schritt | Config | Beobachten |
|---------|--------|------------|
| E7-0 | `stallEnable=false` | REPLUG/Ohr Baseline wie bisher |
| E7-A1 | an, `stallMaxMs=500`, chunk 4096 | HU bricht ab? Medium weg? `stall.timeouts`/`retries` |
| E7-A2 | `stallMaxMs=1000` | wie Lab L1-Budget (~683 ms/4 KiB) |
| E7-B | Producer @32k/48k live | Ohr länger als Ringfenster? `undDelta`/Stille? |

```bash
# Beispiel Config (nach OTA):
curl -s -X POST http://192.168.178.89/api/config -H 'Content-Type: application/json' \
  -d '{"stallEnable":true,"stallScope":1,"stallTimer":0,"stallMaxMs":1000,"stallChunkBytes":4096,"stallRetryMs":2}'
./s6-check.sh stall-on
./mark.sh "E7-A2 maxMs=1000"
# nach Episode Stall wieder aus:
curl -s -X POST http://192.168.178.89/api/config -H 'Content-Type: application/json' \
  -d '{"stallEnable":false}'
```

**Fail-Gate:** HU wirft Medium / Dauer-Reset / kein Ton trotz Klasse A → Stall aus, Episode als E7-FAIL markieren, **nicht** weiterdrehen. PSRAM bleibt Plan B.

**Pass-Hint:** Hörfenster deutlich >8 s @48k bzw. >12 s @32k bei laufendem Stream + `stall.retries`↑ ohne Reset.
