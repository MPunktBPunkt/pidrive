#!/usr/bin/env bash
# Keep PUMP bridge alive when systemd unit is inactive (no sudo for restart).
# Install: crontab -e → @reboot /home/pidrive/ensure_pump_bridge.sh
#          */2 * * * * /home/pidrive/ensure_pump_bridge.sh
set -euo pipefail
LOG=/tmp/pump_bridge_manual.log
PIDFILE=/tmp/pump_bridge_manual.pid
HOST="${PUMP_HOST:-192.168.178.89}"
PORT="${PUMP_TCP_PORT:-9090}"
BIN=/home/pidrive/pump_bridge.py

if systemctl is-active --quiet pidrive_pump_bridge 2>/dev/null; then
  exit 0
fi
if pgrep -f '/home/pidrive/pump_bridge.py' >/dev/null 2>&1; then
  exit 0
fi
if [[ ! -f "$BIN" ]]; then
  echo "missing $BIN" >&2
  exit 1
fi
nohup /usr/bin/python3 -u "$BIN" \
  --transport tcp --host "$HOST" --tcp-port "$PORT" \
  --interval 0.5 --bitrate 48k >>"$LOG" 2>&1 </dev/null &
echo $! >"$PIDFILE"
echo "$(date -Is) started pid=$! host=$HOST" >>"$LOG"
