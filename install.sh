#!/bin/bash
# ============================================================
# PiDrive Install Script v0.9.3
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
║        PiDrive Installer v0.9.3           ║
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
for SVC in pidrive_core pidrive_display pidrive; do
    if systemctl is-active --quiet $SVC 2>/dev/null; then
        systemctl stop $SVC 2>/dev/null || true
        ok "$SVC gestoppt"
    fi
done
ok "Services gestoppt"
# fbcp dauerhaft entfernen (GPT-5.4: sonst blockiert fbcp fb1)
pkill fbcp 2>/dev/null || true
# Falls fbcp als systemd-Service laeuft
systemctl stop fbcp 2>/dev/null || true
systemctl disable fbcp 2>/dev/null || true
# rc.local von fbcp bereinigen
if grep -q "fbcp" /etc/rc.local 2>/dev/null; then
    sed -i '/fbcp/d' /etc/rc.local
    ok "fbcp aus rc.local entfernt"
fi
ok "fbcp gestoppt und dauerhaft deaktiviert"

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
    python3-flask \
    python3-bluez \
    python3-dbus \
    python3-gi \
    2>/dev/null || true

apt-get install -y -qq welle.io 2>/dev/null || \
    warn "welle.io nicht verfuegbar — DAB+ spaeter installierbar"
ok "System-Pakete installiert"

pip3 install mutagen --break-system-packages -q 2>/dev/null || \
pip3 install mutagen -q 2>/dev/null || true
# v0.9.3: RPi.GPIO für Display-Tasten (Key1/Key2/Key3)
pip3 install RPi.GPIO --break-system-packages -q 2>/dev/null || true
ok "Python-Pakete installiert (mutagen + RPi.GPIO)"

# ══════════════════════════════════════════════════════════════
# SCHRITT 3: Repository klonen / aktualisieren
# ══════════════════════════════════════════════════════════════
info "3/10 Repository von GitHub..."
if [ -d "$INSTALL_DIR/.git" ]; then
    info "Update von GitHub..."
    cd "$INSTALL_DIR"
    sudo -u "$REAL_USER" git pull
    # Veraltete .bak-Dateien entfernen
  find "$INSTALL_DIR" -name "*.bak" -delete 2>/dev/null || true
  # Altlasten explizit entfernen
  for _dead in main.py trigger.py ui.py launcher.py; do
    rm -f "$INSTALL_DIR/pidrive/$_dead" 2>/dev/null || true
  done
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
# v0.6.0: minimal rc.local - kein fbcp, kein chvt, kein tty3
# Immer neu schreiben fuer saubere Migration
cat > "$RC" << 'RCEOF'
#!/bin/sh -e
# rc.local - PiDrive v0.6.0
# vtcon1 unbinden: fbcon gibt fb1 frei fuer pygame direkt
echo 0 > /sys/class/vtconsole/vtcon1/bind 2>/dev/null || true
echo 0 > /sys/class/graphics/fbcon/cursor_blink 2>/dev/null || true
exit 0
RCEOF
chmod +x "$RC"
ok "rc.local: vtcon1 unbind (kein fbcp, kein chvt, kein tty3)"

info "7/10 System-Konfiguration..."
# tty3 udev-Regel nicht mehr noetig (kein TIOCSCTTY in v0.6.0)
rm -f /etc/udev/rules.d/99-pidrive-tty.rules 2>/dev/null || true
udevadm control --reload-rules 2>/dev/null || true
ok "Alte tty3 udev-Regel entfernt"

# ══════════════════════════════════════════════════════════════
# SCHRITT 8: Systemdienste einrichten
# ══════════════════════════════════════════════════════════════
info "8/10 Systemdienste einrichten (Core + Display)..."

# Alten monolithischen Service deaktivieren
if systemctl is-active --quiet pidrive 2>/dev/null; then
    systemctl stop pidrive 2>/dev/null || true
fi
systemctl disable pidrive 2>/dev/null || true

# Core Service
cp "$INSTALL_DIR/systemd/pidrive_core.service" "$SERVICE_DIR/pidrive_core.service"
  # v0.9.3: PULSE_SERVER fuer System-PulseAudio erzwingen
  if ! grep -q "^Environment=PULSE_SERVER=" "$SERVICE_DIR/pidrive_core.service"; then
    sed -i '/^WorkingDirectory=/a Environment=PULSE_SERVER=unix:/var/run/pulse/native' \
        "$SERVICE_DIR/pidrive_core.service"
    ok "pidrive_core.service: PULSE_SERVER gesetzt"
  fi
sed -i "s|/home/pi/|$REAL_HOME/|g" "$SERVICE_DIR/pidrive_core.service"

# Display Service
cp "$INSTALL_DIR/systemd/pidrive_display.service" "$SERVICE_DIR/pidrive_display.service"
sed -i "s|/home/pi/|$REAL_HOME/|g" "$SERVICE_DIR/pidrive_display.service"

# Web Service (IMMER aktualisieren — Ordering-Cycle-Fix!)
if [ -f "$INSTALL_DIR/systemd/pidrive_web.service" ]; then
    cp "$INSTALL_DIR/systemd/pidrive_web.service" "$SERVICE_DIR/pidrive_web.service"
    sed -i "s|/home/pi/|$REAL_HOME/|g" "$SERVICE_DIR/pidrive_web.service"
fi

# AVRCP Service
if [ -f "$INSTALL_DIR/systemd/pidrive_avrcp.service" ]; then
    cp "$INSTALL_DIR/systemd/pidrive_avrcp.service" "$SERVICE_DIR/pidrive_avrcp.service"
    sed -i "s|/home/pi/|$REAL_HOME/|g" "$SERVICE_DIR/pidrive_avrcp.service"
fi

# v0.6.0: kein monolithischer pidrive.service mehr

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
systemctl enable pidrive_core pidrive_display rfkill-unblock 2>/dev/null || true
ok "Dienste aktiviert (pidrive_core, pidrive_display, rfkill-unblock)"
[ -f "$SERVICE_DIR/pidrive_web.service" ]   && systemctl enable pidrive_web   2>/dev/null || true
[ -f "$SERVICE_DIR/pidrive_avrcp.service" ] && systemctl enable pidrive_avrcp 2>/dev/null || true

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

# pidrive_ctrl.py entfernt in v0.6.0 — Steuerung via /tmp/pidrive_cmd

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

    # v0.9.3: Zielarchitektur Option B — Spotify über zentralen PulseAudio-Pfad
    # LIBRESPOT_DEVICE=default nutzt den PulseAudio Default-Sink (Klinke oder BT)
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
    if [ -f /lib/systemd/system/raspotify.service ]; then
        sed -i 's/Wants=network.target/Wants=network-online.target/'  /lib/systemd/system/raspotify.service 2>/dev/null || true
        sed -i 's/After=network.target/After=network-online.target/' /lib/systemd/system/raspotify.service 2>/dev/null || true
        # PULSE_SERVER: systemweiter PulseAudio-Daemon
        if ! grep -q "PULSE_SERVER=unix:/var/run/pulse/native" /lib/systemd/system/raspotify.service 2>/dev/null; then
            sed -i '/^\[Service\]/a Environment=PULSE_SERVER=unix:/var/run/pulse/native' \
                /lib/systemd/system/raspotify.service 2>/dev/null || true
        fi
        systemctl enable systemd-networkd-wait-online.service 2>/dev/null || true
        systemctl daemon-reload
    fi
    ok "Raspotify konfiguriert (zentral via PulseAudio)"

  # v0.9.3: Pi 3B Klinken-Ausgang physisch aktivieren
  # amixer numid=3: 0=auto, 1=klinke, 2=HDMI
  # Ohne diese Zeile bleibt Pi-Audio oft auf HDMI trotz PulseAudio-Routing
  amixer -q -c 0 cset numid=3 1 2>/dev/null && ok "Pi Audio: Klinke aktiviert (amixer numid=3=1)" || true

  # __pycache__ loeschen: alte .pyc mit pygame-Import
  find "$INSTALL_DIR/pidrive" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
  find "$INSTALL_DIR/pidrive" -name "*.pyc" -delete 2>/dev/null || true
  ok "Python Cache geloescht (sauberer Start)"
  # Web-Service neu starten
  systemctl reset-failed pidrive_web 2>/dev/null || true
  systemctl restart pidrive_web 2>/dev/null && \
    ok "pidrive_web.service neu gestartet" || \
    warn "pidrive_web konnte nicht gestartet werden"
  # AVRCP Service starten
  if [ -f "$SERVICE_DIR/pidrive_avrcp.service" ]; then
    systemctl restart pidrive_avrcp 2>/dev/null || true
    ok "pidrive_avrcp.service gestartet"
  fi
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

# DVB-T Treiber blacklisten (blockiert sonst RTL-SDR für rtl_fm/welle-cli)
info "RTL-SDR: DVB-T Treiber blacklisten..."
BLACKLIST=/etc/modprobe.d/rtl-sdr-blacklist.conf
if [ ! -f "$BLACKLIST" ] || ! grep -q "dvb_usb_rtl28xxu" "$BLACKLIST" 2>/dev/null; then
    echo "blacklist dvb_usb_rtl28xxu" > "$BLACKLIST"
    echo "blacklist rtl2832"         >> "$BLACKLIST"
    echo "blacklist rtl2830"         >> "$BLACKLIST"
    ok "DVB-T Treiber blacklisted — RTL-SDR jetzt nutzbar"
    # Sofort entladen falls geladen
    rmmod dvb_usb_rtl28xxu 2>/dev/null || true
    rmmod rtl2832 2>/dev/null || true
else
    ok "DVB-T Blacklist bereits vorhanden"
fi

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
# DVB-Treiber Status
if lsmod 2>/dev/null | grep -qE "dvb_usb_rtl28xxu|dvb_core"; then
    warn "DVB-Treiber noch geladen — RTL-SDR erst nach Reboot nutzbar"
else
    ok "Kein blockierender DVB-Treiber"
fi
# Unterspannung
_throttled=$(vcgencmd get_throttled 2>/dev/null || echo "n/a")
info "Stromversorgung: $_throttled"
if echo "$_throttled" | grep -qE "0x[0-9a-f]*[1-9][0-9a-f]*"; then
    warn "Unterspannung erkannt ($_throttled) — 5V/3A Netzteil empfohlen"
    dmesg -T 2>/dev/null | grep -iE "under-voltage|Undervoltage" | tail -3 || true
fi

# Syntax-Check vor Service-Start
info "Python Syntax-Check..."
SYNTAX_ERR=$(find "$INSTALL_DIR/pidrive" -name "*.py" -print0 |     xargs -0 python3 -m py_compile 2>&1 | head -3)
if [ -z "$SYNTAX_ERR" ]; then
    ok "Syntax-Check OK (alle .py Dateien)"
else
    err "Syntax-Fehler gefunden:"
    err "$SYNTAX_ERR"
    err "Service-Start abgebrochen — bitte Fehler beheben"
    exit 1
fi

# Alt-Importe pruefen (ui/trigger/launcher wurden als Dead-Code entfernt)
BAD_IMP=$(grep -RInE '^[[:space:]]*(from[[:space:]]+ui[[:space:]]+import|import[[:space:]]+ui[[:space:]]|from[[:space:]]+trigger[[:space:]]+import|from[[:space:]]+launcher[[:space:]]+import)' \
    "$INSTALL_DIR/pidrive" --include="*.py" --exclude-dir="__pycache__" 2>/dev/null || true)
if [ -n "$BAD_IMP" ]; then
    err "Veraltete Imports gefunden (bitte melden):"
    echo "$BAD_IMP" | head -5
    exit 1
else
    ok "Alt-Import-Check OK"
fi

# Import-Smoke-Test: prueft den echten Startpfad von main_core
if ! (cd "$INSTALL_DIR/pidrive" && python3 -c "import main_core" 2>/dev/null); then
    err "Import-Smoke-Test fehlgeschlagen:"
    (cd "$INSTALL_DIR/pidrive" && python3 -c "import main_core" 2>&1) | head -8
    exit 1
else
    ok "Import-Smoke-Test OK (main_core)"
  # v0.9.3: WebUI Import-Smoke-Test — verhindert stille Strukturfehler wie v0.8.12
  if ! (cd "$INSTALL_DIR/pidrive" && python3 -c "import webui" 2>/dev/null); then
    err "Import-Smoke-Test fehlgeschlagen: webui"
    (cd "$INSTALL_DIR/pidrive" && python3 -c "import webui" 2>&1) | head -12
    exit 1
  else
    ok "Import-Smoke-Test OK (webui)"
  fi
fi

# Service starten + ausfuehrliche Verifikation
info "pidrive_core.service starten..."
if systemctl start pidrive_core 2>/dev/null; then
    sleep 5
    if systemctl is-active --quiet pidrive_core; then
        ok "pidrive_core.service laeuft!"

        # ── KRITISCHER TEST: Ist der Prozess wirklich Python? ──────────────
        PID=$(systemctl show pidrive_core --property=MainPID --value 2>/dev/null)
        if [ -n "$PID" ] && [ "$PID" != "0" ]; then
            ok "Main PID: $PID"

            # exe pruefen — muss /usr/bin/python3 sein, NICHT systemd!
            EXE=$(readlink -f /proc/$PID/exe 2>/dev/null || echo "unbekannt")
            if echo "$EXE" | grep -q "python"; then
                ok "PID $PID exe: $EXE  ← Python laeuft!"
            elif echo "$EXE" | grep -q "systemd"; then
                err "PID $PID exe: $EXE  ← KEIN Python! systemd-Helper haengt."
                err "  → ExecStart in pidrive_core.service pruefen"
            else
                warn "PID $PID exe: $EXE  ← unbekannt, kein Python?"
            fi

            # cmdline pruefen
            CMDLINE=$(tr '\0' ' ' < /proc/$PID/cmdline 2>/dev/null | head -c 80)
            if echo "$CMDLINE" | grep -q "main_core"; then
                ok "cmdline: $CMDLINE"
            else
                info "cmdline: $CMDLINE  (execv von launcher zu main_core normal)"
            fi

            # stdin pruefen
            STDIN=$(readlink /proc/$PID/fd/0 2>/dev/null || echo "unbekannt")
            info "stdin (fd 0) → $STDIN"

            # Neue Log-Eintraege pruefen (nur Eintraege nach Service-Start)
            sleep 3
            START_TS=$(date +"%Y-%m-%d %H:%M" --date="2 seconds ago" 2>/dev/null || date +"%Y-%m-%d %H:%M")
            LOG_NEW=$(grep "Core v0.6\|Core-Loop\|Core gestartet\|PiDrive Core" /var/log/pidrive/pidrive.log 2>/dev/null \
                     | awk -v ts="$START_TS" '$0 >= ts' | tail -3)
            # Fallback: zeige letzte 3 Zeilen wenn awk keine Treffer
            if [ -z "$LOG_NEW" ]; then
                LOG_NEW=$(grep "PiDrive Core v${NEW_VERSION}\|Core-Loop" /var/log/pidrive/pidrive.log 2>/dev/null | tail -3)
            fi
            if [ -n "$LOG_NEW" ]; then
                ok "Neue Log-Eintraege vorhanden:"
                echo "$LOG_NEW" | while read line; do info "  $line"; done
            else
                warn "Keine neuen Log-Eintraege — Prozess haengt vor erstem log.info()"
            fi
        else
            warn "Kein PID ermittelt"
        fi
        # IPC pruefen
        sleep 2
        if [ -f /tmp/pidrive_status.json ]; then
            ok "IPC: /tmp/pidrive_status.json vorhanden"
        else
            warn "IPC: /tmp/pidrive_status.json fehlt — Core schreibt noch nicht"
        fi
        # Display Service starten (optional)
        systemctl start pidrive_display 2>/dev/null || true
        sleep 3
        if systemctl is-active --quiet pidrive_display; then
            ok "pidrive_display.service laeuft!"
        else
            warn "pidrive_display.service inaktiv (optional)"
            warn "  Teste fb1 direkt: sudo python3 -c \"import pygame; ..."
        fi
    else
        warn "pidrive_core.service nicht aktiv — pruefe Log unten"
    fi
else
    warn "pidrive_core Start fehlgeschlagen — journalctl -u pidrive_core"
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
echo -e "  ${CYAN}journalctl -u pidrive_core -f${NC}"
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

# ── Optionaler Car-Only Cleanup (v0.9.3) ─────────────────────────────────────
if [ -f "$INSTALL_DIR/pidrive_car_only_cleanup.sh" ]; then
  echo ""
  echo -e "${BOLD}${YELLOW}Optional: Car-Only System-Cleanup${NC}"
  echo -e "  Deaktiviert unnötige Dienste (cups, ModemManager, snapd, ...)"
  echo -e "  und bereinigt Desktop-Audio-Stack (PipeWire, User-PulseAudio)."
  echo -e "  Empfohlen wenn PiDrive das einzige Nutzungsziel des Pi ist."
  echo ""
  read -r -t 15 -p "  Car-Only Cleanup jetzt ausführen? [j/N] " CLEANUP_CHOICE || CLEANUP_CHOICE="n"
  echo ""
  if [[ "$CLEANUP_CHOICE" =~ ^[jJyY]$ ]]; then
    echo -e "${CYAN}  Starte Car-Only Cleanup...${NC}"
    bash "$INSTALL_DIR/pidrive_car_only_cleanup.sh" || true
  else
    echo -e "  Cleanup übersprungen."
    echo -e "  Manuell ausführen: ${CYAN}sudo bash ~/pidrive/pidrive_car_only_cleanup.sh${NC}"
  fi
fi

echo ""
echo -e "${BOLD}Update:${NC}"
echo -e "  ${CYAN}curl -sL https://raw.githubusercontent.com/MPunktBPunkt/pidrive/main/install.sh | sudo bash${NC}"
