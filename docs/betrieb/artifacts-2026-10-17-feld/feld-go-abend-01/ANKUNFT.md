# Ankunft · 30 s

```bash
# auf Auto-Pi .105
cd ~/feld-go-abend-01
bash wait-esp89.sh          # wartet bis .89 online + Snapshot
less GO.md                  # Reihenfolge M20 → M22 → M24
```

Laptop (Repo):
```bash
cd ~/projects/pidrive
# Status
curl -s http://192.168.178.89/api/status | python3 -c "import sys,json;d=json.load(sys.stdin);m=d.get('msc')or{};print(d['version'],d['resetReason'],d['otgUp'],m.get('bpbVolumeId'),m.get('usbSerial'))"
# Poll während Stecken
python3 tools/feld_status_poll.py --esp http://192.168.178.89 \
  -o docs/betrieb/artifacts-2026-10-17-feld/feld-go-abend-01/m20-repro/poll.jsonl \
  --interval 0.7 --seconds 90 --print
# M24 nach OTG-raus
python3 tools/feld_m24_volume_id.py --esp http://192.168.178.89 --apply \
  -o docs/betrieb/artifacts-2026-10-17-feld/feld-go-abend-01/m24-volume-id
```
