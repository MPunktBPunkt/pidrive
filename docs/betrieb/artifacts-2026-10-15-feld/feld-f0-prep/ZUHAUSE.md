# Zuhause · Sync F0-Prep auf Auto-Pi

```bash
# Desktop:
cd ~/projects/pidrive
tar czf /tmp/SYNC-TO-PI-F0.tgz \
  docs/betrieb/artifacts-2026-10-15-feld \
  docs/fahrzeug/HU-Technical-Facts.md
scp /tmp/SYNC-TO-PI-F0.tgz pidrive@192.168.178.105:/tmp/
# Pi:
ssh pidrive@192.168.178.105
cd ~/pidrive && git pull --ff-only || true
tar xzf /tmp/SYNC-TO-PI-F0.tgz -C ~/pidrive
cd docs/betrieb/artifacts-2026-10-15-feld/feld-f0-prep
chmod +x f0-check.sh f0-identity.sh run-f0.sh mark.sh
./f0-check.sh before
```

Weiter: `ANKUNFT.md` → OTA 0.4.51 → `GO.md`.
