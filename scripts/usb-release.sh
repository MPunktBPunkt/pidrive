#!/bin/bash
# Nach Boot: USB-Quirks lösen und ESP/RTL erneut enumerieren.
# Komplement zu cmdline usbcore.quirks=…:k (IGNORE beim Kaltstart).
set -euo pipefail

log() { echo "[usb-release] $*"; }

QUIRKS_SYS=/sys/module/usbcore/parameters/quirks

# 1) IGNORE-Quirks leeren (falls Kernel das zur Laufzeit erlaubt)
if [[ -w "$QUIRKS_SYS" ]]; then
    cur=$(cat "$QUIRKS_SYS" 2>/dev/null || true)
    log "quirks before: ${cur:-(empty)}"
    echo -n "" > "$QUIRKS_SYS" 2>/dev/null || echo "" > "$QUIRKS_SYS" 2>/dev/null || true
    log "quirks after: $(cat "$QUIRKS_SYS" 2>/dev/null || echo '?')"
else
    log "quirks sysfs not writable — nur authorize/rebind"
fi

# 2) Externe Hubs kurz rebinden → Neu-Enumeration der Ports
rebind_hub() {
    local dev="$1"  # z.B. 1-1.3
    local hubdrv=/sys/bus/usb/drivers/hub
    [[ -d "/sys/bus/usb/devices/$dev" ]] || return 0
    [[ -e "$hubdrv/$dev" ]] || return 0
    log "rebind hub $dev"
    echo "$dev" > "$hubdrv/unbind" 2>/dev/null || true
    sleep 1
    echo "$dev" > "$hubdrv/bind" 2>/dev/null || true
}

# Genesys / typische Downstream-Hubs unter dem Pi-Root-Hub (nicht usb1/usb2 selbst)
for d in /sys/bus/usb/devices/*; do
    [[ -f "$d/idVendor" ]] || continue
    v=$(cat "$d/idVendor" 2>/dev/null || true)
    # 05e3 = Genesys Hub, 2109 = VIA (Pi onboard oft) — nur Genesys rebinden
    if [[ "$v" == "05e3" ]]; then
        rebind_hub "$(basename "$d")"
    fi
done

sleep 2
udevadm settle --timeout=15 2>/dev/null || true

# 3) authorize falls noch 0
n=0
for d in /sys/bus/usb/devices/*; do
    [[ -f "$d/idVendor" ]] || continue
    v=$(cat "$d/idVendor" 2>/dev/null || true)
    p=$(cat "$d/idProduct" 2>/dev/null || true)
    case "$v:$p" in
        303a:*|0bda:2838|0bda:2832|1a86:*)
            auth="$d/authorized"
            if [[ -f "$auth" ]] && [[ "$(cat "$auth")" == "0" ]]; then
                log "authorize $(basename "$d") $v:$p"
                echo 1 > "$auth"
            fi
            n=$((n + 1))
            ;;
    esac
done

udevadm settle --timeout=10 2>/dev/null || true
log "done (peripherals_seen=$n)"
# Bridge nicht synchron starten — sonst Deadlock:
# usb-release ← bluetooth ← core ← pump_bridge ← usb-release
if [[ -e /dev/ttyACM0 ]]; then
    systemctl start --no-block pidrive_pump_bridge.service 2>/dev/null || true
fi
exit 0
