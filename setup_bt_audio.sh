#!/bin/bash
# PiDrive Bluetooth Audio Setup
# Konfiguriert PulseAudio System-Daemon für BT A2DP

set -e
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
ok()   { echo -e "  ${GREEN}✓${NC} $*"; }
warn() { echo -e "  ${YELLOW}⚠${NC} $*"; }
err()  { echo -e "  ${RED}✗${NC} $*"; }

echo "PiDrive BT Audio Setup"
echo "======================"

# 1. pulse-User in bluetooth-Gruppe
if id pulse >/dev/null 2>&1; then
    usermod -aG bluetooth pulse 2>/dev/null || true
    ok "pulse-User in bluetooth-Gruppe"
fi

# 2. DBus Policy für PulseAudio → Bluetooth
mkdir -p /etc/dbus-1/system.d
cat > /etc/dbus-1/system.d/pulseaudio-bluetooth.conf << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE busconfig PUBLIC "-//freedesktop//DTD D-Bus Bus Configuration 1.0//EN"
    "http://www.freedesktop.org/standards/dbus/1.0/busconfig.dtd">
<busconfig>
  <policy user="pulse">
    <allow own="org.pulseaudio.Server"/>
    <allow send_destination="org.bluez"/>
    <allow send_interface="org.bluez.Profile1"/>
    <allow send_interface="org.bluez.MediaEndpoint1"/>
    <allow send_interface="org.bluez.MediaTransport1"/>
  </policy>
  <policy context="default">
    <allow send_destination="org.pulseaudio.Server"/>
  </policy>
</busconfig>
EOF
ok "DBus Policy gesetzt"

# 3. PulseAudio system.pa mit BT-Modulen
mkdir -p /etc/pulse
cat > /etc/pulse/system.pa << 'EOF'
.fail
load-module module-device-restore
load-module module-stream-restore
load-module module-card-restore
load-module module-alsa-card device_id=0
load-module module-bluetooth-policy
load-module module-bluetooth-discover
load-module module-native-protocol-unix auth-anonymous=1 socket=/var/run/pulse/native
EOF
ok "PulseAudio system.pa konfiguriert"

# 4. PulseAudio runtime-Verzeichnis
mkdir -p /var/run/pulse
chown pulse:pulse /var/run/pulse 2>/dev/null || true
ok "PulseAudio runtime-Verzeichnis"

# 5. PulseAudio systemd-Service
cat > /etc/systemd/system/pulseaudio.service << 'EOF'
[Unit]
Description=PulseAudio System Daemon (BT Audio)
After=bluetooth.target dbus.service

[Service]
Type=notify
ExecStart=/usr/bin/pulseaudio --system --realtime --disallow-exit --no-cpu-limit \
    --daemonize=no --log-level=warn
Restart=on-failure
RestartSec=3
LimitRTPRIO=99
LimitNICE=-15
RuntimeDirectory=pulse
RuntimeDirectoryMode=0755

[Install]
WantedBy=multi-user.target
EOF

# 6. Raspotify → PulseAudio (PULSE_SERVER über Socket)
if [ -f /etc/raspotify/conf ]; then
    # PulseAudio Socket-Pfad setzen
    if grep -q "^LIBRESPOT_BACKEND" /etc/raspotify/conf; then
        sed -i 's|^LIBRESPOT_BACKEND=.*|LIBRESPOT_BACKEND=alsa|' /etc/raspotify/conf
    else
        echo 'LIBRESPOT_BACKEND=alsa' >> /etc/raspotify/conf
    fi
    if grep -q "^LIBRESPOT_DEVICE" /etc/raspotify/conf; then
        sed -i 's|^LIBRESPOT_DEVICE=.*|LIBRESPOT_DEVICE=default|' /etc/raspotify/conf
    else
        echo 'LIBRESPOT_DEVICE=default' >> /etc/raspotify/conf
    fi
    ok "Raspotify: LIBRESPOT_DEVICE=default"
fi

# PulseAudio env für raspotify.service
if [ -f /lib/systemd/system/raspotify.service ]; then
    if ! grep -q "PULSE_SERVER" /lib/systemd/system/raspotify.service; then
        sed -i '/\[Service\]/a Environment=PULSE_SERVER=unix:/var/run/pulse/native' \
            /lib/systemd/system/raspotify.service
        ok "raspotify.service: PULSE_SERVER gesetzt"
    fi
fi

# 7. Services neu starten
systemctl daemon-reload
systemctl restart dbus 2>/dev/null || true
sleep 1
systemctl restart bluetooth 2>/dev/null || true
sleep 1
systemctl enable pulseaudio 2>/dev/null || true
systemctl restart pulseaudio 2>/dev/null || true
sleep 2
systemctl restart raspotify 2>/dev/null || true

# 8. Status prüfen
if systemctl is-active --quiet pulseaudio; then
    ok "PulseAudio läuft"
    # Sinks anzeigen
    SINKS=$(PULSE_SERVER=unix:/var/run/pulse/native pactl list sinks short 2>/dev/null || true)
    if [ -n "$SINKS" ]; then
        ok "PulseAudio Sinks:"
        echo "$SINKS" | while read line; do echo "    $line"; done
    fi
else
    err "PulseAudio läuft nicht — prüfe: journalctl -u pulseaudio -n 20"
    exit 1
fi

echo ""
echo "BT Audio Setup abgeschlossen!"
echo "Nächste Schritte:"
echo "  1. Kopfhörer in BT-Pairing-Modus"
echo "  2. bluetoothctl connect 00:16:94:2E:85:DB"
echo "  3. Im Webinterface: Verbindungen → Geräte scannen"
