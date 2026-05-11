#!/bin/bash
# inject_trigger.sh — PiDrive Trigger direkt injizieren
# Verwendung: ./tools/inject_trigger.sh nav_down
CMD_FILE="/tmp/pidrive_cmd"
if [ -z "$1" ]; then
    echo "Verwendung: $0 <trigger>"
    echo "Beispiele: nav_down | nav_up | enter | back | vol_up | vol_down"
    echo "           radio_stop | play_dab:ROCK FM | dab_scan"
    exit 1
fi
echo -n "$1" > "$CMD_FILE"
echo "Trigger: $1"
