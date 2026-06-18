#!/bin/bash
# PiDrive: A2DP-Stack reparieren (br-connection-profile-unavailable)
# Siehe BluetoothError.md / TROUBLESHOOTING.md
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "Bitte mit sudo ausführen:"
    echo "  sudo bash $(readlink -f "$0" 2>/dev/null || echo "$0")"
    exit 1
fi

echo "=== PiDrive A2DP-Stack Reparatur ==="

# WirePlumber 0.5.x Profil-Syntax + BT ohne Telephony
mkdir -p /etc/wireplumber/wireplumber.conf.d
cat > /etc/wireplumber/wireplumber.conf.d/50-bt-pidrive.conf << 'EOF'
monitor.bluez.seat-monitoring = disabled
monitor.bluez.properties = {
    bluez5.roles = [ a2dp_source ]
    bluez5.codecs = [ sbc ]
    bluez5.auto-connect = [ a2dp_source ]
    bluez5.hw-offload-sco = false
}
EOF

cat > /etc/wireplumber/wireplumber.conf.d/10-no-reserve-pidrive.conf << 'EOF'
wireplumber.profiles = {
  main = {
    support.reserve-device = disabled
    monitor.alsa.reserve-device = disabled
  }
}
EOF

# bluez.lua: Seat-Monitoring aus (System-Mode ohne logind-Session)
if [ -f /usr/share/wireplumber/scripts/monitors/bluez.lua ]; then
    mkdir -p /etc/wireplumber/scripts/monitors
    cp /usr/share/wireplumber/scripts/monitors/bluez.lua \
       /etc/wireplumber/scripts/monitors/bluez.lua
    sed -i 's/config\.seat_monitoring = Core\.test_feature.*/config.seat_monitoring = false/' \
       /etc/wireplumber/scripts/monitors/bluez.lua
fi

echo "→ pipewire / pipewire-pulse / wireplumber / bluetooth neu starten …"
systemctl restart pipewire
sleep 2
systemctl restart pipewire-pulse
sleep 1
systemctl restart wireplumber
sleep 3
systemctl restart bluetooth
sleep 2

ENDPOINTS=$(dbus-send --system --print-reply --dest=org.bluez / \
    org.freedesktop.DBus.ObjectManager.GetManagedObjects 2>/dev/null \
    | grep -c MediaEndpoint1 || true)

if [ "${ENDPOINTS:-0}" -gt 0 ]; then
    echo "OK: ${ENDPOINTS} MediaEndpoint(s) bei BlueZ registriert."
    echo "→ Jetzt: pidrivectl bt connect 00:16:94:2E:85:DB"
    exit 0
fi

echo "WARN: Keine MediaEndpoints — D-Bus-Policy evtl. veraltet."
echo "→ sudo reboot   (Policy aus install.sh wird erst nach Reboot aktiv)"
exit 1
