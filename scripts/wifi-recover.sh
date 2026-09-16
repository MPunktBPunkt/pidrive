#!/bin/bash
# PiDrive: WLAN nach Stromausfall / hängendem wlan0 wiederbeleben
# Typischer Fall: eth0 hat IP, wlan0 nicht assoziiert / ohne IPv4.
# Credentials kommen aus dem OS (wpa_supplicant / NetworkManager) — hier nur Revive.
#
# Aufruf:
#   sudo bash scripts/wifi-recover.sh
#   sudo systemctl start pidrive-wifi-recover.service
set -euo pipefail

WLAN_IF="${PIDRIVE_WLAN_IF:-wlan0}"
WAIT_SEC="${PIDRIVE_WIFI_RECOVER_WAIT:-8}"

log() { echo "[wifi-recover] $*"; }

if [ "$(id -u)" -ne 0 ]; then
    echo "Bitte mit sudo ausführen:"
    echo "  sudo bash $(readlink -f "$0" 2>/dev/null || echo "$0")"
    exit 1
fi

if [ ! -d "/sys/class/net/$WLAN_IF" ]; then
    log "Interface $WLAN_IF fehlt — nichts zu tun"
    exit 0
fi

wlan_ipv4() {
    ip -4 -o addr show dev "$WLAN_IF" 2>/dev/null | awk '{print $4}' | head -1
}

wlan_ssid() {
    iwgetid -r "$WLAN_IF" 2>/dev/null || true
}

wlan_ok() {
    local ip ssid
    ip=$(wlan_ipv4)
    ssid=$(wlan_ssid)
    [ -n "$ip" ] && [ -n "$ssid" ]
}

report() {
    local ip ssid state
    ip=$(wlan_ipv4)
    ssid=$(wlan_ssid)
    state=$(cat "/sys/class/net/$WLAN_IF/operstate" 2>/dev/null || echo "?")
    log "Status $WLAN_IF: operstate=$state ssid=${ssid:--} ipv4=${ip:--}"
}

if wlan_ok; then
    report
    log "WLAN bereits ok — keine Aktion"
    exit 0
fi

log "WLAN nicht ok — Recovery starten"
report

# Soft-Block / Link
command -v rfkill >/dev/null 2>&1 && rfkill unblock wifi 2>/dev/null || true
command -v rfkill >/dev/null 2>&1 && rfkill unblock all 2>/dev/null || true
ip link set "$WLAN_IF" down 2>/dev/null || true
sleep 1
ip link set "$WLAN_IF" up 2>/dev/null || true

# Stack-spezifisch: NetworkManager bevorzugt, sonst wpa_supplicant + dhcpcd
if systemctl is-active --quiet NetworkManager 2>/dev/null; then
    log "Pfad: NetworkManager"
    nmcli radio wifi on 2>/dev/null || true
    nmcli device set "$WLAN_IF" managed yes 2>/dev/null || true
    nmcli device connect "$WLAN_IF" 2>/dev/null || true
    # Falls Connect scheitert: kurzer Networking-Reset nur für WiFi
    if ! wlan_ok; then
        nmcli networking off 2>/dev/null || true
        sleep 2
        nmcli networking on 2>/dev/null || true
        sleep 2
        nmcli device connect "$WLAN_IF" 2>/dev/null || true
    fi
else
    log "Pfad: wpa_supplicant / dhcpcd"
    if systemctl list-unit-files "wpa_supplicant@${WLAN_IF}.service" 2>/dev/null | grep -q wpa_supplicant; then
        systemctl restart "wpa_supplicant@${WLAN_IF}.service" 2>/dev/null || true
    elif systemctl list-unit-files wpa_supplicant.service 2>/dev/null | grep -q wpa_supplicant.service; then
        systemctl restart wpa_supplicant.service 2>/dev/null || true
    fi
    if command -v wpa_cli >/dev/null 2>&1; then
        wpa_cli -i "$WLAN_IF" reconfigure 2>/dev/null || true
        wpa_cli -i "$WLAN_IF" reconnect 2>/dev/null || true
    fi
    if systemctl is-active --quiet dhcpcd 2>/dev/null; then
        dhcpcd -n "$WLAN_IF" 2>/dev/null || systemctl restart dhcpcd 2>/dev/null || true
    elif command -v dhclient >/dev/null 2>&1; then
        dhclient -v "$WLAN_IF" 2>/dev/null || true
    fi
fi

# Kurz warten und erneut prüfen; bei Bedarf einmal Firmware-Zyklus (brcmfmac)
i=0
while [ "$i" -lt "$WAIT_SEC" ]; do
    if wlan_ok; then
        report
        log "WLAN wieder erreichbar"
        exit 0
    fi
    sleep 1
    i=$((i + 1))
done

if ! wlan_ok && [ -d /sys/module/brcmfmac ]; then
    log "Noch kein Erfolg — brcmfmac kurz neu laden"
    ip link set "$WLAN_IF" down 2>/dev/null || true
    modprobe -r brcmfmac 2>/dev/null || true
    sleep 2
    modprobe brcmfmac 2>/dev/null || true
    sleep 3
    ip link set "$WLAN_IF" up 2>/dev/null || true
    if systemctl is-active --quiet NetworkManager 2>/dev/null; then
        nmcli device connect "$WLAN_IF" 2>/dev/null || true
    else
        if command -v wpa_cli >/dev/null 2>&1; then
            wpa_cli -i "$WLAN_IF" reconfigure 2>/dev/null || true
            wpa_cli -i "$WLAN_IF" reconnect 2>/dev/null || true
        fi
        systemctl is-active --quiet dhcpcd 2>/dev/null && dhcpcd -n "$WLAN_IF" 2>/dev/null || true
    fi
    sleep "$WAIT_SEC"
fi

report
if wlan_ok; then
    log "WLAN wieder erreichbar"
    exit 0
fi

log "WARN: WLAN weiterhin ohne SSID/IPv4 — Credentials/Router prüfen, dann: journalctl -u pidrive-wifi-recover -b"
exit 1
