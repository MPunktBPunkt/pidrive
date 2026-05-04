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
# Installationsverzeichnis — wird nach REAL_USER-Erkennung gesetzt
# (Platzhalter; wird nach User-Erkennung weiter unten überschrieben)
INSTALL_DIR="/home/pi/pidrive"
SERVICE_DIR="/etc/systemd/system"
LOG_DIR="/var/log/pidrive"
# Echter User — SUDO_USER ist gesetzt wenn via "sudo bash" aufgerufen
# Fallback: erster User mit UID >= 1000 (nicht root), dann pi
if [ -n "$SUDO_USER" ] && id "$SUDO_USER" >/dev/null 2>&1; then
    REAL_USER="$SUDO_USER"
elif id "pi" >/dev/null 2>&1; then
    REAL_USER="pi"
else
    REAL_USER=$(getent passwd | awk -F: '$3 >= 1000 && $3 < 65534 {print $1; exit}')
    [ -z "$REAL_USER" ] && REAL_USER="pi"
fi
REAL_HOME=$(eval echo "~$REAL_USER")
INSTALL_DIR="$REAL_HOME/pidrive"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

ok()   { echo -e "${GREEN}  ✓ ${1}${NC}"; }
info() { echo -e "${BLUE}  → ${1}${NC}"; }
warn() { echo -e "${YELLOW}  ⚠ ${1}${NC}"; }
err()  { echo -e "${RED}  ✗ ${1}${NC}"; }

echo -e "${BOLD}${BLUE}"
cat << 'EOF'
╔═══════════════════════════════════════════╗
║        PiDrive Installer v0.10.16           ║
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

# pip3 Kompatibilität: --break-system-packages nur ab pip 22 (Python 3.10+)
# Bullseye (Python 3.9) hat pip 21 ohne dieses Flag
_pip_install() {
    local pkg="$1"
    pip3 install "$pkg" --break-system-packages -q 2>/dev/null || \
    pip3 install "$pkg" -q 2>/dev/null || \
    true
}
_pip_install mutagen
_pip_install RPi.GPIO
# v0.9.4: numpy für spectrum.py Prototyp
apt-get install -y python3-numpy -q 2>/dev/null || _pip_install numpy
ok "Python-Pakete installiert (mutagen, RPi.GPIO, numpy)"

# ══════════════════════════════════════════════════════════════
# SCHRITT 3: Repository klonen / aktualisieren
# ══════════════════════════════════════════════════════════════
info "3/10 Repository von GitHub..."
if [ -d "$INSTALL_DIR/.git" ]; then
    info "Update von GitHub..."
    cd "$INSTALL_DIR"
    # v0.9.29: settings.json schützen — git stash + restore + key-merge
    _SETTINGS_FILE="$INSTALL_DIR/pidrive/config/settings.json"
    _SETTINGS_BAK="/tmp/pidrive_settings_backup.json"
    if [ -f "$_SETTINGS_FILE" ]; then
        cp "$_SETTINGS_FILE" "$_SETTINGS_BAK"
        # git stash: legt lokale Änderungen beiseite damit git pull nicht abbricht
        cd "$INSTALL_DIR"
        sudo -u "$REAL_USER" git stash 2>/dev/null || true
        info "settings.json gesichert (git stash)"
    fi
    sudo -u "$REAL_USER" git pull
    # settings.json: Backup wiederherstellen (überschreibt Repo-Default)
    if [ -f "$_SETTINGS_BAK" ]; then
        cp "$_SETTINGS_BAK" "$_SETTINGS_FILE"
        ok "settings.json wiederhergestellt (Benutzer-Einstellungen erhalten)"
        # Fehlende neue Keys aus Defaults ergänzen
        python3 -c "
import sys
sys.path.insert(0, '$INSTALL_DIR/pidrive')
try:
    from settings import load_settings, save_settings
    s = load_settings()
    save_settings(s)
    print('  ✓ settings.json: fehlende Keys ergänzt')
except Exception as e:
    print(f'  ⚠ settings merge: {e}')
" 2>/dev/null || true
    fi
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
# Bookworm: /boot/firmware/config.txt  |  Bullseye: /boot/config.txt
if [ -f /boot/firmware/config.txt ]; then
    BOOT_DIR="/boot/firmware"
else
    BOOT_DIR="/boot"
fi
CONFIG_TXT="$BOOT_DIR/config.txt"
CMDLINE_TXT="$BOOT_DIR/cmdline.txt"
ok "Boot-Verzeichnis: $BOOT_DIR"

[ ! -f "$CONFIG_TXT.bak" ] && cp "$CONFIG_TXT" "$CONFIG_TXT.bak"

sed -i 's/^camera_auto_detect=1/camera_auto_detect=0/'   "$CONFIG_TXT" 2>/dev/null || true
sed -i 's/^display_auto_detect=1/display_auto_detect=0/' "$CONFIG_TXT" 2>/dev/null || true
grep -q "^camera_auto_detect"  "$CONFIG_TXT" || echo "camera_auto_detect=0"  >> "$CONFIG_TXT"
grep -q "^display_auto_detect" "$CONFIG_TXT" || echo "display_auto_detect=0" >> "$CONFIG_TXT"
sed -i 's/^dtoverlay=vc4-kms-v3d/#dtoverlay=vc4-kms-v3d/'   "$CONFIG_TXT" 2>/dev/null || true
sed -i 's/^dtoverlay=vc4-fkms-v3d/#dtoverlay=vc4-fkms-v3d/' "$CONFIG_TXT" 2>/dev/null || true
grep -q "^max_framebuffers=2" "$CONFIG_TXT" || echo "max_framebuffers=2" >> "$CONFIG_TXT"

# v0.10.9: fbcon=nodeconfig in cmdline.txt setzen (SPI-Display braucht das)
# LCD-show setzt es auch, aber erst nach Neustart → direkt hier sicherstellen
if [ -f "$CMDLINE_TXT" ]; then
    if ! grep -q "fbcon=nodeconfig" "$CMDLINE_TXT"; then
        sed -i 's/$/ fbcon=nodeconfig/' "$CMDLINE_TXT"
        ok "cmdline.txt: fbcon=nodeconfig gesetzt"
    else
        ok "cmdline.txt: fbcon=nodeconfig bereits vorhanden"
    fi
fi
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
  # v0.9.4: PULSE_SERVER fuer System-PulseAudio erzwingen
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
usermod -a -G video,input,render,tty,systemd-journal "$REAL_USER" 2>/dev/null || true
ok "Gruppen: video, input, render, tty, systemd-journal"

  # ── Berechtigungen prüfen und korrigieren ─────────────────────────────────
  _perm_ok=0; _perm_fix=0; _perm_err=0
  _chk() {
    local p="$1" eo="$2" eg="$3" em="$4" d="$5"
    [ -e "$p" ] || return 0
    local co cg cm changed=0
    co=$(stat -c '%U' "$p" 2>/dev/null)
    cg=$(stat -c '%G' "$p" 2>/dev/null)
    cm=$(stat -c '%a' "$p" 2>/dev/null)
    if [ "$co" != "$eo" ] || [ "$cg" != "$eg" ]; then chown "$eo:$eg" "$p" 2>/dev/null && changed=1; fi
    if [ "$cm" != "$em" ]; then chmod "$em" "$p" 2>/dev/null && changed=1; fi
    if [ $changed -eq 1 ]; then
      warn "  Korrigiert: $p  ($co:$cg/$cm → $eo:$eg/$em)  [$d]"
      _perm_fix=$((_perm_fix+1))
    else
      _perm_ok=$((_perm_ok+1))
    fi
  }
  # Repo + Python-Dateien
  _chk "$INSTALL_DIR"         "$REAL_USER" "$REAL_USER" "755" "Repo-Dir"
  _chk "$INSTALL_DIR/pidrive" "$REAL_USER" "$REAL_USER" "755" "App-Dir"
  _chk "$INSTALL_DIR/install.sh" "$REAL_USER" "$REAL_USER" "755" "Installer"
  for f in "$INSTALL_DIR"/pidrive/*.py "$INSTALL_DIR"/pidrive/modules/*.py "$INSTALL_DIR"/pidrive/web/api/*.py; do
    [ -f "$f" ] && _chk "$f" "$REAL_USER" "$REAL_USER" "644" "Python"
  done
  # Log-Verzeichnis: root schreibt, pi liest im WebUI
  _chk "/var/log/pidrive" "root" "$REAL_USER" "775" "Log-Dir"
  for f in /var/log/pidrive/*.log; do [ -f "$f" ] && _chk "$f" "root" "root" "644" "Log-Datei"; done
  # System-Konfiguration
  [ -f /etc/pulse/system.pa ] && _chk /etc/pulse/system.pa root root 644 "system.pa"
  [ -f /etc/asound.conf ]     && _chk /etc/asound.conf     root root 644 "asound.conf"
  for f in /etc/systemd/system/pidrive*.service; do [ -f "$f" ] && _chk "$f" root root 644 "systemd"; done
  [ -f /etc/systemd/system/pulseaudio.service ] && _chk /etc/systemd/system/pulseaudio.service root root 644 "PA Service"
  # Binaries: nur prüfen, nicht ändern
  for bin in /usr/bin/rtl_fm /usr/bin/welle-cli /usr/bin/mpv /usr/bin/pactl; do
    if [ ! -x "$bin" ]; then warn "  Binary fehlt: $bin"; _perm_err=$((_perm_err+1)); else _perm_ok=$((_perm_ok+1)); fi
  done
  ok "Berechtigungen: ${_perm_ok} OK | ${_perm_fix} korrigiert | ${_perm_err} Fehler"

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

# Raspotify installieren falls nicht vorhanden (Frisch-Install)
if ! dpkg -l raspotify 2>/dev/null | grep -q "^ii" && [ ! -f /etc/raspotify/conf ]; then
    info "Raspotify installieren..."
    # Offizielle Installations-Methode (dtcooper/raspotify)
    _RASP_DEB="https://github.com/dtcooper/raspotify/releases/latest/download/raspotify_latest_armhf.deb"
    if curl -sLo /tmp/raspotify.deb "$_RASP_DEB" 2>/dev/null; then
        dpkg -i /tmp/raspotify.deb 2>/dev/null || apt-get -f install -y -qq 2>/dev/null || true
        rm -f /tmp/raspotify.deb
        ok "Raspotify installiert"
    else
        warn "Raspotify-Download fehlgeschlagen — Spotify Connect nicht verfügbar"
        warn "  Manuell: https://github.com/dtcooper/raspotify"
    fi
fi
if [ -f /etc/raspotify/conf ]; then
    sed -i 's/^LIBRESPOT_DISABLE_CREDENTIAL_CACHE=/#LIBRESPOT_DISABLE_CREDENTIAL_CACHE=/' /etc/raspotify/conf
    if grep -q "LIBRESPOT_NAME" /etc/raspotify/conf; then
        sed -i 's/^LIBRESPOT_NAME=.*/LIBRESPOT_NAME="PiDrive"/' /etc/raspotify/conf
    else
        echo 'LIBRESPOT_NAME="PiDrive"' >> /etc/raspotify/conf
    fi
    grep -q "^LIBRESPOT_ONEVENT" /etc/raspotify/conf || \
        echo "LIBRESPOT_ONEVENT=/usr/local/bin/spotify_event.sh" >> /etc/raspotify/conf

    # v0.9.4: Zielarchitektur Option B — Spotify über zentralen PulseAudio-Pfad
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

  # v0.9.9: /etc/asound.conf — ALSA Default auf Klinke (Card 1) setzen
  # KRITISCH: Auf modernem Pi OS (Kernel >=5.x) ist Card 0 = HDMI, Card 1 = Headphones/Klinke
  # Ohne asound.conf geht ALSA default auf HDMI → kein Ton aus der Klinke
  cat > /etc/asound.conf << 'ASOUNDEOF'
# PiDrive: ALSA Default auf bcm2835 Headphones (Klinke) setzen
# Card 0 = HDMI, Card 1 = Headphones auf modernem Pi OS
defaults.pcm.card 1
defaults.ctl.card 1
defaults.pcm.device 0
ASOUNDEOF
  ok "ALSA: /etc/asound.conf geschrieben (default=card 1 Headphones)"

  # Klinke via amixer auf der richtigen Karte aktivieren
  # Card-Erkennung: Suche nach 'Headphones' in aplay -l
  KLINKE_CARD=$(aplay -l 2>/dev/null | grep -i "headphones" | head -1 | awk '{print $2}' | tr -d ':')
  if [ -z "$KLINKE_CARD" ]; then KLINKE_CARD=1; fi
  amixer -q -c "$KLINKE_CARD" sset 'PCM' 85% unmute 2>/dev/null && ok "Pi Audio: Klinke aktiviert (card $KLINKE_CARD PCM unmute 85%)" || ok "Pi Audio: amixer PCM card $KLINKE_CARD nicht gefunden"

  # v0.10.9: system.pa vollständig neu schreiben
  # Bookworm-PA schreibt kein module-alsa-card in system.pa → komplettes File
  mkdir -p /etc/pulse
  cat > /etc/pulse/system.pa << 'SYSTEMPA'
# PiDrive system.pa — v0.10.9
# System-weiter PulseAudio Daemon (nicht User-Session)
.fail

load-module module-device-restore
load-module module-stream-restore
load-module module-card-restore

# ALSA Hardware: Card 0 = HDMI, Card 1 = Headphones/Klinke
load-module module-alsa-card device_id=0
load-module module-alsa-card device_id=1

# Bluetooth A2DP
load-module module-bluetooth-discover
load-module module-bluetooth-policy

# DBUS
load-module module-dbus-protocol

# IPC
load-module module-native-protocol-unix auth-anonymous=1

# Klinke (Card 1) als Default-Sink
set-default-sink alsa_output.1.stereo-fallback
SYSTEMPA
  ok "system.pa: vollständig neu geschrieben (Card 0+1, BT, IPC)"

  # v0.9.14: pulse-access Gruppe
  groupadd -f pulse-access 2>/dev/null || true
  usermod -aG pulse-access root 2>/dev/null || true
  usermod -aG pulse-access "$REAL_USER" 2>/dev/null || true
  ok "pulse-access Gruppe: root + $REAL_USER hinzugefügt"

  # v0.10.16: PulseAudio System-Service einrichten (Bookworm-kompatibel)
  # Bookworm installiert PA als User-Session-Service → umschalten auf System-Mode
  # Schritt 1: User-Session PA für ALLE User deaktivieren + laufende Instanz töten
  systemctl --global disable pulseaudio.socket pulseaudio.service 2>/dev/null || true
  # Als pi-User den User-Service stoppen und masken
  sudo -u "$REAL_USER" XDG_RUNTIME_DIR="/run/user/$(id -u $REAL_USER 2>/dev/null || echo 1000)"       systemctl --user stop pulseaudio.service pulseaudio.socket 2>/dev/null || true
  sudo -u "$REAL_USER" XDG_RUNTIME_DIR="/run/user/$(id -u $REAL_USER 2>/dev/null || echo 1000)"       systemctl --user mask pulseaudio.socket 2>/dev/null || true
  sudo -u "$REAL_USER" XDG_RUNTIME_DIR="/run/user/$(id -u $REAL_USER 2>/dev/null || echo 1000)"       systemctl --user disable pulseaudio.service 2>/dev/null || true
  # User-PA-Socket null-masken: ln -sf /dev/null verhindert Socket-Aktivierung zuverlässig
  mkdir -p /etc/systemd/user
  ln -sf /dev/null /etc/systemd/user/pulseaudio.socket
  ln -sf /dev/null /etc/systemd/user/pulseaudio.service
  ok "User-PA Socket + Service null-maskiert"
  # Alle laufenden PA-Prozesse als User beenden
  pkill -u "$REAL_USER" pulseaudio 2>/dev/null || true
  sleep 1
  # Schritt 2: System-Service Unit schreiben
  cat > /etc/systemd/system/pulseaudio.service << 'PASERVICE'
[Unit]
Description=PiDrive Sound Service (System Mode)
After=bluetooth.target dbus.service
Requires=dbus.service
Before=pidrive_core.service

[Service]
Type=notify
ExecStart=/usr/bin/pulseaudio --system --realtime --disallow-exit --no-cpu-limit --log-target=journal
Restart=on-failure
RestartSec=5
LimitRTPRIO=99
LimitNICE=-19
ProtectSystem=false
ProtectHome=false
PrivateUsers=false

[Install]
WantedBy=multi-user.target
PASERVICE
  # Lingering deaktivieren: verhindert user-systemd Session-Autostart
  loginctl disable-linger "$REAL_USER" 2>/dev/null || true
  # Alle PA-Prozesse killen bevor System-PA startet
  pkill -9 pulseaudio 2>/dev/null || true
  sleep 1
  systemctl daemon-reload
  systemctl enable pulseaudio 2>/dev/null || true
  systemctl start pulseaudio 2>/dev/null || true
  sleep 3
  # Sicherstellen dass kein User-PA mehr läuft
  pkill -u "$REAL_USER" pulseaudio 2>/dev/null || true
  sleep 1
  # Sinks prüfen (nicht nur ob Service aktiv)
  _pa_sinks=$(PULSE_SERVER=unix:/var/run/pulse/native pactl list sinks short 2>/dev/null | wc -l)
  if systemctl is-active --quiet pulseaudio && [ "${_pa_sinks:-0}" -gt 0 ]; then
    ok "PulseAudio: System-Service läuft ($_pa_sinks Sinks vorhanden)"
    # Socket-Existenz prüfen (pidrive_core.service braucht diesen Pfad)
    if [ -S /var/run/pulse/native ]; then
      ok "PulseAudio: Socket /var/run/pulse/native vorhanden ✓"
    else
      warn "PulseAudio: Socket /var/run/pulse/native fehlt — Reboot erforderlich"
    fi
  elif systemctl is-active --quiet pulseaudio; then
    warn "PulseAudio: Service aktiv aber keine Sinks — Reboot erforderlich"
    warn "  → Nach Reboot: sudo systemctl status pulseaudio"
  else
    warn "PulseAudio System-Service inaktiv"
    warn "  Debug: journalctl -u pulseaudio --no-pager | tail -20"
  fi

  # v0.9.13: Default Sink auf Klinke (Card 1 = alsa_output.1.*) setzen
  # ACHTUNG: alsa_output.0.* enthält KEIN "hdmi" im Namen!
  # -v hdmi filtert NOT, weil "0.stereo-fallback" ≠ "hdmi" — Card-Index ist der Indikator.
  KLINKE_SINK=$(PULSE_SERVER=unix:/var/run/pulse/native pactl list sinks short 2>/dev/null | awk '$2 ~ /alsa_output\.1\./ {print $2; exit}')
  if [ -z "$KLINKE_SINK" ]; then
    # Fallback: analog-stereo oder headphone im Namen
    KLINKE_SINK=$(PULSE_SERVER=unix:/var/run/pulse/native pactl list sinks short 2>/dev/null | grep -i 'analog\|headphone' | grep alsa_output | head -1 | awk '{print $2}')
  fi
  if [ -n "$KLINKE_SINK" ]; then
    PULSE_SERVER=unix:/var/run/pulse/native pactl set-default-sink "$KLINKE_SINK" 2>/dev/null || true
    ok "PulseAudio: Default Sink = $KLINKE_SINK (Klinke Card 1)"

    # v0.10.3: Default Sink in system.pa persistieren (überlebt Reboots)
    if [ -f /etc/pulse/system.pa ]; then
      # Alten set-default-sink Eintrag entfernen, neuen am Ende schreiben
      grep -v "^set-default-sink" /etc/pulse/system.pa > /tmp/system.pa.new
      echo "" >> /tmp/system.pa.new
      echo "# PiDrive: Klinke als Default-Sink (v0.10.3)" >> /tmp/system.pa.new
      echo "set-default-sink $KLINKE_SINK" >> /tmp/system.pa.new
      mv /tmp/system.pa.new /etc/pulse/system.pa
      ok "PulseAudio: Default Sink in system.pa persistiert ($KLINKE_SINK)"
    fi
  else
    warn "PulseAudio: Klinken-Sink noch nicht sichtbar — beim ersten Abspielen gesetzt"
  fi

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
  # v0.9.4: WebUI Import-Smoke-Test — verhindert stille Strukturfehler wie v0.8.12
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
# v0.10.0: Diagnose erst nach boot_phase=steady warten (max 25s)
echo ""
echo "  → Warte auf boot_phase=steady..."
_SW=0
while [ $_SW -lt 25 ]; do
  _PHASE=$(python3 -c "import json; print(json.load(open('/tmp/pidrive_source_state.json')).get('boot_phase',''))" 2>/dev/null || echo "")
  [ "$_PHASE" = "steady" ] && { ok "boot_phase=steady — starte Diagnose"; break; }
  sleep 1; _SW=$((_SW+1))
done
[ $_SW -ge 25 ] && warn "Timeout — Diagnose startet (boot_phase ggf. noch nicht steady)"
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

# ── Car-Only Cleanup (v0.10.16: bei Frisch-Install mit anschliessendem Reboot) ──
if [ -f "$INSTALL_DIR/pidrive_car_only_cleanup.sh" ]; then
  _CLEANUP_DONE_FILE="/etc/pidrive_car_cleanup_done"
  if [ ! -f "$_CLEANUP_DONE_FILE" ]; then
    info "Car-Only Cleanup (Erstinstallation — automatisch)..."
    echo -e "  Deaktiviert unnötige Dienste und User-PulseAudio."
    bash "$INSTALL_DIR/pidrive_car_only_cleanup.sh" || true
    touch "$_CLEANUP_DONE_FILE"
    ok "Car-Only Cleanup abgeschlossen"
    echo ""
    warn "Erstinstallation: Reboot erforderlich damit PulseAudio System-Mode greift."
    echo -e "  ${CYAN}sudo reboot${NC}"
    echo ""
    echo -e "${BOLD}Update nach Reboot:${NC}"
    echo -e "  ${CYAN}curl -sL https://raw.githubusercontent.com/MPunktBPunkt/pidrive/main/install.sh | sudo bash${NC}"
    exit 0
  else
    echo ""
    echo -e "${BOLD}${YELLOW}Optional: Car-Only System-Cleanup${NC}"
    echo -e "  Deaktiviert unnötige Dienste (cups, ModemManager, snapd, ...)"
    echo -e "  und bereinigt Desktop-Audio-Stack (PipeWire, User-PulseAudio)."
    echo ""
    read -r -t 15 -p "  Car-Only Cleanup erneut ausführen? [j/N] " CLEANUP_CHOICE || CLEANUP_CHOICE="n"
    echo ""
    if [[ "$CLEANUP_CHOICE" =~ ^[jJyY]$ ]]; then
      echo -e "${CYAN}  Starte Car-Only Cleanup...${NC}"
      bash "$INSTALL_DIR/pidrive_car_only_cleanup.sh" || true
      ok "Car-Only Cleanup abgeschlossen"
    else
      echo -e "  Cleanup übersprungen."
      echo -e "  Manuell: ${CYAN}sudo bash ~/pidrive/pidrive_car_only_cleanup.sh${NC}"
    fi
  fi
fi

echo ""
echo -e "${BOLD}Update:${NC}"
echo -e "  ${CYAN}curl -sL https://raw.githubusercontent.com/MPunktBPunkt/pidrive/main/install.sh | sudo bash${NC}"
