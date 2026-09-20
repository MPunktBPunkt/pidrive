#!/bin/bash
# Freigabe verzögerter USB-Geräte (ESP / RTL-SDR) nach dem Boot.
# Wird von pidrive-usb-release.service aufgerufen.
set -euo pipefail

log() { echo "[usb-release] $*"; }

release_one() {
    local d="$1"
    local auth="$d/authorized"
    [[ -f "$auth" ]] || return 0
    local cur
    cur=$(cat "$auth" 2>/dev/null || echo 1)
    if [[ "$cur" == "0" ]]; then
        log "authorize $(basename "$d") vendor=$(cat "$d/idVendor" 2>/dev/null) product=$(cat "$d/idProduct" 2>/dev/null)"
        echo 1 > "$auth"
    fi
}

n=0
for d in /sys/bus/usb/devices/*; do
    [[ -f "$d/idVendor" ]] || continue
    v=$(cat "$d/idVendor" 2>/dev/null || true)
    p=$(cat "$d/idProduct" 2>/dev/null || true)
    case "$v:$p" in
        303a:*|0bda:2838|0bda:2832|1a86:*)
            release_one "$d"
            n=$((n + 1))
            ;;
    esac
done

udevadm settle --timeout=10 2>/dev/null || true
log "done (matched=$n)"
# Bridge starten falls ACM jetzt da
if [[ -e /dev/ttyACM0 ]]; then
    systemctl start pidrive_pump_bridge.service 2>/dev/null || true
fi
exit 0
