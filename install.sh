#!/bin/bash
# ============================================================
# PiDrive Install Script v0.3.1
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

echo -e "${BOLD}${BLUE}"
cat << 'EOF'
╔═══════════════════════════════════════════╗
║        PiDrive Installer v0.3.1           ║
║   github.com/MPunktBPunkt/pidrive         ║
╚═══════════════════════════════════════════╝
EOF
echo -e "${NC}"

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
    wpasupplicant dhcpcd5 rtl-sdr sox \
    2>/dev/null || true

# welle-cli fuer DAB+ (optional, kein Fehler wenn nicht verfuegbar)
apt-get install -y -qq welle.io 2>/dev/null || \
    warn "welle.io nicht verfuegbar - DAB+ deaktiviert (kann spaeter installiert werden)"
ok "System-Pakete installiert"

pip3 install mutagen --break-system-packages -q 2>/dev/null || \
pip3 install mutagen -q 2>/dev/null || true
ok "Python-Pakete installiert (mutagen)"

# ── Repository klonen / updaten ───────────────────────────────
if [ -d "$INSTALL_DIR/.git" ]; then
    info "Update von GitHub..."
    cd "$INSTALL_DIR"
    sudo -u "$REAL_USER" git pull
    ok "Aktualisiert"
else
    info "Klone von GitHub: $REPO_URL"
    sudo -u "$REAL_USER" git clone "$REPO_URL" "$INSTALL_DIR"
    ok "Geklont nach $INSTALL_DIR"
fi

# ── Verzeichnisse ─────────────────────────────────────────────
MUSIK_DIR="$REAL_HOME/Musik"
[ ! -d "$MUSIK_DIR" ] && sudo -u "$REAL_USER" mkdir -p "$MUSIK_DIR"
ok "Musik-Verzeichnis: $MUSIK_DIR"

mkdir -p "$LOG_DIR"
chown "$REAL_USER:$REAL_USER" "$LOG_DIR"
ok "Log-Verzeichnis: $LOG_DIR"

# ── /boot/config.txt ──────────────────────────────────────────
info "/boot/config.txt konfigurieren..."
[ ! -f /boot/config.txt.bak ] && cp /boot/config.txt /boot/config.txt.bak

sed -i 's/^camera_auto_detect=1/camera_auto_detect=0/' /boot/config.txt 2>/dev/null || true
sed -i 's/^display_auto_detect=1/display_auto_detect=0/' /boot/config.txt 2>/dev/null || true
grep -q "^camera_auto_detect" /boot/config.txt || echo "camera_auto_detect=0" >> /boot/config.txt
grep -q "^display_auto_detect" /boot/config.txt || echo "display_auto_detect=0" >> /boot/config.txt
sed -i 's/^dtoverlay=vc4-kms-v3d/#dtoverlay=vc4-kms-v3d/' /boot/config.txt 2>/dev/null || true
sed -i 's/^dtoverlay=vc4-fkms-v3d/#dtoverlay=vc4-fkms-v3d/' /boot/config.txt 2>/dev/null || true
grep -q "^max_framebuffers=2" /boot/config.txt || echo "max_framebuffers=2" >> /boot/config.txt
ok "/boot/config.txt konfiguriert"

# ── SSH ───────────────────────────────────────────────────────
systemctl enable ssh 2>/dev/null && systemctl start ssh 2>/dev/null || true
ok "SSH aktiviert"

# ── Systemdienst (aus systemd/ Ordner im Repo) ────────────────
info "pidrive.service einrichten..."
if [ -f "$INSTALL_DIR/systemd/pidrive.service" ]; then
    cp "$INSTALL_DIR/systemd/pidrive.service" "$SERVICE_DIR/pidrive.service"
    # Pfade auf aktuellen User anpassen
    sed -i "s|/home/pi/|$REAL_HOME/|g" "$SERVICE_DIR/pidrive.service"
    ok "pidrive.service aus Repo kopiert"
else
    # Fallback: Service inline erstellen
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
ExecStartPre=/bin/chvt 3
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
    ok "pidrive.service erstellt (Fallback)"
fi
systemctl daemon-reload
systemctl enable pidrive
ok "pidrive.service aktiviert"

# ── rfkill-unblock Service ────────────────────────────────────
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
systemctl enable rfkill-unblock 2>/dev/null
ok "rfkill-unblock.service aktiviert"

# ── Konsolen-Unterdrückung ────────────────────────────────────
RC="/etc/rc.local"
[ ! -f "$RC" ] && printf '#!/bin/bash\nexit 0\n' > "$RC" && chmod +x "$RC"
if ! grep -q "vtcon1" "$RC"; then
    sed -i '/^exit 0/i echo 0 > /sys/class/vtconsole/vtcon1/bind\necho 0 > /sys/class/graphics/fbcon/cursor_blink\ncon2fbmap 1 1\nchvt 3\n' "$RC"
    ok "Konsolenunterdrückung + chvt 3 in rc.local"
elif ! grep -q "chvt 3" "$RC"; then
    sed -i '/^exit 0/i chvt 3' "$RC"
    ok "chvt 3 zu rc.local hinzugefuegt"
else
    ok "rc.local bereits korrekt"
fi

# ── Berechtigungen ────────────────────────────────────────────
usermod -a -G video,input,render "$REAL_USER" 2>/dev/null || true
ok "Gruppen: video, input, render"

# ── pidrive_ctrl Link ─────────────────────────────────────────
ln -sf "$INSTALL_DIR/pidrive_ctrl.py" "$REAL_HOME/pidrive_ctrl.py" 2>/dev/null || true
ok "pidrive_ctrl.py verknuepft"

# ── Spotify onevent ───────────────────────────────────────────
cat > /usr/local/bin/spotify_event.sh << 'EOF'
#!/bin/bash
if [ "$PLAYER_EVENT" = "track_changed" ] || [ "$PLAYER_EVENT" = "playing" ]; then
    echo "${PLAYER_EVENT}|${NAME}|${ARTISTS}|${ALBUM}" > /tmp/spotify_status
fi
EOF
chmod +x /usr/local/bin/spotify_event.sh
ok "Spotify onevent Script"

if [ -f /etc/raspotify/conf ]; then
    sed -i 's/^LIBRESPOT_DISABLE_CREDENTIAL_CACHE=/#LIBRESPOT_DISABLE_CREDENTIAL_CACHE=/' /etc/raspotify/conf
    grep -q "^LIBRESPOT_ONEVENT" /etc/raspotify/conf || \
        echo "LIBRESPOT_ONEVENT=/usr/local/bin/spotify_event.sh" >> /etc/raspotify/conf
    if [ -f /lib/systemd/system/raspotify.service ]; then
        sed -i 's/Wants=network.target/Wants=network-online.target/' /lib/systemd/system/raspotify.service 2>/dev/null || true
        sed -i 's/After=network.target/After=network-online.target/' /lib/systemd/system/raspotify.service 2>/dev/null || true
        systemctl enable systemd-networkd-wait-online.service 2>/dev/null || true
        systemctl daemon-reload
    fi
    ok "Raspotify konfiguriert"
fi

# ── Abschluss ─────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${GREEN}Installation abgeschlossen!${NC}"
echo ""
echo -e "${BOLD}Naechste Schritte:${NC}"
echo -e "  1. ${YELLOW}Display-Treiber:${NC}"
echo -e "     git clone https://github.com/goodtft/LCD-show ~/LCD-show"
echo -e "     cd ~/LCD-show && sudo ./LCD35-show"
echo ""
echo -e "  2. ${YELLOW}Spotify OAuth:${NC}"
echo -e "     sudo systemctl stop raspotify"
echo -e "     /usr/bin/librespot --name PiDrive --enable-oauth \\"
echo -e "       --system-cache /var/cache/raspotify"
echo ""
echo -e "  3. ${YELLOW}Starten & testen:${NC}"
echo -e "     sudo systemctl start pidrive"
echo -e "     python3 ~/pidrive_ctrl.py"
echo ""
echo -e "${BOLD}Logs:${NC}"
echo -e "  ${CYAN}tail -f $LOG_DIR/pidrive.log${NC}"
echo -e "  ${CYAN}journalctl -u pidrive -f${NC}"
echo ""
echo -e "${BOLD}Update:${NC}"
echo -e "  ${CYAN}cd $INSTALL_DIR && git pull && sudo systemctl restart pidrive${NC}"
