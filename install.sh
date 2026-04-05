#!/bin/bash
# ============================================================
# PiDrive Install Script
# Installiert PiDrive direkt von GitHub
#
# Aufruf:
#   curl -sL https://raw.githubusercontent.com/DEIN-USER/pidrive/main/install.sh | bash
#   oder:
#   bash install.sh
# ============================================================

set -e

REPO_URL="https://github.com/DEIN-USER/pidrive"
INSTALL_DIR="/home/pi/pidrive"
SERVICE_DIR="/etc/systemd/system"
REAL_USER=${SUDO_USER:-pi}
REAL_HOME=$(eval echo "~$REAL_USER")

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; BOLD='\033[1m'; NC='\033[0m'

ok()   { echo -e "${GREEN}  ✓ ${1}${NC}"; }
info() { echo -e "${BLUE}  → ${1}${NC}"; }
warn() { echo -e "${YELLOW}  ⚠ ${1}${NC}"; }

echo -e "${BOLD}${BLUE}"
cat << 'EOF'
╔═══════════════════════════════════════╗
║        PiDrive Installer             ║
║  github.com/DEIN-USER/pidrive        ║
╚═══════════════════════════════════════╝
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
apt-get install -y -qq \
    python3-pygame python3-pip git mpv \
    avahi-daemon avahi-utils rfkill \
    bluez pulseaudio pulseaudio-module-bluetooth \
    2>/dev/null || true
ok "Pakete installiert"

# mutagen fuer MP3-Tags
pip3 install mutagen --break-system-packages -q 2>/dev/null || \
pip3 install mutagen -q 2>/dev/null || true
ok "mutagen installiert"

# ── Repository klonen / updaten ───────────────────────────────
if [ -d "$INSTALL_DIR/.git" ]; then
    info "Update von GitHub..."
    cd "$INSTALL_DIR"
    sudo -u "$REAL_USER" git pull
    ok "Aktualisiert"
else
    info "Klone von GitHub..."
    sudo -u "$REAL_USER" git clone "$REPO_URL" "$INSTALL_DIR"
    ok "Geklont nach $INSTALL_DIR"
fi

# ── Musik-Verzeichnis anlegen ─────────────────────────────────
MUSIK_DIR="$REAL_HOME/Musik"
if [ ! -d "$MUSIK_DIR" ]; then
    sudo -u "$REAL_USER" mkdir -p "$MUSIK_DIR"
    ok "Musik-Verzeichnis: $MUSIK_DIR"
fi

# ── /boot/config.txt anpassen ─────────────────────────────────
info "/boot/config.txt konfigurieren..."

# camera/display auto_detect deaktivieren
sed -i 's/^camera_auto_detect=1/camera_auto_detect=0/' /boot/config.txt 2>/dev/null || true
sed -i 's/^display_auto_detect=1/display_auto_detect=0/' /boot/config.txt 2>/dev/null || true

# vc4-kms-v3d deaktivieren
sed -i 's/^dtoverlay=vc4-kms-v3d/#dtoverlay=vc4-kms-v3d/' /boot/config.txt 2>/dev/null || true
sed -i 's/^dtoverlay=vc4-fkms-v3d/#dtoverlay=vc4-fkms-v3d/' /boot/config.txt 2>/dev/null || true

ok "/boot/config.txt angepasst"

# ── Systemdienste einrichten ──────────────────────────────────
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
systemctl enable ipod
ok "pidrive.service aktiviert"

# rfkill-unblock Service
cat > "$SERVICE_DIR/rfkill-unblock.service" << 'EOF'
[Unit]
Description=Unblock RF devices
After=network.target

[Service]
Type=oneshot
ExecStart=/usr/sbin/rfkill unblock all
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable rfkill-unblock
ok "rfkill-unblock.service aktiviert"

# ── Konsolenunterdrückung in rc.local ─────────────────────────
RC="/etc/rc.local"
if [ ! -f "$RC" ]; then
    echo "#!/bin/bash" > "$RC"
    echo "exit 0" >> "$RC"
    chmod +x "$RC"
fi
if ! grep -q "vtcon1" "$RC"; then
    sed -i '/^exit 0/i echo 0 > /sys/class/vtconsole/vtcon1/bind\necho 0 > /sys/class/graphics/fbcon/cursor_blink\ncon2fbmap 1 1\n' "$RC"
    ok "Konsolenunterdrückung in rc.local"
fi

# Berechtigungen
usermod -a -G video,input,render "$REAL_USER" 2>/dev/null || true

# ── pidrive_ctrl.py Link ─────────────────────────────────────────
ln -sf "$INSTALL_DIR/pidrive_ctrl.py" "$REAL_HOME/pidrive_ctrl.py" 2>/dev/null || true

# ── Spotify onevent Script ────────────────────────────────────
cat > /usr/local/bin/spotify_event.sh << 'EOF'
#!/bin/bash
# Wird von librespot bei Wiedergabe-Events aufgerufen
if [ "$PLAYER_EVENT" = "track_changed" ] || [ "$PLAYER_EVENT" = "playing" ]; then
    echo "${PLAYER_EVENT}|${NAME}|${ARTISTS}|${ALBUM}" > /tmp/spotify_status
fi
EOF
chmod +x /usr/local/bin/spotify_event.sh
ok "Spotify onevent Script installiert"

# Raspotify konfigurieren wenn installiert
if [ -f /etc/raspotify/conf ]; then
    if ! grep -q "^LIBRESPOT_ONEVENT" /etc/raspotify/conf; then
        echo "LIBRESPOT_ONEVENT=/usr/local/bin/spotify_event.sh" >> /etc/raspotify/conf
        ok "Raspotify onevent konfiguriert"
    fi
    # Credential Cache aktivieren
    sed -i 's/^LIBRESPOT_DISABLE_CREDENTIAL_CACHE=/#LIBRESPOT_DISABLE_CREDENTIAL_CACHE=/' /etc/raspotify/conf
fi

echo ""
echo -e "${GREEN}${BOLD}Installation abgeschlossen!${NC}"
echo ""
echo -e "Naechste Schritte:"
echo -e "  1. ${YELLOW}Display-Treiber:${NC} cd ~/LCD-show && sudo ./LCD35-show"
echo -e "  2. ${YELLOW}Spotify OAuth:${NC}   sudo /usr/bin/librespot --name PiDrive --enable-oauth"
echo -e "  3. ${YELLOW}Reboot:${NC}          sudo reboot"
echo ""
echo -e "Update spaeter: ${CYAN}cd $INSTALL_DIR && git pull${NC}"
echo -e "Steuerung:      ${CYAN}python3 ~/pidrive_ctrl.py${NC}"
