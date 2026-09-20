#!/bin/bash
# Fügt usbcore.quirks für ESP/RTL in cmdline.txt ein (IGNORE bis usb-release).
set -euo pipefail
BOOT_DIR=/boot/firmware
[[ -f "$BOOT_DIR/cmdline.txt" ]] || BOOT_DIR=/boot
CMD="$BOOT_DIR/cmdline.txt"
[[ -f "$CMD" ]] || { echo "no cmdline"; exit 1; }

QUIRKS="usbcore.quirks=0bda:2838:k,0bda:2832:k,303a:1001:k,1a86:55d3:k"
# Backup einmalig
[[ -f "$CMD.bak-pidrive" ]] || cp "$CMD" "$CMD.bak-pidrive"

line=$(cat "$CMD" | tr -d '\n')
# alte pidrive-quirks entfernen
line=$(echo "$line" | sed -E 's/[[:space:]]*usbcore\.quirks=[^[:space:]]*//g')
line="$line $QUIRKS"
echo "$line" > "$CMD"
echo "cmdline updated:"
cat "$CMD"
