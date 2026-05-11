#!/bin/bash
# watch_avrcp.sh — AVRCP-Events live beobachten
while true; do
    clear
    echo "=== AVRCP Live [$(date +%H:%M:%S)] ==="
    if [ -f /tmp/pidrive_avrcp_events.json ]; then
        python3 -c "
import json,datetime as dt
d=json.load(open("/tmp/pidrive_avrcp_events.json"))
evs=d.get("events",[])
print(f"Events gesamt: {d.get(chr(39)total{chr(39)},0)}")
for e in evs[-15:]:
  ts=dt.datetime.fromtimestamp(e["ts"]).strftime("%H:%M:%S")
  t=e.get("trigger","") or "(ignoriert)"
  print(f"  [{ts}] #{e[chr(39)id{chr(39)}]:>3} {e[chr(39)event{chr(39)]:<15} ctx={e.get(chr(39)context{chr(39)},chr(39)?{chr(39)):<10} -> {t}")
"
    else
        echo "(Warte auf ersten AVRCP-Event...)"
    fi
    pidrivectl quick 2>/dev/null
    sleep 1
done
