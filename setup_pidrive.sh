#!/bin/bash
# ============================================================
# PiDrive Setup Script
# Raspberry Pi 3B/4 + Joy-IT TFT3.5 Display
# ============================================================
# Aufruf: sudo bash setup_pidrive.sh
# Idempotent: Kann mehrfach ausgefuehrt werden
# ============================================================

set -e

# ── Farben ────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# ── Hilfsfunktionen ───────────────────────────────────────────
ok()   { echo -e "${GREEN}  ✓ ${1}${NC}"; }
fail() { echo -e "${RED}  ✗ ${1}${NC}"; }
info() { echo -e "${CYAN}  → ${1}${NC}"; }
warn() { echo -e "${YELLOW}  ⚠ ${1}${NC}"; }
step() { echo -e "\n${BOLD}${BLUE}━━━ ${1} ━━━${NC}"; }
ask()  { echo -e "${YELLOW}  ? ${1}${NC}"; }

# ── Root-Check ────────────────────────────────────────────────
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Bitte als root ausfuehren: sudo bash $0${NC}"
    exit 1
fi

# Echter User (nicht root)
REAL_USER=${SUDO_USER:-pi}
REAL_HOME=$(eval echo "~$REAL_USER")

# ── Status-Tracking ───────────────────────────────────────────
ERRORS=()
WARNINGS=()
MANUAL_STEPS=()

add_error()   { ERRORS+=("$1"); }
add_warning() { WARNINGS+=("$1"); }
add_manual()  { MANUAL_STEPS+=("$1"); }

# ── Banner ────────────────────────────────────────────────────
clear
echo -e "${BOLD}${BLUE}"
cat << 'EOF'
╔═══════════════════════════════════════════════╗
║         PiDrive Setup Script                ║
║   Raspberry Pi + Joy-IT TFT3.5 Display        ║
║         Spotify Connect via Raspotify         ║
╚═══════════════════════════════════════════════╝
EOF
echo -e "${NC}"

# ── Konfiguration abfragen ────────────────────────────────────
step "Konfiguration"

ask "WLAN SSID (leer = ueberspringen):"
read -r WIFI_SSID

if [ -n "$WIFI_SSID" ]; then
    ask "WLAN Passwort:"
    read -rs WIFI_PASS
    echo ""
fi

ask "Spotify Geraetename (Standard: PiDrive):"
read -r SPOTIFY_NAME
SPOTIFY_NAME=${SPOTIFY_NAME:-PiDrive}

ask "Hostname fuer den Pi (Standard: raspberrypi):"
read -r NEW_HOSTNAME
NEW_HOSTNAME=${NEW_HOSTNAME:-raspberrypi}

echo ""
info "Konfiguration:"
info "  WLAN SSID:    ${WIFI_SSID:-nicht konfiguriert}"
info "  Spotify Name: $SPOTIFY_NAME"
info "  Hostname:     $NEW_HOSTNAME"
echo ""
ask "Weiter? (j/n)"
read -r CONFIRM
if [ "$CONFIRM" != "j" ] && [ "$CONFIRM" != "J" ]; then
    echo "Abgebrochen."
    exit 0
fi

# ══════════════════════════════════════════════════════════════
# SCHRITT 1: System-Update
# ══════════════════════════════════════════════════════════════
step "1/12 System-Update"

info "apt update..."
if apt-get update -qq; then
    ok "apt update"
else
    add_error "apt update fehlgeschlagen"
    fail "apt update"
fi

info "apt upgrade..."
if DEBIAN_FRONTEND=noninteractive apt-get upgrade -y -qq; then
    ok "apt upgrade"
else
    add_warning "apt upgrade hatte Fehler"
    warn "apt upgrade"
fi

# ══════════════════════════════════════════════════════════════
# SCHRITT 2: Pakete installieren
# ══════════════════════════════════════════════════════════════
step "2/12 Pakete installieren"

PACKAGES=(
    python3-pygame
    python3-evdev
    python3-pip
    git
    cmake
    curl
    avahi-utils
    avahi-daemon
    evtest
    fbset
    bluetooth
    bluez
    rfkill
    wpasupplicant
    dhcpcd5
    build-essential
    libraspberrypi-dev
    tty
)

for pkg in "${PACKAGES[@]}"; do
    if dpkg -l "$pkg" 2>/dev/null | grep -q "^ii"; then
        ok "$pkg (bereits installiert)"
    else
        info "$pkg installieren..."
        if DEBIAN_FRONTEND=noninteractive apt-get install -y -qq "$pkg" 2>/dev/null; then
            ok "$pkg"
        else
            add_warning "$pkg konnte nicht installiert werden"
            warn "$pkg"
        fi
    fi
done

# ══════════════════════════════════════════════════════════════
# SCHRITT 3: Hostname setzen
# ══════════════════════════════════════════════════════════════
step "3/12 Hostname konfigurieren"

CURRENT_HOSTNAME=$(hostname)
if [ "$CURRENT_HOSTNAME" != "$NEW_HOSTNAME" ]; then
    echo "$NEW_HOSTNAME" > /etc/hostname
    sed -i "s/127.0.1.1.*/127.0.1.1\t$NEW_HOSTNAME/" /etc/hosts
    hostnamectl set-hostname "$NEW_HOSTNAME" 2>/dev/null || true
    ok "Hostname auf '$NEW_HOSTNAME' gesetzt (nach Reboot aktiv)"
else
    ok "Hostname ist bereits '$NEW_HOSTNAME'"
fi

# ══════════════════════════════════════════════════════════════
# SCHRITT 4: WLAN konfigurieren
# ══════════════════════════════════════════════════════════════
step "4/12 WLAN konfigurieren"

if [ -n "$WIFI_SSID" ]; then
    # wpa_supplicant.conf
    WPA_CONF="/etc/wpa_supplicant/wpa_supplicant.conf"
    if ! grep -q "ssid=\"$WIFI_SSID\"" "$WPA_CONF" 2>/dev/null; then
        cat > "$WPA_CONF" << EOF
country=DE
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1

network={
    ssid="$WIFI_SSID"
    psk="$WIFI_PASS"
}
EOF
        ok "wpa_supplicant.conf konfiguriert"
    else
        ok "WLAN '$WIFI_SSID' bereits konfiguriert"
    fi

    # rfkill unblock
    rfkill unblock wifi 2>/dev/null || true
    ip link set wlan0 up 2>/dev/null || true

    # WLAN Autostart Service
    cat > /etc/systemd/system/wlan-autostart.service << 'EOF'
[Unit]
Description=WLAN Autostart
After=network.target

[Service]
Type=oneshot
ExecStart=/usr/sbin/rfkill unblock wifi
ExecStart=/usr/sbin/ip link set wlan0 up
ExecStart=/usr/sbin/dhcpcd wlan0
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF
    systemctl daemon-reload
    systemctl enable wlan-autostart 2>/dev/null
    ok "WLAN Autostart Service eingerichtet"
else
    warn "WLAN nicht konfiguriert (uebersprungen)"
    add_manual "WLAN manuell konfigurieren: sudo raspi-config -> System Options -> Wireless LAN"
fi

# ══════════════════════════════════════════════════════════════
# SCHRITT 5: SPI und SSH aktivieren
# ══════════════════════════════════════════════════════════════
step "5/12 SPI und SSH aktivieren"

# SSH
systemctl enable ssh 2>/dev/null
systemctl start ssh 2>/dev/null
ok "SSH aktiviert"

# SPI
if ! grep -q "^dtparam=spi=on" /boot/config.txt; then
    echo "dtparam=spi=on" >> /boot/config.txt
    ok "SPI aktiviert"
else
    ok "SPI bereits aktiv"
fi

# I2C
if ! grep -q "^dtparam=i2c_arm=on" /boot/config.txt; then
    echo "dtparam=i2c_arm=on" >> /boot/config.txt
    ok "I2C aktiviert"
else
    ok "I2C bereits aktiv"
fi

# Bluetooth
systemctl enable bluetooth 2>/dev/null
systemctl start bluetooth 2>/dev/null
ok "Bluetooth Service aktiviert"

# ══════════════════════════════════════════════════════════════
# SCHRITT 6: /boot/config.txt konfigurieren
# ══════════════════════════════════════════════════════════════
step "6/12 /boot/config.txt konfigurieren"

# Backup
if [ ! -f /boot/config.txt.bak ]; then
    cp /boot/config.txt /boot/config.txt.bak
    ok "Backup erstellt: /boot/config.txt.bak"
fi

# camera_auto_detect=0
if grep -q "^camera_auto_detect=1" /boot/config.txt; then
    sed -i 's/^camera_auto_detect=1/camera_auto_detect=0/' /boot/config.txt
    ok "camera_auto_detect=0 gesetzt"
elif ! grep -q "camera_auto_detect" /boot/config.txt; then
    echo "camera_auto_detect=0" >> /boot/config.txt
    ok "camera_auto_detect=0 hinzugefuegt"
else
    ok "camera_auto_detect=0 bereits gesetzt"
fi

# display_auto_detect=0
if grep -q "^display_auto_detect=1" /boot/config.txt; then
    sed -i 's/^display_auto_detect=1/display_auto_detect=0/' /boot/config.txt
    ok "display_auto_detect=0 gesetzt"
elif ! grep -q "display_auto_detect" /boot/config.txt; then
    echo "display_auto_detect=0" >> /boot/config.txt
    ok "display_auto_detect=0 hinzugefuegt"
else
    ok "display_auto_detect=0 bereits gesetzt"
fi

# [all] Block am Ende sicherstellen
if ! grep -q "^dtoverlay=tft35a" /boot/config.txt; then
    warn "tft35a Overlay fehlt noch — wird von LCD35-show gesetzt (Schritt 7)"
fi

# HDMI Konfiguration
if ! grep -q "^hdmi_cvt=480 320" /boot/config.txt; then
    # Sicherstellen dass [all] Block existiert
    if ! grep -q "^\[all\]" /boot/config.txt; then
        echo "[all]" >> /boot/config.txt
    fi
    cat >> /boot/config.txt << 'EOF'
hdmi_force_hotplug=1
hdmi_group=2
hdmi_mode=87
hdmi_cvt=480 320 60 6 0 0 0
hdmi_drive=2
EOF
    ok "HDMI Aufloesung 480x320 konfiguriert"
else
    ok "HDMI Konfiguration bereits vorhanden"
fi

# max_framebuffers
if ! grep -q "^max_framebuffers=2" /boot/config.txt; then
    echo "max_framebuffers=2" >> /boot/config.txt
    ok "max_framebuffers=2 gesetzt"
else
    ok "max_framebuffers bereits gesetzt"
fi

# vc4-fkms-v3d auskommentieren falls aktiv (stoert Display)
if grep -q "^dtoverlay=vc4-fkms-v3d" /boot/config.txt; then
    sed -i 's/^dtoverlay=vc4-fkms-v3d/#dtoverlay=vc4-fkms-v3d/' /boot/config.txt
    ok "vc4-fkms-v3d deaktiviert (stoerte SPI Display)"
fi
if grep -q "^dtoverlay=vc4-kms-v3d" /boot/config.txt; then
    sed -i 's/^dtoverlay=vc4-kms-v3d/#dtoverlay=vc4-kms-v3d/' /boot/config.txt
    ok "vc4-kms-v3d deaktiviert (stoerte SPI Display)"
fi

# ══════════════════════════════════════════════════════════════
# SCHRITT 7: LCD-show Display-Treiber
# ══════════════════════════════════════════════════════════════
step "7/12 Display-Treiber (LCD-show)"

LCD_DIR="$REAL_HOME/LCD-show"

if [ ! -d "$LCD_DIR" ]; then
    info "LCD-show klonen..."
    sudo -u "$REAL_USER" git clone https://github.com/goodtft/LCD-show.git "$LCD_DIR"
    ok "LCD-show geklont"
else
    ok "LCD-show bereits vorhanden"
fi

# Pruefen ob Treiber bereits aktiv
if grep -q "^dtoverlay=tft35a" /boot/config.txt; then
    ok "TFT35 Treiber bereits in config.txt aktiv"
else
    warn "TFT35 Treiber noch nicht installiert"
    add_manual "Display-Treiber installieren: cd ~/LCD-show && sudo ./LCD35-show"
    add_manual "ACHTUNG: LCD35-show startet automatisch neu!"
fi

# ══════════════════════════════════════════════════════════════
# SCHRITT 8: Konsole unterdrücken (rc.local)
# ══════════════════════════════════════════════════════════════
step "8/12 Konsolen-Unterdrückung"

RC_LOCAL="/etc/rc.local"

if [ ! -f "$RC_LOCAL" ]; then
    cat > "$RC_LOCAL" << 'EOF'
#!/bin/bash
# rc.local

echo 0 > /sys/class/vtconsole/vtcon1/bind
echo 0 > /sys/class/graphics/fbcon/cursor_blink
con2fbmap 1 1

exit 0
EOF
    chmod +x "$RC_LOCAL"
    ok "rc.local erstellt"
elif ! grep -q "vtcon1" "$RC_LOCAL"; then
    # Vor exit 0 einfuegen
    sed -i '/^exit 0/i echo 0 > /sys/class/vtconsole/vtcon1/bind\necho 0 > /sys/class/graphics/fbcon/cursor_blink\ncon2fbmap 1 1\n' "$RC_LOCAL"
    ok "Konsolen-Unterdrückung zu rc.local hinzugefuegt"
else
    ok "Konsolen-Unterdrückung bereits in rc.local"
fi

# ══════════════════════════════════════════════════════════════
# SCHRITT 9: rfkill-unblock Service
# ══════════════════════════════════════════════════════════════
step "9/12 rfkill-unblock Service"

cat > /etc/systemd/system/rfkill-unblock.service << 'EOF'
[Unit]
Description=Unblock RF devices (WiFi + Bluetooth)
After=network.target

[Service]
Type=oneshot
ExecStart=/usr/sbin/rfkill unblock all
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable rfkill-unblock 2>/dev/null
ok "rfkill-unblock Service eingerichtet"

# ══════════════════════════════════════════════════════════════
# SCHRITT 10: Raspotify installieren
# ══════════════════════════════════════════════════════════════
step "10/12 Raspotify (Spotify Connect)"

if command -v librespot &>/dev/null || [ -f /usr/bin/librespot ]; then
    ok "Raspotify/librespot bereits installiert"
else
    info "Raspotify installieren..."
    if curl -sL https://dtcooper.github.io/raspotify/install.sh | sh; then
        ok "Raspotify installiert"
    else
        add_error "Raspotify Installation fehlgeschlagen"
        fail "Raspotify"
    fi
fi

# Konfiguration
RASPOTIFY_CONF="/etc/raspotify/conf"
if [ -f "$RASPOTIFY_CONF" ]; then
    # Name setzen
    if grep -q "^LIBRESPOT_NAME=" "$RASPOTIFY_CONF"; then
        sed -i "s/^LIBRESPOT_NAME=.*/LIBRESPOT_NAME=\"$SPOTIFY_NAME\"/" "$RASPOTIFY_CONF"
    else
        echo "LIBRESPOT_NAME=\"$SPOTIFY_NAME\"" >> "$RASPOTIFY_CONF"
    fi
    ok "Spotify Name: $SPOTIFY_NAME"

    # Bitrate 320
    if ! grep -q "^LIBRESPOT_BITRATE=320" "$RASPOTIFY_CONF"; then
        sed -i 's/^#LIBRESPOT_BITRATE=.*/LIBRESPOT_BITRATE=320/' "$RASPOTIFY_CONF"
        grep -q "^LIBRESPOT_BITRATE" "$RASPOTIFY_CONF" || echo "LIBRESPOT_BITRATE=320" >> "$RASPOTIFY_CONF"
    fi
    ok "Bitrate auf 320kbps gesetzt"

    # Credential Cache NICHT deaktivieren
    if grep -q "^LIBRESPOT_DISABLE_CREDENTIAL_CACHE=" "$RASPOTIFY_CONF"; then
        sed -i 's/^LIBRESPOT_DISABLE_CREDENTIAL_CACHE=/#LIBRESPOT_DISABLE_CREDENTIAL_CACHE=/' "$RASPOTIFY_CONF"
        ok "Credential Cache aktiviert (DISABLE auskommentiert)"
    else
        ok "Credential Cache bereits korrekt konfiguriert"
    fi

    # System Cache
    mkdir -p /var/cache/raspotify
    if ! grep -q "^LIBRESPOT_SYSTEM_CACHE=" "$RASPOTIFY_CONF"; then
        echo "LIBRESPOT_SYSTEM_CACHE=/var/cache/raspotify" >> "$RASPOTIFY_CONF"
    fi
    ok "System Cache konfiguriert: /var/cache/raspotify"
fi

# Raspotify Service: network-online.target
RASPOTIFY_SERVICE="/lib/systemd/system/raspotify.service"
if [ -f "$RASPOTIFY_SERVICE" ]; then
    if ! grep -q "network-online.target" "$RASPOTIFY_SERVICE"; then
        sed -i 's/Wants=network.target/Wants=network-online.target/' "$RASPOTIFY_SERVICE"
        sed -i 's/After=network.target/After=network-online.target/' "$RASPOTIFY_SERVICE"
        ok "Raspotify wartet auf network-online.target"
    else
        ok "Raspotify Service Timing bereits korrekt"
    fi
fi

# networkd-wait-online aktivieren
systemctl enable systemd-networkd-wait-online.service 2>/dev/null || true
systemctl daemon-reload

# OAuth pruefen
if [ -f "/var/cache/raspotify/credentials.json" ]; then
    ok "Spotify OAuth-Token vorhanden"
else
    add_manual "Spotify OAuth einrichten:"
    add_manual "  sudo systemctl stop raspotify"
    add_manual "  /usr/bin/librespot --name \"$SPOTIFY_NAME\" --enable-oauth --system-cache /var/cache/raspotify"
    add_manual "  URL im Browser oeffnen (SSH-Tunnel: ssh -L 5588:127.0.0.1:5588 pi@<IP>)"
    add_manual "  Nach Login: sudo systemctl start raspotify"
fi

# ══════════════════════════════════════════════════════════════
# SCHRITT 11: iPod Script installieren
# ══════════════════════════════════════════════════════════════
step "11/12 iPod Script"

# main.py pruefen
if [ -f "$REAL_HOME/main.py" ]; then
    ok "main.py vorhanden: $REAL_HOME/main.py"
else
    warn "main.py fehlt!"
    add_manual "main.py nach $REAL_HOME/main.py kopieren"
    add_manual "  scp main.py $REAL_USER@$(hostname -I | cut -d' ' -f1):~/"
fi

# ipod_ctrl.py erstellen
cat > "$REAL_HOME/ipod_ctrl.py" << 'CTRLEOF'
#!/usr/bin/env python3
"""Tastatur-Steuerung fuer iPod Menue ueber File-Trigger"""
import sys
import tty
import termios

TRIGGER = "/tmp/ipod_cmd"

def send(cmd):
    with open(TRIGGER, "w") as f:
        f.write(cmd)
    print(f">> {cmd}")

def main():
    print("iPod Steuerung (q = Beenden):")
    print("  w/Pfeil hoch   = up")
    print("  s/Pfeil runter = down")
    print("  d/Enter/Rechts = enter")
    print("  a/ESC/Links    = back")
    print("  1=Musik 2=WiFi 3=BT 4=System")

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        while True:
            ch = sys.stdin.read(1)
            if ch == 'q':
                break
            elif ch == 'w':   send("up")
            elif ch == 's':   send("down")
            elif ch == 'd':   send("enter")
            elif ch == 'a':   send("back")
            elif ch == '1':   send("cat:0")
            elif ch == '2':   send("cat:1")
            elif ch == '3':   send("cat:2")
            elif ch == '4':   send("cat:3")
            elif ch == '\r':  send("enter")
            elif ch == '\x1b':
                ch2 = sys.stdin.read(1)
                if ch2 == '[':
                    ch3 = sys.stdin.read(1)
                    if ch3 == 'A':   send("up")
                    elif ch3 == 'B': send("down")
                    elif ch3 == 'C': send("enter")
                    elif ch3 == 'D': send("back")
                else:
                    send("back")
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)

if __name__ == "__main__":
    main()
CTRLEOF

chown "$REAL_USER:$REAL_USER" "$REAL_HOME/ipod_ctrl.py"
chmod +x "$REAL_HOME/ipod_ctrl.py"
ok "ipod_ctrl.py erstellt: $REAL_HOME/ipod_ctrl.py"

# pidrive.service
cat > /etc/systemd/system/pidrive.service << EOF
[Unit]
Description=PiDrive Menu
After=multi-user.target

[Service]
Type=simple
User=$REAL_USER
Environment=SDL_FBDEV=/dev/fb0
Environment=SDL_VIDEODRIVER=fbcon
Environment=SDL_NOMOUSE=1
ExecStartPre=/bin/sleep 3
ExecStart=/usr/bin/python3 $REAL_HOME/main.py
Restart=always
RestartSec=3
StandardInput=tty
TTYPath=/dev/tty3
TTYReset=yes
TTYVHangup=yes

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload

if [ -f "$REAL_HOME/main.py" ]; then
    systemctl enable ipod 2>/dev/null
    ok "pidrive.service aktiviert"
else
    warn "pidrive.service konfiguriert aber nicht aktiviert (main.py fehlt)"
fi

# Berechtigungen
usermod -a -G video,input,render "$REAL_USER" 2>/dev/null || true
chmod 666 /dev/fb0 2>/dev/null || true
chmod 666 /dev/tty1 2>/dev/null || true
ok "Berechtigungen gesetzt (video, input, render Gruppe)"

# Trigger-Verzeichnis
chmod 777 /tmp
ok "/tmp Berechtigungen gesetzt"

# ══════════════════════════════════════════════════════════════
# SCHRITT 12: Abschlusspruefung
# ══════════════════════════════════════════════════════════════
step "12/12 Abschlusspruefung"

echo ""
echo -e "${BOLD}System-Check:${NC}"

# SPI
if lsmod | grep -q spi_bcm2835; then
    ok "SPI Treiber geladen"
else
    warn "SPI Treiber nicht geladen (nach Reboot pruefen)"
fi

# Display Treiber
if grep -q "^dtoverlay=tft35a" /boot/config.txt; then
    ok "TFT35 Display-Treiber in config.txt"
else
    fail "TFT35 Display-Treiber fehlt in config.txt"
    add_error "LCD35-show muss noch ausgefuehrt werden"
fi

# fbcp
if ps aux | grep -q "[f]bcp"; then
    ok "fbcp (Framebuffer Copy) laeuft"
else
    warn "fbcp nicht aktiv (wird nach LCD35-show automatisch gestartet)"
fi

# Avahi
if systemctl is-active --quiet avahi-daemon; then
    ok "Avahi mDNS Daemon laeuft"
else
    fail "Avahi nicht aktiv"
    add_error "sudo systemctl start avahi-daemon"
fi

# Bluetooth
if systemctl is-active --quiet bluetooth; then
    ok "Bluetooth Service laeuft"
else
    warn "Bluetooth nicht aktiv"
fi

# WLAN
if ip a show wlan0 2>/dev/null | grep -q "inet "; then
    IP=$(ip a show wlan0 | grep "inet " | awk '{print $2}')
    ok "WLAN verbunden: $IP"
else
    warn "WLAN nicht verbunden"
fi

# Raspotify
if systemctl is-active --quiet raspotify; then
    ok "Raspotify laeuft"
else
    warn "Raspotify nicht aktiv"
fi

# OAuth Token
if [ -f "/var/cache/raspotify/credentials.json" ]; then
    ok "Spotify Token vorhanden"
else
    warn "Spotify OAuth noch nicht eingerichtet"
fi

# main.py
if [ -f "$REAL_HOME/main.py" ]; then
    ok "main.py vorhanden"
else
    fail "main.py fehlt!"
fi

# ipod Service
if systemctl is-enabled --quiet ipod 2>/dev/null; then
    ok "pidrive.service aktiviert"
else
    warn "pidrive.service noch nicht aktiviert"
fi

# pygame
if python3 -c "import pygame" 2>/dev/null; then
    PGVER=$(python3 -c "import pygame; print(pygame.version.ver)")
    ok "pygame $PGVER verfuegbar"
else
    fail "pygame nicht installiert"
    add_error "sudo apt install python3-pygame"
fi

# ── Zusammenfassung ───────────────────────────────────────────
echo ""
echo -e "${BOLD}${BLUE}════════════════════════════════════════${NC}"
echo -e "${BOLD}           SETUP ZUSAMMENFASSUNG          ${NC}"
echo -e "${BOLD}${BLUE}════════════════════════════════════════${NC}"

if [ ${#ERRORS[@]} -eq 0 ]; then
    echo -e "${GREEN}${BOLD}✓ Keine Fehler!${NC}"
else
    echo -e "${RED}${BOLD}✗ Fehler (${#ERRORS[@]}):${NC}"
    for err in "${ERRORS[@]}"; do
        echo -e "${RED}  • $err${NC}"
    done
fi

if [ ${#WARNINGS[@]} -gt 0 ]; then
    echo ""
    echo -e "${YELLOW}${BOLD}⚠ Warnungen (${#WARNINGS[@]}):${NC}"
    for wrn in "${WARNINGS[@]}"; do
        echo -e "${YELLOW}  • $wrn${NC}"
    done
fi

if [ ${#MANUAL_STEPS[@]} -gt 0 ]; then
    echo ""
    echo -e "${CYAN}${BOLD}→ Manuelle Schritte erforderlich:${NC}"
    for step in "${MANUAL_STEPS[@]}"; do
        echo -e "${CYAN}  • $step${NC}"
    done
fi

echo ""
echo -e "${BOLD}Naechste Schritte:${NC}"
echo -e "  1. ${YELLOW}sudo reboot${NC} (fuer config.txt Aenderungen)"
echo -e "  2. Nach Reboot: ${YELLOW}cd ~/LCD-show && sudo ./LCD35-show${NC} (wenn noch nicht gemacht)"
echo -e "  3. Spotify OAuth: ${YELLOW}Siehe manuelle Schritte oben${NC}"
echo -e "  4. iPod Script starten: ${YELLOW}sudo systemctl start ipod${NC}"
echo -e "  5. Navigation testen: ${YELLOW}python3 ~/ipod_ctrl.py${NC}"
echo ""
echo -e "${BOLD}SSH-Zugang nach Reboot:${NC}"
IP_ADDR=$(hostname -I | cut -d' ' -f1)
echo -e "  ${CYAN}ssh $REAL_USER@$IP_ADDR${NC}"
echo ""
echo -e "${GREEN}${BOLD}Setup abgeschlossen!${NC}"
