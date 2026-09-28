#!/usr/bin/env bash
# Measure whether the Pulse/PipeWire default-sink monitor carries FM/DAB audio
# (Baustelle B — field 2026-09-28: ffmpeg may capture silence via mailbox.stereo-fallback).
set -euo pipefail
PULSE_SERVER="${PULSE_SERVER:-unix:/run/user/$(id -u)/pulse/native}"
export PULSE_SERVER
MON="$(pactl get-default-sink 2>/dev/null || true).monitor"
if [[ -z "${MON%.monitor}" || "$MON" == ".monitor" ]]; then
  echo "no default sink" >&2
  exit 1
fi
echo "monitor=$MON"
echo "Play FM/DAB for ~5s, then measuring…"
ffmpeg -hide_banner -nostats -f pulse -i "$MON" -t 5 -af volumedetect -f null - 2>&1 \
  | grep -E 'mean_volume|max_volume|Input|error|Error' || true
