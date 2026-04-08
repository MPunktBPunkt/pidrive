#!/bin/bash
# ============================================================
# PiDrive Install Script v0.3.7
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
err()  { echo -e "${RED}  ✗ ${1}${NC}"; }

echo -e "${BOLD}${BLUE}"
cat << 'EOF'
╔═══════════════════════════════════════════╗
║        PiDrive Installer v0.5.7           ║
║   github.com/MPunktBPunkt/pidrive         ║
╚═══════════════════════════════════════════╝
EOF
echo -e "${NC}"

if [ "$EUID" -ne 0 ]; then
    err "Bitte als root ausfuehren: sudo bash install.sh"
    exit 1
fi

# ══════════════════════════════════════════════════════════════
# SCHRITT 1: Service stoppen (falls aktiv)
# ══════════════════════════════════════════════════════════════
info "1/10 Laufenden Service stoppen..."
if systemctl is-active --quiet pidrive 2>/dev/null; then
    systemctl stop pidrive
    ok "pidrive.service gestoppt"
else
    ok "pidrive.service war nicht aktiv"
fi

# ══════════════════════════════════════════════════════════════
# SCHRITT 2: Pakete installieren
# ══════════════════════════════════════════════════════════════
info "2/10 Pakete installieren..."
apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
    python3-pygame python3-pip git mpv \
    avahi-daemon avahi-utils rfkill \
    bluez pulseaudio pulseaudio-module-bluetooth \
    wpasupplicant dhcpcd5 rtl-sdr sox \
    2>/dev/null || true

apt-get install -y -qq welle.io 2>/dev/null || \
    warn "welle.io nicht verfuegbar — DAB+ spaeter installierbar"
ok "System-Pakete installiert"

pip3 install mutagen --break-system-packages -q 2>/dev/null || \
pip3 install mutagen -q 2>/dev/null || true
ok "Python-Pakete installiert (mutagen)"

# ══════════════════════════════════════════════════════════════
# SCHRITT 3: Repository klonen / aktualisieren
# ══════════════════════════════════════════════════════════════
info "3/10 Repository von GitHub..."
if [ -d "$INSTALL_DIR/.git" ]; then
    info "Update von GitHub..."
    cd "$INSTALL_DIR"
    sudo -u "$REAL_USER" git pull
    ok "Repository aktualisiert"
else
    info "Klone $REPO_URL nach $INSTALL_DIR..."
    sudo -u "$REAL_USER" git clone "$REPO_URL" "$INSTALL_DIR"
    ok "Repository geklont"
fi

# VERSION anzeigen
VER=$(cat "$INSTALL_DIR/pidrive/VERSION" 2>/dev/null || echo "?")
ok "PiDrive Version: $VER"

# ══════════════════════════════════════════════════════════════
# SCHRITT 4: Verzeichnisse
# ══════════════════════════════════════════════════════════════
info "4/10 Verzeichnisse anlegen..."
MUSIK_DIR="$REAL_HOME/Musik"
[ ! -d "$MUSIK_DIR" ] && sudo -u "$REAL_USER" mkdir -p "$MUSIK_DIR"
ok "Musik-Verzeichnis: $MUSIK_DIR"

mkdir -p "$LOG_DIR"
chown "$REAL_USER:$REAL_USER" "$LOG_DIR"
ok "Log-Verzeichnis: $LOG_DIR"

# ══════════════════════════════════════════════════════════════
# SCHRITT 5: /boot/config.txt
# ══════════════════════════════════════════════════════════════
info "5/10 /boot/config.txt konfigurieren..."
[ ! -f /boot/config.txt.bak ] && cp /boot/config.txt /boot/config.txt.bak

sed -i 's/^camera_auto_detect=1/camera_auto_detect=0/'   /boot/config.txt 2>/dev/null || true
sed -i 's/^display_auto_detect=1/display_auto_detect=0/' /boot/config.txt 2>/dev/null || true
grep -q "^camera_auto_detect"  /boot/config.txt || echo "camera_auto_detect=0"  >> /boot/config.txt
grep -q "^display_auto_detect" /boot/config.txt || echo "display_auto_detect=0" >> /boot/config.txt
sed -i 's/^dtoverlay=vc4-kms-v3d/#dtoverlay=vc4-kms-v3d/'   /boot/config.txt 2>/dev/null || true
sed -i 's/^dtoverlay=vc4-fkms-v3d/#dtoverlay=vc4-fkms-v3d/' /boot/config.txt 2>/dev/null || true
grep -q "^max_framebuffers=2" /boot/config.txt || echo "max_framebuffers=2" >> /boot/config.txt
ok "/boot/config.txt konfiguriert"

# ══════════════════════════════════════════════════════════════
# SCHRITT 6: rc.local (Boot-Vorbereitung)
# ══════════════════════════════════════════════════════════════
info "6/10 rc.local konfigurieren..."
RC="/etc/rc.local"

if [ ! -f "$RC" ]; then
    cat > "$RC" << 'EOF'
#!/bin/bash
# rc.local - PiDrive Boot-Vorbereitung

sleep 7                               # Warten bis SPI-Display bereit
fbcp &                                # Framebuffer-Copy starten
echo 0 > /sys/class/vtconsole/vtcon1/bind
echo 0 > /sys/class/graphics/fbcon/cursor_blink
con2fbmap 1 1
chvt 3                                # VT3 in den Vordergrund
chmod 660 /dev/tty3                   # Lesezugriff fuer launcher.py

exit 0
EOF
    chmod +x "$RC"
    ok "rc.local erstellt"
else
    # vtcon1-Block
    if ! grep -q "vtcon0" "$RC"; then
        sed -i '/^exit 0/i sleep 7\nfbcp \&\necho 0 > /sys/class/vtconsole/vtcon0/bind\necho 0 > /sys/class/vtconsole/vtcon1/bind\necho 0 > /sys/class/graphics/fbcon/cursor_blink\ncon2fbmap 1 1\n' "$RC"
        ok "rc.local Block hinzugefuegt"
    else
        # chvt 3 nachruesten falls fehlend
        if ! grep -q "chvt 3" "$RC"; then
            sed -i '/^exit 0/i chvt 3' "$RC"
            ok "chvt 3 zu rc.local hinzugefuegt"
        else
            ok "rc.local: chvt 3 vorhanden"
        fi
        # chmod 660 /dev/tty3 nachruesten falls fehlend
        if ! grep -q "chmod 660 /dev/tty3" "$RC"; then
            sed -i '/chvt 3/a chmod 660 /dev/tty3' "$RC"
            ok "chmod 660 /dev/tty3 zu rc.local hinzugefuegt"
        else
            ok "rc.local: chmod 660 /dev/tty3 vorhanden"

        fi
    fi
fi

# ══════════════════════════════════════════════════════════════
# SCHRITT 7: udev-Regel fuer /dev/tty3
# ══════════════════════════════════════════════════════════════
info "7/10 udev-Regel fuer /dev/tty3..."
UDEV_RULE='/etc/udev/rules.d/99-pidrive-tty.rules'
echo 'KERNEL=="tty3", GROUP="tty", MODE="0660"' > "$UDEV_RULE"
udevadm control --reload-rules
udevadm trigger /dev/tty3 2>/dev/null || true
ok "udev-Regel gesetzt: /dev/tty3 → 0660"

# ══════════════════════════════════════════════════════════════
# SCHRITT 7b: logind.conf — VT-Verwaltung fuer SDL freigeben
# ══════════════════════════════════════════════════════════════
info "logind.conf konfigurieren..."
LOGIND_CONF="/etc/systemd/logind.conf"
# HandleVTSwitches=no: logind blockiert VT-Wechsel nicht mehr
# NAutoVTs=0: logind startet keine Auto-VTs (kein getty auf VT1-6)
if ! grep -q "^HandleVTSwitches=no" "$LOGIND_CONF" 2>/dev/null; then
    # Entferne alte auskommentierte Eintraege und setze neue
    sed -i 's/^#*HandleVTSwitches=.*/HandleVTSwitches=no/' "$LOGIND_CONF" 2>/dev/null ||         echo "HandleVTSwitches=no" >> "$LOGIND_CONF"
    ok "logind: HandleVTSwitches=no gesetzt"
else
    ok "logind: HandleVTSwitches=no bereits aktiv"
fi
if ! grep -q "^NAutoVTs=0" "$LOGIND_CONF" 2>/dev/null; then
    sed -i 's/^#*NAutoVTs=.*/NAutoVTs=0/' "$LOGIND_CONF" 2>/dev/null ||         echo "NAutoVTs=0" >> "$LOGIND_CONF"
    ok "logind: NAutoVTs=0 gesetzt"
else
    ok "logind: NAutoVTs=0 bereits aktiv"
fi
systemctl daemon-reload
systemctl restart systemd-logind 2>/dev/null || true

# ══════════════════════════════════════════════════════════════
# SCHRITT 8: Systemdienste einrichten
# ══════════════════════════════════════════════════════════════
info "8/10 Systemdienste einrichten..."

# pidrive.service aus Repo kopieren
if [ -f "$INSTALL_DIR/systemd/pidrive.service" ]; then
    cp "$INSTALL_DIR/systemd/pidrive.service" "$SERVICE_DIR/pidrive.service"
    # Pfade auf aktuellen User anpassen (falls nicht pi)
    # Nur ExecStart und WorkingDirectory anpassen — keine anderen Zeilen anfassen
    # Aggressives sed auf die ganze Datei wuerde TTY/PAM-Zeilen beschaedigen
    sed -i "s|^WorkingDirectory=.*|WorkingDirectory=$REAL_HOME/pidrive/pidrive|" "$SERVICE_DIR/pidrive.service"
    sed -i "s|^ExecStart=.*|ExecStart=/usr/bin/python3 $REAL_HOME/pidrive/pidrive/launcher.py|" "$SERVICE_DIR/pidrive.service"
    ok "pidrive.service aus Repo kopiert und angepasst"
else
    warn "pidrive.service nicht im Repo — erstelle Fallback"
    cat > "$SERVICE_DIR/pidrive.service" << EOF
[Unit]
Description=PiDrive - Car Infotainment
After=multi-user.target rc-local.service

[Service]
Type=simple
User=root
Environment=SDL_FBDEV=/dev/fb0
Environment=SDL_VIDEODRIVER=fbcon
Environment=SDL_NOMOUSE=1
WorkingDirectory=$INSTALL_DIR/pidrive
ExecStartPre=/bin/sleep 3
ExecStartPre=/bin/bash -c 'echo 0 > /sys/class/vtconsole/vtcon0/bind || true'
ExecStartPre=/bin/bash -c 'echo 0 > /sys/class/vtconsole/vtcon1/bind || true'
ExecStart=/usr/bin/python3 $INSTALL_DIR/pidrive/launcher.py
Restart=always
RestartSec=5
StandardOutput=null
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
    ok "pidrive.service (Fallback) erstellt"
fi

# rfkill-unblock.service
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
systemctl enable pidrive
systemctl enable rfkill-unblock 2>/dev/null || true
ok "Dienste aktiviert (pidrive, rfkill-unblock)"

# SSH
systemctl enable ssh 2>/dev/null && systemctl start ssh 2>/dev/null || true
ok "SSH aktiviert"

# ══════════════════════════════════════════════════════════════
# SCHRITT 9: Berechtigungen
# ══════════════════════════════════════════════════════════════
info "9/10 Berechtigungen setzen..."
usermod -a -G video,input,render,tty "$REAL_USER" 2>/dev/null || true
ok "Gruppen: video, input, render, tty"

# chmod tty3 nicht mehr noetig

ln -sf "$INSTALL_DIR/pidrive_ctrl.py" "$REAL_HOME/pidrive_ctrl.py" 2>/dev/null || true
ok "pidrive_ctrl.py verknuepft"

# ══════════════════════════════════════════════════════════════
# SCHRITT 10: Spotify konfigurieren + Service starten
# ══════════════════════════════════════════════════════════════
info "10/10 Spotify & Abschluss..."

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
    if grep -q "LIBRESPOT_NAME" /etc/raspotify/conf; then
        sed -i 's/^LIBRESPOT_NAME=.*/LIBRESPOT_NAME="PiDrive"/' /etc/raspotify/conf
    else
        echo 'LIBRESPOT_NAME="PiDrive"' >> /etc/raspotify/conf
    fi
    grep -q "^LIBRESPOT_ONEVENT" /etc/raspotify/conf || \
        echo "LIBRESPOT_ONEVENT=/usr/local/bin/spotify_event.sh" >> /etc/raspotify/conf
    if [ -f /lib/systemd/system/raspotify.service ]; then
        sed -i 's/Wants=network.target/Wants=network-online.target/'  /lib/systemd/system/raspotify.service 2>/dev/null || true
        sed -i 's/After=network.target/After=network-online.target/' /lib/systemd/system/raspotify.service 2>/dev/null || true
        systemctl enable systemd-networkd-wait-online.service 2>/dev/null || true
        systemctl daemon-reload
    fi
    ok "Raspotify konfiguriert"
fi

# ── Zeitzone und fake-hwclock ──────────────────────────────────────────────
info "Zeitzone und Uhr..."

# Zeitzone Deutschland
timedatectl set-timezone Europe/Berlin 2>/dev/null ||     ln -sf /usr/share/zoneinfo/Europe/Berlin /etc/localtime 2>/dev/null || true
ok "Zeitzone: Europe/Berlin"

# fake-hwclock: Pi merkt sich letzte bekannte Zeit beim Shutdown
# Verhindert apt "Datei noch nicht gueltig" nach Stromunterbrechung
if ! dpkg -l fake-hwclock 2>/dev/null | grep -q "^ii"; then
    apt-get install -y -qq fake-hwclock 2>/dev/null || true
fi
fake-hwclock save 2>/dev/null && ok "fake-hwclock: aktuelle Zeit gespeichert" || true

# ── RTL-SDR Check ─────────────────────────────────────────────────────────
info "RTL-SDR pruefen..."
if lsusb 2>/dev/null | grep -qiE "rtl|realtek|2838|0bda"; then
    ok "RTL-SDR USB Stick erkannt — DAB+ und FM verfuegbar"
else
    warn "RTL-SDR USB Stick nicht gefunden"
    warn "  -> DAB+ und FM benoetigen einen RTL-SDR Stick (z.B. RTL2832U)"
    warn "  -> Jetzt anschliessen oder spaeter: Musik → DAB+ / FM Radio"
fi
if which rtl_fm >/dev/null 2>&1; then
    ok "rtl_fm vorhanden"
else
    warn "rtl_fm nicht installiert -> sudo apt install rtl-sdr"
fi
if which welle-cli >/dev/null 2>&1; then
    ok "welle-cli vorhanden (DAB+)"
else
    warn "welle-cli nicht installiert -> sudo apt install welle.io"
fi

# Service starten + ausfuehrliche Verifikation
info "pidrive.service starten..."
if systemctl start pidrive 2>/dev/null; then
    sleep 5  # Launcher braucht Zeit fuer setsid+TIOCSCTTY
    if systemctl is-active --quiet pidrive; then
        ok "pidrive.service laeuft!"

        # ── KRITISCHER TEST: Ist der Prozess wirklich Python? ──────────────
        PID=$(systemctl show pidrive --property=MainPID --value 2>/dev/null)
        if [ -n "$PID" ] && [ "$PID" != "0" ]; then
            ok "Main PID: $PID"

            # exe pruefen — muss /usr/bin/python3 sein, NICHT systemd!
            EXE=$(readlink -f /proc/$PID/exe 2>/dev/null || echo "unbekannt")
            if echo "$EXE" | grep -q "python"; then
                ok "PID $PID exe: $EXE  ← Python laeuft!"
            elif echo "$EXE" | grep -q "systemd"; then
                err "PID $PID exe: $EXE  ← KEIN Python! systemd-Helper haengt."
                err "  → PAMName/StandardInput/TTYPath Kombination blockiert Prozessstart."
                err "  → service-Datei pruefen: PAMName=login entfernen?"
            else
                warn "PID $PID exe: $EXE  ← unbekannt, kein Python?"
            fi

            # cmdline pruefen
            CMDLINE=$(tr '\0' ' ' < /proc/$PID/cmdline 2>/dev/null | head -c 80)
            if echo "$CMDLINE" | grep -q "launcher.py"; then
                ok "cmdline: $CMDLINE"
            else
                warn "cmdline: '$CMDLINE'  ← launcher.py nicht sichtbar"
            fi

            # stdin pruefen
            STDIN=$(readlink /proc/$PID/fd/0 2>/dev/null || echo "unbekannt")
            info "stdin (fd 0) → $STDIN"

            # Neue Log-Eintraege pruefen
            sleep 3
            LOG_NEW=$(grep "LAUNCH\|PiDrive gestartet\|pygame" /var/log/pidrive/pidrive.log 2>/dev/null | tail -3)
            if [ -n "$LOG_NEW" ]; then
                ok "Neue Log-Eintraege vorhanden:"
                echo "$LOG_NEW" | while read line; do info "  $line"; done
            else
                warn "Keine neuen Log-Eintraege — Prozess haengt vor erstem log.info()"
            fi
        else
            warn "Kein PID ermittelt"
        fi
    else
        warn "pidrive.service nicht aktiv — pruefe Log unten"
    fi
else
    warn "Start fehlgeschlagen (evtl. noch kein Display-Treiber)"
fi

# ══════════════════════════════════════════════════════════════
# DIAGNOSE
# ══════════════════════════════════════════════════════════════
echo ""
echo -e "${BOLD}${CYAN}Automatische Diagnose...${NC}"
if [ -f "$INSTALL_DIR/pidrive/diagnose.py" ]; then
    python3 "$INSTALL_DIR/pidrive/diagnose.py" 2>/dev/null || true
else
    warn "diagnose.py nicht gefunden"
fi

# ══════════════════════════════════════════════════════════════
# ABSCHLUSS
# ══════════════════════════════════════════════════════════════
echo ""
echo -e "${BOLD}${GREEN}Installation abgeschlossen! (v$VER)${NC}"
echo ""
echo -e "${BOLD}Log pruefen:${NC}"
echo -e "  ${CYAN}tail -20 $LOG_DIR/pidrive.log${NC}"
echo -e "  ${CYAN}journalctl -u pidrive -f${NC}"
echo ""
echo -e "${BOLD}Naechste Schritte:${NC}"
echo -e "  1. ${YELLOW}Display-Treiber (falls noch nicht):${NC}"
echo -e "     git clone https://github.com/goodtft/LCD-show ~/LCD-show"
echo -e "     cd ~/LCD-show && sudo ./LCD35-show"
echo ""
echo -e "  2. ${YELLOW}Spotify OAuth (einmalig):${NC}"
echo -e "     sudo systemctl stop raspotify"
echo -e "     /usr/bin/librespot --name PiDrive --enable-oauth \\"
echo -e "       --system-cache /var/cache/raspotify"
echo ""
echo -e "  3. ${YELLOW}Nach Display-Treiber: neu starten:${NC}"
echo -e "     ${CYAN}sudo reboot${NC}"
echo ""
echo -e "${BOLD}Update:${NC}"
echo -e "  ${CYAN}curl -sL https://raw.githubusercontent.com/MPunktBPunkt/pidrive/main/install.sh | sudo bash${NC}"
