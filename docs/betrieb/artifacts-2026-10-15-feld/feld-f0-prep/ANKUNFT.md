# Ankunft · F0 starten (Auto-Pi)

ESP `.89` im Heim-WLAN. **Ziel: OTA 0.4.51 → Smoke → F0 B0…B3.**  
Stall bleibt **aus**.

```bash
ssh pidrive@192.168.178.105
cd ~/pidrive && git pull --ff-only || true
# Sync falls nötig:
# tar xzf /tmp/SYNC-TO-PI-F0.tgz -C ~/pidrive 2>/dev/null || true
cd ~/pidrive/docs/betrieb/artifacts-2026-10-15-feld/feld-f0-prep
./f0-check.sh before
```

### P1 — OTA 0.4.51 (einmal)

Watcher (Desktop, wartet auf Auto-WLAN):

```bash
cd ~/projects/pidrive/docs/betrieb/artifacts-2026-10-15-feld/feld-f0-prep
./ota-f0-051.sh          # wartet; nach HTTP-200 oft Minuten offline → Retry ohne Reflash
# Log: ota-f0-051.log · Artefakte: ota-YYYYMMDD-HHMMSS/
```

Danach auf dem Auto-Pi:

```bash
./f0-check.sh after-ota
# Pflicht: version enthält 0.4.51, stall_enable=false
./mark.sh "OTA 0.4.51 stall off OK"
```

Smoke (ohne Matrix): Stick/ESP mounten, Menü, **eine** Station von Kopf tippen → Ton?  
Nein → Abort, kein F0.

### P2 — F0

```bash
./run-f0.sh poll 1200
# zweites Terminal:
./mark.sh "B0 control P>>0 then replug"
# … B0 durchspielen, dann B1/B2/B3 mit:
./f0-identity.sh serial    # oder label / volume-id
./f0-check.sh after-B1
./mark.sh "B1 ear + playingUid"
```

### Abort

- Weiße LED / Serial-Sprung → **Klasse B**, Lauf verwerfen  
- `stall_enable=true` → sofort aus, kein Claim  
- Mehrere Identity-Felder driftieren → Isolation FAIL, Lauf ungültig  

Pocket: `GO.md` · Auswertung: `PROTOKOLL.md` → `ERGEBNIS.md`
