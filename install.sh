#!/bin/bash
# ============================================================
# PiDrive Install Script
# Raspberry Pi Car Infotainment
#
# Aufruf:
#   curl -sL https://raw.githubusercontent.com/MPunktBPunkt/pidrive/main/install.sh | sudo bash
#   oder lokal:
#   sudo bash install.sh
# ============================================================

set -e

REPO_URL="https://github.com/MPunktBPunkt/pidrive"
INSTALL_DIR="/home/pi/pidrive"
SERVICE_DIR="/etc/systemd/system"
LOG_DIR="/var/log/pidrive"
REAL_USER=${SUDO_USER:-pi}
REAL_HOME=$(eval echo "~$REAL_USER")

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

ok()   { echo -e "${GREEN}  ✓ ${1}${NC}"; }
info() { echo -e "${BLUE}  → ${1}${NC}"; }
warn() { echo -e "${YELLOW}  ⚠ ${1}${NC}"; }
fail() { echo -e "${RED}  ✗ ${1}${NC}"; }

echo -e "${BOLD}${BLUE}"
cat << 'EOF'
╔═══════════════════════════════════════════╗
║           PiDrive Installer               ║
║   github.com/MPunktBPunkt/pidrive         ║
╚═══════════════════════════════════════════╝
EOF
echo -e "${NC}"

# Root check
if [ "$EUID" -ne 0 ]; then
    echo "Bitte als root ausfuehren: sudo bash install.sh"
    exit 1
fi

# ── Abhaengigkeiten ───────────────────────────────────────────
info "Pakete installieren..."
apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
    python3-pygame python3-pip git mpv \
    avahi-daemon avahi-utils rfkill \
    bluez pulseaudio pulseaudio-module-bluetooth \
    wpasupplicant dhcpcd5 \
    2>/dev/null || true
ok "System-Pakete installiert"

# mutagen fuer MP3-Tags und Album-Art
pip3 install mutagen --break-system-packages -q 2>/dev/null || \
pip3 install mutagen -q 2>/dev/null || true
ok "Python-Pakete installiert (mutagen)"

# ── Repository klonen / updaten ───────────────────────────────
if [ -d "$INSTALL_DIR/.git" ]; then
    info "Update von GitHub..."
    cd "$INSTALL_DIR"
    sudo -u "$REAL_USER" git pull
    ok "Aktualisiert auf neueste Version"
else
    info "Klone von GitHub: $REPO_URL"
    sudo -u "$REAL_USER" git clone "$REPO_URL" "$INSTALL_DIR"
    ok "Geklont nach $INSTALL_DIR"
fi

# ── Musik-Verzeichnis ─────────────────────────────────────────
MUSIK_DIR="$REAL_HOME/Musik"
if [ ! -d "$MUSIK_DIR" ]; then
    sudo -u "$REAL_USER" mkdir -p "$MUSIK_DIR"
    ok "Musik-Verzeichnis: $MUSIK_DIR"
else
    ok "Musik-Verzeichnis vorhanden: $MUSIK_DIR"
fi

# ── Log-Verzeichnis ───────────────────────────────────────────
mkdir -p "$LOG_DIR"
chown "$REAL_USER:$REAL_USER" "$LOG_DIR"
ok "Log-Verzeichnis: $LOG_DIR"

# ── /boot/config.txt ─────────────────────────────────────────
info "/boot/config.txt konfigurieren..."

if [ ! -f /boot/config.txt.bak ]; then
    cp /boot/config.txt /boot/config.txt.bak
    ok "Backup: /boot/config.txt.bak"
fi

# camera/display auto_detect deaktivieren (blockieren SPI Display!)
sed -i 's/^camera_auto_detect=1/camera_auto_detect=0/' /boot/config.txt 2>/dev/null || true
sed -i 's/^display_auto_detect=1/display_auto_detect=0/' /boot/config.txt 2>/dev/null || true
grep -q "^camera_auto_detect" /boot/config.txt || echo "camera_auto_detect=0" >> /boot/config.txt
grep -q "^display_auto_detect" /boot/config.txt || echo "display_auto_detect=0" >> /boot/config.txt

# vc4-kms-v3d deaktivieren (stoert SPI Display)
sed -i 's/^dtoverlay=vc4-kms-v3d/#dtoverlay=vc4-kms-v3d/' /boot/config.txt 2>/dev/null || true
sed -i 's/^dtoverlay=vc4-fkms-v3d/#dtoverlay=vc4-fkms-v3d/' /boot/config.txt 2>/dev/null || true

# max_framebuffers
grep -q "^max_framebuffers=2" /boot/config.txt || echo "max_framebuffers=2" >> /boot/config.txt

ok "/boot/config.txt konfiguriert"

# ── SSH aktivieren ────────────────────────────────────────────
systemctl enable ssh 2>/dev/null && systemctl start ssh 2>/dev/null || true
ok "SSH aktiviert"

# ── Systemdienste ─────────────────────────────────────────────
info "pidrive.service einrichten..."
cat > "$SERVICE_DIR/pidrive.service" << EOF
[Unit]
Description=PiDrive - Car Infotainment
After=multi-user.target

[Service]
Type=simple
User=$REAL_USER
Environment=SDL_FBDEV=/dev/fb0
Environment=SDL_VIDEODRIVER=fbcon
Environment=SDL_NOMOUSE=1
WorkingDirectory=$INSTALL_DIR/pidrive
ExecStartPre=/bin/sleep 5
ExecStart=/usr/bin/python3 $INSTALL_DIR/pidrive/main.py
Restart=always
RestartSec=5
StandardInput=tty
TTYPath=/dev/tty3
TTYReset=yes
TTYVHangup=yes

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable pidrive
ok "pidrive.service aktiviert"

# rfkill-unblock Service
cat > "$SERVICE_DIR/rfkill-unblock.service" << 'EOF'
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
ok "rfkill-unblock.service aktiviert"

# ── Konsolen-Unterdrückung (rc.local) ─────────────────────────
RC="/etc/rc.local"
if [ ! -f "$RC" ]; then
    printf '#!/bin/bash\nexit 0\n' > "$RC"
    chmod +x "$RC"
fi
if ! grep -q "vtcon1" "$RC"; then
    sed -i '/^exit 0/i echo 0 > /sys/class/vtconsole/vtcon1/bind\necho 0 > /sys/class/graphics/fbcon/cursor_blink\ncon2fbmap 1 1\n' "$RC"
    ok "Konsolenunterdrückung in rc.local"
fi

# ── Berechtigungen ────────────────────────────────────────────
usermod -a -G video,input,render "$REAL_USER" 2>/dev/null || true
ok "Benutzer $REAL_USER: video, input, render Gruppen"

# ── pidrive_ctrl Link ─────────────────────────────────────────
ln -sf "$INSTALL_DIR/pidrive_ctrl.py" "$REAL_HOME/pidrive_ctrl.py" 2>/dev/null || true
ok "pidrive_ctrl.py verknuepft"

# ── Spotify onevent Script ────────────────────────────────────
cat > /usr/local/bin/spotify_event.sh << 'EOF'
#!/bin/bash
# Wird von librespot bei Wiedergabe-Events aufgerufen
# Schreibt Track-Info fuer PiDrive nach /tmp/spotify_status
if [ "$PLAYER_EVENT" = "track_changed" ] || [ "$PLAYER_EVENT" = "playing" ]; then
    echo "${PLAYER_EVENT}|${NAME}|${ARTISTS}|${ALBUM}" > /tmp/spotify_status
fi
EOF
chmod +x /usr/local/bin/spotify_event.sh
ok "Spotify onevent Script: /usr/local/bin/spotify_event.sh"

# Raspotify konfigurieren wenn installiert
if [ -f /etc/raspotify/conf ]; then
    # Credential Cache aktivieren (PFLICHT nach OAuth!)
    sed -i 's/^LIBRESPOT_DISABLE_CREDENTIAL_CACHE=/#LIBRESPOT_DISABLE_CREDENTIAL_CACHE=/' /etc/raspotify/conf
    # onevent setzen
    if ! grep -q "^LIBRESPOT_ONEVENT" /etc/raspotify/conf; then
        echo "LIBRESPOT_ONEVENT=/usr/local/bin/spotify_event.sh" >> /etc/raspotify/conf
    fi
    # network-online.target
    if [ -f /lib/systemd/system/raspotify.service ]; then
        sed -i 's/Wants=network.target/Wants=network-online.target/' /lib/systemd/system/raspotify.service 2>/dev/null || true
        sed -i 's/After=network.target/After=network-online.target/' /lib/systemd/system/raspotify.service 2>/dev/null || true
        systemctl enable systemd-networkd-wait-online.service 2>/dev/null || true
        systemctl daemon-reload
    fi
    ok "Raspotify konfiguriert"
fi

# ── Abschlussbericht ──────────────────────────────────────────
echo ""
echo -e "${BOLD}${GREEN}Installation abgeschlossen!${NC}"
echo ""
echo -e "${BOLD}Naechste Schritte:${NC}"
echo -e "  1. ${YELLOW}Display-Treiber installieren:${NC}"
echo -e "     git clone https://github.com/goodtft/LCD-show ~/LCD-show"
echo -e "     cd ~/LCD-show && sudo ./LCD35-show"
echo -e "     (Pi startet danach automatisch neu)"
echo ""
echo -e "  2. ${YELLOW}Spotify OAuth einrichten:${NC}"
echo -e "     sudo systemctl stop raspotify"
echo -e "     /usr/bin/librespot --name PiDrive --enable-oauth \\"
echo -e "       --system-cache /var/cache/raspotify"
echo -e "     (SSH-Tunnel noetig: ssh -L 5588:127.0.0.1:5588 pi@<IP> -N)"
echo ""
echo -e "  3. ${YELLOW}Testen:${NC}"
echo -e "     sudo systemctl start pidrive"
echo -e "     python3 ~/pidrive_ctrl.py"
echo ""
echo -e "${BOLD}Logs:${NC}"
echo -e "  Live:    ${CYAN}tail -f $LOG_DIR/pidrive.log${NC}"
echo -e "  Service: ${CYAN}journalctl -u pidrive -f${NC}"
echo -e "  Debug:   ${CYAN}journalctl -u pidrive -n 50 --no-pager${NC}"
echo ""
echo -e "${BOLD}Update:${NC}"
echo -e "  ${CYAN}cd $INSTALL_DIR && git pull && sudo systemctl restart pidrive${NC}"
