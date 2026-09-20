#!/bin/bash
# Früher: IGNORE-quirks für ESP/RTL. Feldtest: Hub-Kaltstart trotzdem tot.
# Diese Datei entfernt Quirks wieder aus cmdline.txt (Aufräumen).
set -euo pipefail
BOOT_DIR=/boot/firmware
[[ -f "$BOOT_DIR/cmdline.txt" ]] || BOOT_DIR=/boot
CMD="$BOOT_DIR/cmdline.txt"
[[ -f "$CMD" ]] || exit 0
if ! grep -q 'usbcore.quirks=' "$CMD"; then
  echo "no usbcore.quirks in cmdline — ok"
  exit 0
fi
[[ -f "$CMD.bak-pidrive" ]] || cp "$CMD" "$CMD.bak-pidrive"
line=$(tr -d '\n' < "$CMD" | sed -E 's/[[:space:]]*usbcore\.quirks=[^[:space:]]*//g')
printf '%s\n' "$line" > "$CMD"
echo "removed usbcore.quirks from cmdline"
cat "$CMD"
