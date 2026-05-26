#!/bin/bash
PIDRIVE_VERSION="0.11.50"

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
# ── Benutzer- und Pfad-Erkennung ─────────────────────────────────────────
# Priorität: SUDO_USER → erster User ≥1000 → root-Fallback (kein pi-Phantom)
if [ -n "$SUDO_USER" ] && id "$SUDO_USER" >/dev/null 2>&1; then
    REAL_USER="$SUDO_USER"
elif id "pidrive" >/dev/null 2>&1; then
    REAL_USER="pidrive"  # Dedizierter pidrive-Systemuser
elif id "pi" >/dev/null 2>&1; then
    REAL_USER="pi"       # Legacy Raspberry Pi
else
    REAL_USER=$(getent passwd | awk -F: '$3 >= 1000 && $3 < 65534 {print $1; exit}')
fi
# Kein brauchbarer Nicht-root-User → bewusst root nehmen (kein pi-Phantom)
if [ -z "$REAL_USER" ]; then
    REAL_USER="root"
    REAL_HOME="/root"
    INSTALL_DIR="/opt/pidrive"
else
    REAL_HOME=$(eval echo "~$REAL_USER")
    # Validierung: Home muss existieren oder anlegt werden können
    if [ ! -d "$REAL_HOME" ]; then
        mkdir -p "$REAL_HOME" 2>/dev/null || REAL_HOME="/root"
    fi
    INSTALL_DIR="$REAL_HOME/pidrive"
fi

# ── run_as_real_user(): sudo-unabhängiger User-Context-Wrapper ────────────
# Wird für git clone/pull und Musik-Verzeichnis benutzt.
# Reihenfolge: sudo → runuser → su → direkt (wenn REAL_USER==root)
run_as_real_user() {
    if [ "$REAL_USER" = "root" ] || [ "$EUID" -ne 0 ]; then
        "$@"
    elif command -v sudo >/dev/null 2>&1; then
        sudo -u "$REAL_USER" "$@"
    elif command -v runuser >/dev/null 2>&1; then
        runuser -u "$REAL_USER" -- "$@"
    elif command -v su >/dev/null 2>&1; then
        su - "$REAL_USER" -c "$(printf '%q ' "$@")"
    else
        "$@"  # Letzer Fallback: direkt
    fi
}

# ── Platform Detection ────────────────────────────────────────────────────
ARCH=$(uname -m)
IS_ARM=false
[[ "$ARCH" == arm* ]] || [[ "$ARCH" == aarch64 ]] && IS_ARM=true

IS_PI=false
grep -qi "Raspberry Pi" /proc/cpuinfo 2>/dev/null && IS_PI=true

IS_CONTAINER=false
# Robuste Container-Erkennung ohne D-Bus-Abhängigkeit
# systemd-detect-virt wird mit Timeout versucht, Fallback via /proc
if timeout 2 systemd-detect-virt --container -q 2>/dev/null; then
    IS_CONTAINER=true
elif [ -f /.dockerenv ] || [ -f /run/.containerenv ]; then
    IS_CONTAINER=true
elif grep -q "container=lxc\|container=docker\|container=podman" /proc/1/environ 2>/dev/null; then
    IS_CONTAINER=true
elif [ "$(cat /proc/1/comm 2>/dev/null)" != "systemd" ] && [ "$EUID" -eq 0 ] &&      [ ! -f /run/systemd/private/clean-shutdown ]; then
    # Kein echter systemd als PID1 → wahrscheinlich Container
    IS_CONTAINER=true
fi

HAS_DISPLAY=false
[ -e /sys/class/graphics/fb1 ] && HAS_DISPLAY=true

HAS_BT=false
command -v bluetoothctl &>/dev/null && bluetoothctl list 2>/dev/null | grep -q Controller && HAS_BT=true

HAS_SDR=false
lsusb 2>/dev/null | grep -qi "0bda:2838\|0bda:2832\|RTL2832\|RTL2838" && HAS_SDR=true

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

ok()   { echo -e "${GREEN}  ✓ ${1}${NC}"; }
info() { echo -e "${BLUE}  → ${1}${NC}"; }
warn() { echo -e "${YELLOW}  ⚠ ${1}${NC}"; }
err()  { echo -e "${RED}  ✗ ${1}${NC}"; }

echo -e "${BOLD}${BLUE}"
echo "╔═══════════════════════════════════════════╗"
printf "║  %-42s║\n" "PiDrive Installer v${PIDRIVE_VERSION}"
echo "║   github.com/MPunktBPunkt/pidrive         ║"
echo "╚═══════════════════════════════════════════╝"
echo -e "${NC}" 

if [ "$EUID" -ne 0 ]; then
    err "Bitte als root ausfuehren:  su -  dann  bash ~/pidrive/install.sh"
    err "  (oder: sudo bash install.sh  wenn sudo installiert ist)"
    exit 1
fi

# sudo verfuegbar? Auf Systemen ohne sudo direkt als root.
if command -v sudo &>/dev/null; then _SUDO="sudo"; else _SUDO=""; fi

# ══════════════════════════════════════════════════════════════
# SCHRITT 1: Service stoppen (falls aktiv)
# ══════════════════════════════════════════════════════════════
info "1/10 Laufenden Service stoppen..."
for SVC in pidrive_core pidrive; do  # display entfernt
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
    wpasupplicant rtl-sdr sox \
    python3-flask \
    python3-bluez \
    python3-dbus \
    python3-gi \
    2>/dev/null || true

apt-get install -y -qq welle.io 2>/dev/null || \
    warn "welle.io nicht verfuegbar — DAB+ spaeter installierbar"
if $IS_PI; then
    apt-get install -y -q dhcpcd5 2>/dev/null || true
fi
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
# RPi.GPIO nur auf ARM (nicht auf x86_64/Thin-Client)
if [[ "$(uname -m)" == arm* ]] || [[ "$(uname -m)" == aarch64 ]]; then
    _pip_install RPi.GPIO
    GPIO_INSTALLED=true
else
    GPIO_INSTALLED=false
fi
# v0.9.4: numpy für spectrum.py Prototyp
apt-get install -y python3-numpy -q 2>/dev/null || _pip_install numpy
if [ "$GPIO_INSTALLED" = "true" ]; then
    ok "Python-Pakete installiert (mutagen, RPi.GPIO, numpy)"
else
    ok "Python-Pakete installiert (mutagen, numpy) — RPi.GPIO uebersprungen (kein ARM)"
fi

# ══════════════════════════════════════════════════════════════
# SCHRITT 3: Repository klonen / aktualisieren
# ══════════════════════════════════════════════════════════════
info "3/10 Repository von GitHub..."
# Diagnose: Zeige INSTALL_DIR und Status
info "  INSTALL_DIR: $INSTALL_DIR"
info "  REAL_USER:   $REAL_USER"
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
        run_as_real_user git -C "$INSTALL_DIR" stash 2>/dev/null || true
        info "settings.json gesichert (git stash)"
    fi
    set +e  # git pull darf nicht den Installer abbrechen
    run_as_real_user git -C "$INSTALL_DIR" pull
    _git_rc=$?
    set -e
    if [ $_git_rc -ne 0 ]; then
        warn "git pull fehlgeschlagen (rc=$_git_rc) — versuche Reset und erneuten Pull"
        run_as_real_user git -C "$INSTALL_DIR" fetch origin main 2>/dev/null || true
        run_as_real_user git -C "$INSTALL_DIR" reset --hard origin/main 2>/dev/null || true
    fi
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
    set +e
    run_as_real_user git clone "$REPO_URL" "$INSTALL_DIR"
    _clone_rc=$?
    set -e
    if [ $_clone_rc -ne 0 ]; then
        err "git clone fehlgeschlagen — Netzwerk/DNS pruefen"
        err "  $REPO_URL nach $INSTALL_DIR"
        exit 1
    fi
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
[ ! -d "$MUSIK_DIR" ] && run_as_real_user mkdir -p "$MUSIK_DIR"
ok "Musik-Verzeichnis: $MUSIK_DIR"

mkdir -p "$LOG_DIR"
chown "$REAL_USER:$REAL_USER" "$LOG_DIR"
ok "Log-Verzeichnis: $LOG_DIR"

  # v0.10.55: tmpfiles.d — IPC-Dateien 0666 damit webui (pi) CMD_FILE schreiben kann
  cat > /etc/tmpfiles.d/pidrive.conf << 'TMPEOF'
# PiDrive IPC: world-writable damit webui (pi) CMD_FILE schreiben kann
# Trigger: nur pidrive-Gruppe darf schreiben (nicht world-write)
f /tmp/pidrive_cmd          0660 root pidrive -
# Status/Menu: world-readable für Diagnose
f /tmp/pidrive_status.json  0664 root pidrive -
f /tmp/pidrive_menu.json    0664 root pidrive -
f /tmp/pidrive_list.json    0664 root pidrive -
TMPEOF
  # Sofort anwenden auf bestehende Dateien
  chmod 666 /tmp/pidrive_cmd 2>/dev/null || true
  chmod 666 /tmp/pidrive_menu.json 2>/dev/null || true
  chmod 666 /tmp/pidrive_status.json 2>/dev/null || true
  ok "tmpfiles.d: IPC-Dateien konfiguriert (cmd=0660:pidrive, status=0664)"

# ══════════════════════════════════════════════════════════════
# SCHRITT 5: /boot/config.txt
# ══════════════════════════════════════════════════════════════
info "5/10 /boot/config.txt konfigurieren..."
if ! $IS_PI; then
    ok "/boot/config.txt: uebersprungen (kein Raspberry Pi)"
else
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

# fbcon=nodeconfig: nur wenn SPI-Display (fb1) vorhanden oder bereits konfiguriert
if [ -e /sys/class/graphics/fb1 ] || grep -q "fbcon=nodeconfig" "$CMDLINE_TXT" 2>/dev/null; then
    if [ -f "$CMDLINE_TXT" ] && ! grep -q "fbcon=nodeconfig" "$CMDLINE_TXT"; then
        sed -i 's/$/ fbcon=nodeconfig/' "$CMDLINE_TXT"
        ok "cmdline.txt: fbcon=nodeconfig gesetzt (fb1-Display erkannt)"
    else
        ok "cmdline.txt: fbcon=nodeconfig bereits vorhanden"
    fi
else
    ok "cmdline.txt: kein SPI-Display erkannt — fbcon-Konfiguration uebersprungen"
fi
ok "/boot/config.txt konfiguriert"
fi  # IS_PI boot config

# ══════════════════════════════════════════════════════════════
# SCHRITT 6: rc.local (Boot-Vorbereitung)
# ══════════════════════════════════════════════════════════════
info "6/10 rc.local konfigurieren..."
RC="/etc/rc.local"
# v0.6.0: minimal rc.local - kein fbcp, kein chvt, kein tty3
# Immer neu schreiben fuer saubere Migration
cat > "$RC" << 'RC_HEREDOC_END'
#!/bin/sh -e
# rc.local - PiDrive
# vtcon1 unbind: nur wenn SPI-Display (fb1) vorhanden
if [ -e /sys/class/graphics/fb1 ]; then
echo 0 > /sys/class/vtconsole/vtcon1/bind 2>/dev/null || true
echo 0 > /sys/class/graphics/fbcon/cursor_blink 2>/dev/null || true
fi
exit 0
RC_HEREDOC_END
chmod +x "$RC"
ok "rc.local: konfiguriert (vtcon1 unbind nur wenn fb1 vorhanden)"

info "7/10 System-Konfiguration..."
# tty3 udev-Regel nicht mehr noetig (kein TIOCSCTTY in v0.6.0)
rm -f /etc/udev/rules.d/99-pidrive-tty.rules 2>/dev/null || true
udevadm control --reload-rules 2>/dev/null || true
ok "Alte tty3 udev-Regel entfernt"

# ══════════════════════════════════════════════════════════════

# ── D-Bus Policy für MPRIS2 (SystemBus Ownership) ───────────────────────────
if [ -f "$INSTALL_DIR/systemd/pidrive-mpris2.conf" ]; then
    cp "$INSTALL_DIR/systemd/pidrive-mpris2.conf" /etc/dbus-1/system.d/pidrive-mpris2.conf
    chmod 644 /etc/dbus-1/system.d/pidrive-mpris2.conf
    echo "  ✓ D-Bus Policy: MPRIS2 auf SystemBus erlaubt (pidrive-mpris2.conf)"
    systemctl reload dbus 2>/dev/null || true
fi

# ── pidrivectl CLI ──────────────────────────────────────────────────────────
info "pidrivectl CLI installieren"
# CLI-Einstiegspunkt ausführbar machen (vor Permission-Fixer geschützt)
chmod +x "$INSTALL_DIR/pidrive/cli/cli.py"
# Wrapper-Script: sudo-fähig, kein PATH-Problem, kein Shebang-Problem
# Alten Symlink ZUERST entfernen (sonst überschreibt cat > die Zieldatei)
rm -f /usr/local/bin/pidrivectl /usr/bin/pidrivectl
# Wrapper als echte Datei anlegen (kein Symlink, kein .py)
cat > /usr/local/bin/pidrivectl << WRAPPER_END
#!/bin/bash
exec python3 ${INSTALL_DIR}/pidrive/cli/cli.py "\$@"
WRAPPER_END
chmod +x /usr/local/bin/pidrivectl
# Auch in /usr/bin damit sudo es findet
ln -sf /usr/local/bin/pidrivectl /usr/bin/pidrivectl 2>/dev/null || true
echo "  ✓ pidrivectl → /usr/local/bin/pidrivectl + /usr/bin/pidrivectl"
if python3 "$INSTALL_DIR/pidrive/cli/cli.py" --help >/dev/null 2>&1; then
    echo "  ✓ pidrivectl aufrufbar (python3 OK)"
else
    echo "  ⚠ pidrivectl Test fehlgeschlagen — CLI-Pfad prüfen"
fi

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
sed -i "s|/home/pi/pidrive|${INSTALL_DIR}|g" "$SERVICE_DIR/pidrive_core.service"
sed -i "s|/home/pi/|${REAL_HOME}/|g" "$SERVICE_DIR/pidrive_core.service"

# pidrive_display.service: entfernt v0.11.50

# Web Service (IMMER aktualisieren — Ordering-Cycle-Fix!)
if [ -f "$INSTALL_DIR/systemd/pidrive_web.service" ]; then
    cp "$INSTALL_DIR/systemd/pidrive_web.service" "$SERVICE_DIR/pidrive_web.service"
    sed -i "s|/home/pi/pidrive|${INSTALL_DIR}|g" "$SERVICE_DIR/pidrive_web.service"
sed -i "s|/home/pi/|${REAL_HOME}/|g" "$SERVICE_DIR/pidrive_web.service"
    sed -i "s|PIDRIVE_REAL_USER|${REAL_USER}|g" "$SERVICE_DIR/pidrive_web.service"
    ok "pidrive_web.service: User=${REAL_USER}"
fi

# AVRCP Service
if [ -f "$INSTALL_DIR/systemd/pidrive_avrcp.service" ]; then
    cp "$INSTALL_DIR/systemd/pidrive_avrcp.service" "$SERVICE_DIR/pidrive_avrcp.service"
    sed -i "s|/home/pi/pidrive|${INSTALL_DIR}|g" "$SERVICE_DIR/pidrive_avrcp.service"
sed -i "s|/home/pi/|${REAL_HOME}/|g" "$SERVICE_DIR/pidrive_avrcp.service"
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
systemctl enable pidrive_core rfkill-unblock 2>/dev/null || true
ok "Dienste aktiviert (pidrive_core, pidrive_web, rfkill-unblock)"
[ -f "$SERVICE_DIR/pidrive_web.service" ]   && systemctl enable pidrive_web   2>/dev/null || true
[ -f "$SERVICE_DIR/pidrive_avrcp.service" ] && systemctl enable pidrive_avrcp 2>/dev/null || true

# SSH
systemctl enable ssh 2>/dev/null && systemctl start ssh 2>/dev/null || true
ok "SSH aktiviert"

# sudoers nur schreiben wenn sudo installiert
if command -v sudo >/dev/null 2>&1; then
    mkdir -p /etc/sudoers.d
    # v0.10.55: sudoers für PiDrive — NOPASSWD für spezifische Wartungsbefehle
    # Pi OS Bookworm fragt bei jedem sudo nach Passwort (kein Session-Timeout mehr)
    # Sudoers dynamisch mit REAL_USER
    cat > /etc/sudoers.d/pidrive << SUDOEOF
# PiDrive: ausgewaehlte Befehle ohne Passwort fuer Benutzer ${REAL_USER}
${REAL_USER} ALL=(ALL) NOPASSWD: /bin/systemctl restart pidrive_core
${REAL_USER} ALL=(ALL) NOPASSWD: /bin/systemctl restart pidrive_web
${REAL_USER} ALL=(ALL) NOPASSWD: /bin/systemctl restart pulseaudio
${REAL_USER} ALL=(ALL) NOPASSWD: /bin/systemctl status pidrive_core
${REAL_USER} ALL=(ALL) NOPASSWD: /bin/systemctl status pulseaudio
${REAL_USER} ALL=(ALL) NOPASSWD: /bin/journalctl
${REAL_USER} ALL=(ALL) NOPASSWD: /sbin/reboot
${REAL_USER} ALL=(ALL) NOPASSWD: /sbin/poweroff
${REAL_USER} ALL=(ALL) NOPASSWD: /sbin/shutdown
SUDOEOF
    chmod 440 /etc/sudoers.d/pidrive
else
    ok "sudoers: sudo nicht installiert (apt-get install -y sudo)"
fi  # sudo check
ok "sudoers: NOPASSWD für pidrive-Wartungsbefehle"

# ══════════════════════════════════════════════════════════════
# SCHRITT 9: Berechtigungen
# ══════════════════════════════════════════════════════════════
info "9/10 Berechtigungen setzen..."
# pidrive-Gruppe anlegen (IPC-Schreibrecht + Bedienung)
groupadd -f pidrive 2>/dev/null || true
usermod -a -G pidrive "$REAL_USER" 2>/dev/null || true
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

# Raspotify installieren (Frisch-Install oder fehlerhafter Vorversuch)
# Spotify Connect: Raspotify (ARM) oder librespot direkt (x86)
if ! command -v librespot &>/dev/null && ! dpkg -l raspotify 2>/dev/null | grep -q "^ii"; then
    if $IS_ARM; then
        info "Raspotify installieren (ARM)..."
        if curl -sL https://dtcooper.github.io/raspotify/install.sh | sh 2>/dev/null; then
            command -v librespot &>/dev/null && ok "Raspotify/librespot installiert" ||                 warn "Raspotify-Script lief — librespot nicht gefunden (manuell pruefen)"
        else
            warn "Raspotify-Installation fehlgeschlagen"
        fi
    else
        info "librespot installieren (x86)..."
        _LB_INSTALLED=false

        # Versuch 1: Debian-Repo (Bullseye/Bookworm, fehlt in Trixie)
        if apt-get install -y librespot -q 2>/dev/null && command -v librespot &>/dev/null; then
            ok "librespot installiert via apt"
            _LB_INSTALLED=true
        fi

        # Versuch 2: GitHub Binary (Fallback fuer Trixie/neuere Distros)
        if ! $_LB_INSTALLED; then
            info "librespot GitHub Binary laden..."
            _LB_TMP=$(mktemp -d)
            _LB_OK=false
            # Versuche verschiedene Release-Pfade (GitHub naming variiert)
            for _LB_URL in \
                "https://github.com/librespot-org/librespot/releases/latest/download/librespot-linux-amd64.tar.gz" \
                "https://github.com/librespot-org/librespot/releases/latest/download/librespot-linux-x86_64.tar.gz"; do
                if curl -sfL --connect-timeout 15 "$_LB_URL" \
                        -o "$_LB_TMP/librespot.tar.gz" 2>/dev/null; then
                    tar xzf "$_LB_TMP/librespot.tar.gz" -C "$_LB_TMP" 2>/dev/null || true
                    # Binary suchen (direkt oder in Unterverzeichnis)
                    _LB_BIN=$(find "$_LB_TMP" -name "librespot" -type f 2>/dev/null | head -1)
                    if [ -n "$_LB_BIN" ]; then
                        install -m 755 "$_LB_BIN" /usr/local/bin/librespot
                        command -v librespot &>/dev/null && _LB_OK=true && break
                    fi
                fi
            done
            rm -rf "$_LB_TMP"
            if $_LB_OK; then
                ok "librespot installiert (GitHub Binary)"
                _LB_INSTALLED=true
            else
                warn "librespot GitHub Download fehlgeschlagen"
                warn "  Manuell nach Install (einmalig):"
                warn "    curl -sfL https://github.com/librespot-org/librespot/releases/latest/download/librespot-linux-amd64.tar.gz | tar xz"
                warn "    ${_SUDO} install -m755 librespot /usr/local/bin/"
            fi
        fi

        # Versuch 3: cargo (falls Rust installiert)
        if ! $_LB_INSTALLED && command -v cargo &>/dev/null; then
            info "librespot via cargo installieren (dauert 2-5 Min)..."
            if cargo install librespot 2>/dev/null && command -v librespot &>/dev/null; then
                ok "librespot installiert via cargo"
                _LB_INSTALLED=true
            fi
        fi
    fi
else
    ok "librespot/Raspotify bereits installiert"
fi
# Spotify OAuth Credentials prüfen
if command -v librespot &>/dev/null; then
    if [ -f /var/cache/librespot/credentials.json ]; then
        ok "Spotify OAuth: Token vorhanden"
    else
        warn "Spotify OAuth: noch nicht eingerichtet"
        warn "  → Nach Install: pidrivectl system spotify-oauth"
    fi
fi
# ══════════════════════════════════════════════════════════════
# Audio-Konfiguration: ALSA + PulseAudio System-Mode (v0.10.55)
# Läuft IMMER — unabhängig von Raspotify-Installation
# ══════════════════════════════════════════════════════════════
# ALSA-Karten dynamisch erkennen (Pi: Card 0=HDMI, Card 1=Klinke; andere: variabel)
ALSA_HEADPHONE_CARD=""
ALSA_HDMI_CARD=""
while IFS= read -r line; do
    [[ "$line" =~ ^card\ ([0-9]+).*[Hh]eadphone ]] && ALSA_HEADPHONE_CARD="${BASH_REMATCH[1]}"
    [[ "$line" =~ ^card\ ([0-9]+).*[Hh][Dd][Mm][Ii] ]] && ALSA_HDMI_CARD="${BASH_REMATCH[1]}"
done < <(aplay -l 2>/dev/null)
# Fallback: Pi-Standard
[ -z "$ALSA_HEADPHONE_CARD" ] && $IS_PI && ALSA_HEADPHONE_CARD=1
[ -z "$ALSA_HEADPHONE_CARD" ] && ALSA_HEADPHONE_CARD=0  # Fallback: erste Karte

if [ -n "$ALSA_HEADPHONE_CARD" ]; then
    cat > /etc/asound.conf << ASOUNDEOF
# PiDrive: ALSA Default auf Klinken-Ausgang (Card ${ALSA_HEADPHONE_CARD})
defaults.pcm.card ${ALSA_HEADPHONE_CARD}
defaults.ctl.card ${ALSA_HEADPHONE_CARD}
defaults.pcm.device 0
ASOUNDEOF
    ok "ALSA: /etc/asound.conf geschrieben (Card ${ALSA_HEADPHONE_CARD} = Klinke)"
else
    ok "ALSA: kein Headphone-Ausgang erkannt — /etc/asound.conf uebersprungen"
fi

# Klinke via amixer aktivieren (nur wenn Hardware vorhanden)
if ! $IS_CONTAINER && command -v amixer >/dev/null 2>&1; then
    KLINKE_CARD=$(aplay -l 2>/dev/null | grep -i "headphones" | head -1 | awk '{print $2}' | tr -d ':')
    [ -z "$KLINKE_CARD" ] && $IS_PI && KLINKE_CARD=1
    if [ -n "$KLINKE_CARD" ]; then
        amixer -q -c "$KLINKE_CARD" sset 'PCM' 85% unmute 2>/dev/null \
            && ok "Pi Audio: Klinke aktiviert (card $KLINKE_CARD PCM unmute 85%)" \
            || ok "Pi Audio: amixer PCM card $KLINKE_CARD nicht gefunden"
    fi
else
    ok "Pi Audio: amixer uebersprungen (Container oder amixer nicht verfuegbar)"
fi

# system.pa: plattformadaptiv schreiben
mkdir -p /etc/pulse
if $IS_CONTAINER; then
    # Im Container: minimales system.pa (kein ALSA, aber IPC/Basis)
    mkdir -p /etc/pulse
    cat > /etc/pulse/system.pa << CONTAINER_PA_END
# PiDrive system.pa — Container/Dev-Modus (kein echtes Audio-Device)
.fail
load-module module-device-restore
load-module module-null-sink sink_name=pidrive_null
set-default-sink pidrive_null
load-module module-native-protocol-unix auth-anonymous=1
CONTAINER_PA_END
    ok "system.pa: Container-Modus (Null-Sink fuer Entwicklung)"
else
    # Ermittle verfuegbare ALSA-Karten dynamisch
    PA_CARD_LINES=""
    PA_DEFAULT_SINK=""
    while IFS= read -r card_line; do
        CARD_NUM=$(echo "$card_line" | grep -oP "(?<=card )\d+" || echo "")
        [ -n "$CARD_NUM" ] && PA_CARD_LINES="${PA_CARD_LINES}load-module module-alsa-card device_id=${CARD_NUM}
"
    done < <(aplay -l 2>/dev/null | grep "^card " || echo "card 0:")
    # Fallback wenn keine Karten erkannt
    [ -z "$PA_CARD_LINES" ] && PA_CARD_LINES="load-module module-alsa-sink
"

    # Default Sink: auf Pi Klinke (Card 1), sonst auto
    if $IS_PI && [ -n "$ALSA_HEADPHONE_CARD" ]; then
        PA_DEFAULT_SINK="set-default-sink alsa_output.${ALSA_HEADPHONE_CARD}.stereo-fallback"
    fi

    cat > /etc/pulse/system.pa << SYSTEMPA_END
# PiDrive system.pa — $(date +%Y-%m-%d)
# Plattform: ${ARCH}$(${IS_PI} && echo " (Pi)")$(${IS_CONTAINER} && echo " (Container)")
.fail

load-module module-device-restore
load-module module-stream-restore
load-module module-card-restore

# ALSA Hardware (automatisch erkannt)
$(echo -e "$PA_CARD_LINES")
# Bluetooth A2DP
load-module module-bluetooth-discover
load-module module-bluetooth-policy

# Null-Sink als Fallback (z.B. wenn kein BT verbunden — verhindert librespot-Crash)
load-module module-null-sink sink_name=pidrive_null sink_properties=device.description=PiDrive-Fallback

# D-Bus + IPC
load-module module-dbus-protocol
load-module module-native-protocol-unix auth-anonymous=1

$([ -n "$PA_DEFAULT_SINK" ] && echo "$PA_DEFAULT_SINK")
SYSTEMPA_END
    ok "system.pa: geschrieben (${ARCH}$(${IS_PI} && echo ", Pi-Klinke" || echo ", generisch"))"
fi

# v0.9.14: pulse-access Gruppe
groupadd -f pulse-access 2>/dev/null || true
usermod -aG pulse-access root 2>/dev/null || true
usermod -aG pulse-access "$REAL_USER" 2>/dev/null || true
ok "pulse-access Gruppe: root + $REAL_USER hinzugefügt"

# v0.10.55: PulseAudio System-Service einrichten (Bookworm-kompatibel)
# Bookworm installiert PA als User-Session-Service → umschalten auf System-Mode
# Schritt 1: User-Session PA für ALLE User deaktivieren + laufende Instanz töten
systemctl --global disable pulseaudio.socket pulseaudio.service 2>/dev/null || true
# User-PA stoppen/maskieren (nur auf echtem Host mit User-Session)
if ! $IS_CONTAINER && [ "$REAL_USER" != "root" ]; then
    UID_VAL=$(id -u "$REAL_USER" 2>/dev/null || echo 1000)
    XDG_RT="/run/user/${UID_VAL}"
    if command -v runuser >/dev/null 2>&1; then
        runuser -u "$REAL_USER" -- env XDG_RUNTIME_DIR="$XDG_RT"             systemctl --user stop pulseaudio.service pulseaudio.socket 2>/dev/null || true
        runuser -u "$REAL_USER" -- env XDG_RUNTIME_DIR="$XDG_RT"             systemctl --user mask pulseaudio.socket 2>/dev/null || true
        runuser -u "$REAL_USER" -- env XDG_RUNTIME_DIR="$XDG_RT"             systemctl --user mask pulseaudio.service 2>/dev/null || true
    elif command -v sudo >/dev/null 2>&1; then
        sudo -u "$REAL_USER" XDG_RUNTIME_DIR="$XDG_RT"             systemctl --user stop pulseaudio.service pulseaudio.socket 2>/dev/null || true
        sudo -u "$REAL_USER" XDG_RUNTIME_DIR="$XDG_RT"             systemctl --user mask pulseaudio.socket 2>/dev/null || true
        sudo -u "$REAL_USER" XDG_RUNTIME_DIR="$XDG_RT"             systemctl --user mask pulseaudio.service 2>/dev/null || true
    fi
fi
runuser -u "$REAL_USER" -- XDG_RUNTIME_DIR="/run/user/$(id -u $REAL_USER 2>/dev/null || echo 1000)"       systemctl --user mask pulseaudio.socket 2>/dev/null || true
runuser -u "$REAL_USER" -- XDG_RUNTIME_DIR="/run/user/$(id -u $REAL_USER 2>/dev/null || echo 1000)"       systemctl --user disable pulseaudio.service 2>/dev/null || true
# User-PA-Socket null-masken: ln -sf /dev/null verhindert Socket-Aktivierung zuverlässig
mkdir -p /etc/systemd/user
ln -sf /dev/null /etc/systemd/user/pulseaudio.socket
ln -sf /dev/null /etc/systemd/user/pulseaudio.service
ok "User-PA Socket + Service null-maskiert"
# PipeWire-Konflikt erkennen: PipeWire + System-PulseAudio konkurrieren um den PA-Socket
if systemctl --user is-active pipewire-pulse &>/dev/null 2>&1    || pgrep -x pipewire-pulse &>/dev/null 2>&1    || pgrep -x pipewire &>/dev/null 2>&1; then
    warn "PipeWire laeuft gleichzeitig mit System-PulseAudio!"
    warn "  → Das verursacht: Keine Sinks, Default Sink (null), Audio-Konflikte"
    warn "  → Fix: ${_SUDO} bash ~/pidrive/pidrive_car_only_cleanup.sh && ${_SUDO} reboot"
    warn "  → (deaktiviert PipeWire, behaelt nur System-PulseAudio)"
else
    : # Kein PipeWire-Konflikt
fi

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
UMask=0000
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
# PA Unit-Datei verifizieren
if [ -f /etc/systemd/system/pulseaudio.service ]; then
  ok "PA Unit-Datei: /etc/systemd/system/pulseaudio.service vorhanden ✓"
else
  warn "PA Unit-Datei FEHLT — systemctl kann pulseaudio.service nicht finden!"
  warn "  → Installer-Fehler: PA-Setup wurde nicht korrekt abgeschlossen"
fi
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
  warn "  → Nach Reboot: ${_SUDO} systemctl status pulseaudio"
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
# WebUI-URL anzeigen
_PI_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
if [ -n "$_PI_IP" ]; then
    echo ""
    echo "  ┌─────────────────────────────────────┐"
    printf "  │  🌐  WebUI: http://%-17s│\n" "${_PI_IP}:8080"
    echo "  │  CLI:       pidrivectl status        │"
    echo "  └─────────────────────────────────────┘"
    echo ""
fi
# AVRCP Service starten
if [ -f "$SERVICE_DIR/pidrive_avrcp.service" ]; then
  systemctl restart pidrive_avrcp 2>/dev/null || true
  ok "pidrive_avrcp.service gestartet"
fi
  # Verify: PA unit file tatsächlich geschrieben?
  if [ -f /etc/systemd/system/pulseaudio.service ]; then
    ok "PA Unit-Datei: /etc/systemd/system/pulseaudio.service vorhanden ✓"
  else
    warn "PA Unit-Datei FEHLT — systemctl kann pulseaudio.service nicht finden!"
    warn "  → ${_SUDO} bash ~/pidrive/pidrive_car_only_cleanup.sh && ${_SUDO} reboot"
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

fi

# librespot.service fuer x86 (falls kein raspotify vorhanden)
if command -v librespot &>/dev/null && [ ! -f /etc/raspotify/conf ]; then
    if [ ! -f /etc/systemd/system/librespot.service ]; then
        info "librespot.service anlegen (x86 PulseAudio)..."
        cat > /etc/systemd/system/librespot.service << 'LSEOF'
[Unit]
Description=PiDrive Spotify Connect (librespot)
After=network-online.target pulseaudio.service
Wants=network-online.target

[Service]
User=PIDRIVE_REAL_USER_PLACEHOLDER
Environment=PULSE_SERVER=unix:/var/run/pulse/native
ExecStart=/usr/local/bin/librespot \
  --name PiDrive \
  --device-type automobile \
  --system-cache /var/cache/librespot
  --onevent /usr/local/bin/spotify_event.sh
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
LSEOF
        # REAL_USER in Service ersetzen
        sed -i "s/PIDRIVE_REAL_USER_PLACEHOLDER/$REAL_USER/g" \
            /etc/systemd/system/librespot.service
        systemctl daemon-reload
        systemctl enable librespot 2>/dev/null || true
        ok "librespot.service eingerichtet (x86, PulseAudio)"
    else
        ok "librespot.service bereits vorhanden"
    fi
elif command -v librespot &>/dev/null && [ -f /etc/raspotify/conf ]; then
    : # ARM mit raspotify — bereits weiter oben behandelt
fi

# ── Zeitzone und fake-hwclock ──────────────────────────────────────────────
info "Zeitzone und Uhr..."

# Zeitzone Deutschland
timedatectl set-timezone Europe/Berlin 2>/dev/null ||     ln -sf /usr/share/zoneinfo/Europe/Berlin /etc/localtime 2>/dev/null || true
ok "Zeitzone: Europe/Berlin"

# fake-hwclock: Pi merkt sich letzte bekannte Zeit beim Shutdown
# Verhindert apt "Datei noch nicht gueltig" nach Stromunterbrechung
if $IS_PI && ! $IS_CONTAINER; then
    if ! dpkg -l fake-hwclock 2>/dev/null | grep -q "^ii"; then
        apt-get install -y -qq fake-hwclock 2>/dev/null || true
    fi
    fake-hwclock save 2>/dev/null && ok "fake-hwclock: aktuelle Zeit gespeichert" || true
else
    ok "Uhr: systemd-timesyncd (fake-hwclock uebersprungen)"
fi

# ── RTL-SDR Check ─────────────────────────────────────────────────────────

# DVB-T Treiber blacklisten (blockiert sonst RTL-SDR für rtl_fm/welle-cli)
# udev-Regel fuer RTL-SDR (Zugriff fuer plugdev-Gruppe)
UDEV_RTL="/etc/udev/rules.d/10-rtlsdr.rules"
if [ ! -f "$UDEV_RTL" ]; then
    cat > "$UDEV_RTL" << 'UDEVEOF'
# PiDrive: RTL-SDR Zugriff fuer Gruppe plugdev
SUBSYSTEMS=="usb", ATTRS{idVendor}=="0bda", ATTRS{idProduct}=="2838", GROUP="plugdev", MODE="0664"
SUBSYSTEMS=="usb", ATTRS{idVendor}=="0bda", ATTRS{idProduct}=="2832", GROUP="plugdev", MODE="0664"
UDEVEOF
    udevadm control --reload-rules 2>/dev/null || true
    ok "udev: RTL-SDR Regel angelegt (plugdev-Gruppe)"
else
    ok "udev: RTL-SDR Regel bereits vorhanden"
fi
usermod -a -G plugdev "$REAL_USER" 2>/dev/null || true

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
    warn "rtl_fm nicht installiert -> ${_SUDO} apt install rtl-sdr"
fi
if which rtl_sdr >/dev/null 2>&1; then
    ok "rtl_sdr vorhanden (Spectrum/FFT verfuegbar)"
else
    warn "rtl_sdr nicht gefunden — Spectrum/FFT nicht verfuegbar (${_SUDO} apt install rtl-sdr)"
fi
if which welle-cli >/dev/null 2>&1; then
    ok "welle-cli vorhanden (DAB+)"
else
    warn "welle-cli nicht installiert -> ${_SUDO} apt install welle.io"
fi
# DVB-Treiber Status
if lsmod 2>/dev/null | grep -qE "dvb_usb_rtl28xxu|dvb_core"; then
    warn "DVB-Treiber noch geladen — RTL-SDR erst nach Reboot nutzbar"
else
    ok "Kein blockierender DVB-Treiber"
fi
# Unterspannung
# vcgencmd nur auf Pi verfuegbar
if $IS_PI; then
    _throttled=$(vcgencmd get_throttled 2>/dev/null || echo "n/a")
else
    _throttled="n/a (kein Pi)"
fi
info "Stromversorgung: $_throttled"
if echo "$_throttled" | grep -qE "0x[0-9a-f]*[1-9][0-9a-f]*"; then
    warn "Unterspannung erkannt ($_throttled) — 5V/3A Netzteil empfohlen"
    dmesg -T 2>/dev/null | grep -iE "under-voltage|Undervoltage" | tail -3 || true
fi

# ── Syntax-Check + Shell-Code-Erkennung vor Service-Start ──────────────
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

# Shell-Code in .py-Dateien erkennen (verhindert Symlink-Follow-Bug)
SHELL_IN_PY=$(find "$INSTALL_DIR/pidrive" -name "*.py" -exec     grep -lP "^exec python3|^#!/bin/bash|^cat >" {} \; 2>/dev/null | head -3)
if [ -z "$SHELL_IN_PY" ]; then
    ok "Shell-Code-Check OK"
else
    err "Shell-Code in .py-Datei(en) gefunden:"
    # Auto-Restore aus Git
    for f in $SHELL_IN_PY; do
        warn "  Stelle wieder her: $f"
        rel="${f#$INSTALL_DIR/}"
        git -C "$INSTALL_DIR" checkout HEAD -- "$rel" 2>/dev/null &&             ok "  Restored: $rel" || err "  Konnte nicht wiederhergestellt werden: $rel"
    done
fi

# Alt-Importe pruefen (ui/trigger/launcher wurden als Dead-Code entfernt)
BAD_IMP=$(grep -RInE '^[[:space:]]*(from[[:space:]]+ui[[:space:]]+import|import[[:space:]]+ui[[:space:]]|from[[:space:]]+launcher[[:space:]]+import)' \
    "$INSTALL_DIR/pidrive" --include="*.py" --exclude-dir="__pycache__" 2>/dev/null || true)
BAD_IMP2=$(grep -RInE '^[[:space:]]*(import[[:space:]]+td_nav|import[[:space:]]+td_radio|import[[:space:]]+td_scanner|import[[:space:]]+td_hardware|import[[:space:]]+td_system)\b' \
    "$INSTALL_DIR/pidrive" --include="*.py" --exclude-dir="__pycache__" 2>/dev/null || true)
BAD_IMP="${BAD_IMP}${BAD_IMP2}"
if [ -n "$BAD_IMP" ]; then
    err "Veraltete Imports gefunden (bitte melden):"
    echo "$BAD_IMP" | head -5
    exit 1
else
    ok "Alt-Import-Check OK"
fi

# Import-Smoke-Test: prueft den echten Startpfad von main_core
if ! (cd "$INSTALL_DIR/pidrive" && python3 -c "
import sys; sys.path.insert(0, '.')
import importlib, sys as _sys
_mods = [
    'log','ipc','settings','status','modules.source_state',
    'modules.audio','modules.wifi','modules.bluetooth','modules.system',
    'modules.webradio','modules.dab','modules.fm','modules.scanner',
    'modules.update','modules.favorites','modules.core_callbacks',
    'trigger.td_hardware','trigger.td_nav','trigger.td_radio',
    'trigger.td_scanner','trigger.td_system','trigger.trigger_dispatcher',
    'menu.menu_model','menu.menu_builder','menu.menu_state',
    'cli.cli','webui','main_core',
]
_errs = []
for _m in _mods:
    try: importlib.import_module(_m)
    except Exception as e: _errs.append(f'{_m}: {e}'); print(f'  ✗ {_m}: {e}', file=_sys.stderr)
if _errs: sys.exit(1)
"
  python3 -c "import webui"
  # Neue Zielpfade (v0.10.55+)
  python3 -c "import cli.cli" 2>/dev/null && echo "  ✓ cli.cli" || echo "  ⚠ cli.cli nicht importierbar"
  python3 -c "import cli.service" 2>/dev/null && echo "  ✓ cli.service" || echo "  ⚠ cli.service"
  python3 -c "from web.app import app" 2>/dev/null && echo "  ✓ web.app" || echo "  ⚠ web.app"
  python3 -c "import web.shared" 2>/dev/null && echo "  ✓ web.shared" || echo "  ⚠ web.shared"
  python3 -c "import web.api.routes_audio" 2>/dev/null && echo "  ✓ web.api.routes_audio" || echo "  ⚠ web.api.routes_audio" 2>/dev/null); then
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

# Runtime-Stabilitaetsfenster: 15s beobachten (Review v0.11.50)
_CORE_PID=$(systemctl show pidrive_core --property=MainPID --value 2>/dev/null | tr -d ' ')
_RESTART0=$(systemctl show pidrive_core --property=NRestarts --value 2>/dev/null | grep -oE '[0-9]+' | head -1)
printf "  → Stabilitaetspruefung (15s)..."
sleep 15
_RESTART1=$(systemctl show pidrive_core --property=NRestarts --value 2>/dev/null | grep -oE '[0-9]+' | head -1)
_ACTIVE=$(systemctl is-active pidrive_core 2>/dev/null)
_TRACEBACK=$(journalctl -u pidrive_core --since "30 seconds ago" --no-pager -q 2>/dev/null   | grep -c "Traceback\|UnboundLocalError\|ImportError\|ModuleNotFoundError" 2>/dev/null   | tr -dc '0-9' || echo 0)
_TRACEBACK=${_TRACEBACK:-0}
_STATUS_AGE=$(python3 -c "import os,time; f='/tmp/pidrive_status.json'; print(int(time.time()-os.path.getmtime(f))) if os.path.exists(f) else print(9999)" 2>/dev/null | tr -dc '0-9' || echo 9999)
_STATUS_AGE=${_STATUS_AGE:-9999}
echo ""
if [ "$_ACTIVE" != "active" ]; then
  err "KRITISCH: pidrive_core nach 15s nicht mehr aktiv — Installation fehlgeschlagen"
  err "  journalctl -u pidrive_core -n 20"
  exit 1
elif [ "${_RESTART1:-0}" -gt "${_RESTART0:-0}" ] 2>/dev/null; then
  err "KRITISCH: Restart-Loop erkannt! (${_RESTART0} -> ${_RESTART1})"
  err "  journalctl -u pidrive_core -n 20"
  exit 1
elif [ "${_TRACEBACK:-0}" -gt 0 ]; then
  err "KRITISCH: Python-Traceback im Core-Log (${_TRACEBACK}x)"
  journalctl -u pidrive_core --since "30 seconds ago" --no-pager -q 2>/dev/null | grep -m5 "Error\|Traceback" || true
  exit 1
elif [ "${_STATUS_AGE:-9999}" -gt 20 ]; then
  warn "Core laeuft, aber status.json veraltet (${_STATUS_AGE}s)"
else
  ok "Stabilitaetspruefung OK (15s stabil, kein Restart, kein Traceback)"
fi

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
echo -e "  1. ${YELLOW}Spotify OAuth (einmalig, nach librespot-Installation):${NC}"
echo -e "     ${_SUDO} systemctl stop librespot raspotify 2>/dev/null; true"
echo -e "     /usr/local/bin/librespot --name PiDrive --enable-oauth \\"
echo -e "       --system-cache /var/cache/librespot"
echo ""
echo -e "  2. ${YELLOW}Reboot (nach Erstinstallation — wichtig fuer RTL-SDR!):${NC}"
echo -e "     ${CYAN}${_SUDO} reboot${NC}"
echo ""
echo -e "     RTL-SDR-Hinweis: DVB-T Treiber wird erst nach Reboot deaktiviert."
echo -e "     Alternativ ohne Reboot: ${CYAN}${_SUDO} modprobe -r dvb_usb_rtl28xxu rtl2832${NC}"
echo ""

# ── Car-Only Cleanup (v0.10.55: bei Frisch-Install mit anschliessendem Reboot) ──
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
    echo -e "  ${CYAN}${_SUDO} reboot${NC}"
    echo ""
    echo -e "${BOLD}Update nach Reboot:${NC}"
    echo -e "  ${CYAN}curl -sL https://raw.githubusercontent.com/MPunktBPunkt/pidrive/main/install.sh | ${_SUDO} bash${NC}"
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
      echo -e "  Manuell: ${CYAN}${_SUDO} bash ~/pidrive/pidrive_car_only_cleanup.sh${NC}"
    fi
  fi
fi

echo ""
echo -e "${BOLD}Update:${NC}"
echo -e "  ${CYAN}curl -sL https://raw.githubusercontent.com/MPunktBPunkt/pidrive/main/install.sh | ${_SUDO} bash${NC}"
# ── Journald: Größe begrenzen (SD-Karten-Schonung) ─────────────────────────
_jcf=/etc/systemd/journald.conf.d/pidrive.conf
mkdir -p /etc/systemd/journald.conf.d
cat > "$_jcf" << 'JEOF'
[Journal]
SystemMaxUse=50M
SystemMaxFileSize=10M
MaxRetentionSec=7day
JEOF
systemctl restart systemd-journald 2>/dev/null || true
echo "  ✓ Journald: max 50M, 7 Tage Retention"

