#!/usr/bin/env bash
# pidrive_car_only_cleanup.sh — PiDrive Car-Only System Cleanup
# v0.9.0 — PipeWire System-Mode; Avahi bleibt an
#
# Macht folgendes:
#   1) PiDrive-Dienste sicherstellen
#   2) Unnötige Desktop-/Raspbian-Dienste deaktivieren (ohne avahi)
#   3) User-Audio-Stack (PulseAudio/User-PipeWire) HARD killen + maskieren
#   4) Altprozesse beenden + RTL-SDR-State bereinigen
#   5) snapd deaktivieren
#   6) PiDrive + System-PipeWire sauber neu starten
#
# Verwendung: sudo bash ~/pidrive/pidrive_car_only_cleanup.sh
#
set -e

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; RED='\033[0;31m'; NC='\033[0m'
ok()   { echo -e "${GREEN}  ✓ $*${NC}"; }
warn() { echo -e "${YELLOW}  ⚠ $*${NC}"; }
info() { echo -e "${BLUE}  → $*${NC}"; }
err()  { echo -e "${RED}  ✗ $*${NC}"; }

echo
echo "=================================================="
echo " PiDrive Car-Only Cleanup v0.9.0"
echo " github.com/MPunktBPunkt/pidrive"
echo "=================================================="
echo

if [ "$EUID" -ne 0 ]; then
  err "Bitte mit sudo ausführen:"
  echo "  sudo bash ~/pidrive/pidrive_car_only_cleanup.sh"
  exit 1
fi

# REAL_USER: SUDO_USER bevorzugen, dann pidrive als Default (nicht pi)
if [ -n "$SUDO_USER" ] && [ "$SUDO_USER" != "root" ]; then
    REAL_USER="$SUDO_USER"
elif id pidrive &>/dev/null 2>&1; then
    REAL_USER="pidrive"
elif id pi &>/dev/null 2>&1; then
    REAL_USER="pi"
else
    REAL_USER="$(getent passwd | awk -F: '$3>=1000 && $3<65534{print $1;exit}')"
fi
REAL_UID="$(id -u "$REAL_USER" 2>/dev/null || echo 1000)"

# ------------------------------------------------------------------
# 1) PiDrive-Dienste sicherstellen
# ------------------------------------------------------------------
info "PiDrive-Dienste aktivieren..."
for SVC in pidrive_core pidrive_web pidrive_avrcp pidrive_btagent \
           rfkill-unblock bluetooth pipewire pipewire-pulse wireplumber; do
  systemctl enable "$SVC" 2>/dev/null || true
done
# Legacy-Display-Unit bewusst nicht enablen
ok "PiDrive-Dienste aktiviert"

# ------------------------------------------------------------------
# 2) Unnötige Standard-/Desktop-Dienste deaktivieren
# ------------------------------------------------------------------
info "Nicht benötigte Dienste deaktivieren..."
# avahi-daemon bleibt an (mDNS / .local, Installer installiert es bewusst)
for SVC in ModemManager ofono dundee cups cups-browsed triggerhappy; do
  if systemctl list-unit-files "${SVC}.service" 2>/dev/null | grep -q "${SVC}.service"; then
    systemctl stop "$SVC" 2>/dev/null || true
    systemctl disable "$SVC" 2>/dev/null || true
    ok "$SVC deaktiviert"
  fi
done
if systemctl is-enabled avahi-daemon >/dev/null 2>&1; then
  ok "avahi-daemon bleibt aktiv (.local / mDNS)"
fi

# ------------------------------------------------------------------
# 3) User-Audio-Stack HARD killen + maskieren (System-PipeWire bleibt)
# ------------------------------------------------------------------
info "Desktop-Audio-Stack für Benutzer ${REAL_USER} deaktivieren und beenden..."

for CMD in \
  "systemctl --user stop pulseaudio.service" \
  "systemctl --user stop pulseaudio.socket" \
  "systemctl --user disable pulseaudio.service" \
  "systemctl --user disable pulseaudio.socket" \
  "systemctl --user mask pulseaudio.service" \
  "systemctl --user mask pulseaudio.socket" \
  "systemctl --user stop pipewire.service" \
  "systemctl --user stop pipewire.socket" \
  "systemctl --user stop pipewire-pulse.service" \
  "systemctl --user stop wireplumber.service" \
  "systemctl --user stop pipewire-media-session.service" \
  "systemctl --user disable pipewire.service" \
  "systemctl --user disable pipewire.socket" \
  "systemctl --user disable pipewire-pulse.service" \
  "systemctl --user disable wireplumber.service" \
  "systemctl --user disable pipewire-media-session.service" \
  "systemctl --user mask pipewire.service" \
  "systemctl --user mask pipewire.socket" \
  "systemctl --user mask pipewire-pulse.service" \
  "systemctl --user mask wireplumber.service" \
  "systemctl --user mask pipewire-media-session.service"
do
  runuser -u "$REAL_USER" -- \
    XDG_RUNTIME_DIR="/run/user/${REAL_UID}" \
    DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/${REAL_UID}/bus" \
    bash -lc "$CMD" 2>/dev/null || true
done

pkill -u "$REAL_UID" -f "/usr/bin/pipewire$"          2>/dev/null || true
pkill -u "$REAL_UID" -f "/usr/bin/pipewire-pulse"     2>/dev/null || true
pkill -u "$REAL_UID" -f "/usr/bin/wireplumber"        2>/dev/null || true
pkill -u "$REAL_UID" -f "/usr/bin/pipewire-media-session" 2>/dev/null || true
pkill -u "$REAL_UID" -f "/usr/bin/pulseaudio"         2>/dev/null || true
sleep 1
pkill -9 -u "$REAL_UID" -f "/usr/bin/pipewire$"       2>/dev/null || true
pkill -9 -u "$REAL_UID" -f "/usr/bin/pipewire-pulse"  2>/dev/null || true
pkill -9 -u "$REAL_UID" -f "/usr/bin/wireplumber"     2>/dev/null || true
pkill -9 -u "$REAL_UID" -f "/usr/bin/pulseaudio"      2>/dev/null || true

loginctl disable-linger "$REAL_USER" 2>/dev/null || true

mkdir -p "/home/${REAL_USER}/.config/systemd/user"
for UNIT in pulseaudio.service pulseaudio.socket \
            pipewire.service pipewire.socket pipewire-pulse.service \
            wireplumber.service pipewire-media-session.service; do
  cat > "/home/${REAL_USER}/.config/systemd/user/${UNIT}" << 'UNITEOF'
[Unit]
Description=Masked by PiDrive Car-Only Cleanup (use system PipeWire)
[Service]
ExecStart=/bin/false
UNITEOF
done
chown -R "${REAL_USER}:${REAL_USER}" "/home/${REAL_USER}/.config/systemd" 2>/dev/null || true

ok "User-PulseAudio/User-PipeWire deaktiviert — System-PipeWire bleibt"

# ------------------------------------------------------------------
# 4) Altprozesse beenden
# ------------------------------------------------------------------
info "Laufende Altprozesse beenden..."
for PROC in "bluetoothctl scan" dbus-monitor pidrive_radio pidrive_dab \
            pidrive_fm pidrive_scanner rtl_fm welle-cli mpv aplay; do
  pkill -f "$PROC" 2>/dev/null || true
done
ok "Altprozesse beendet"

# ------------------------------------------------------------------
# 5) RTL-SDR Stale-State bereinigen
# ------------------------------------------------------------------
info "RTL-SDR Lock/State aufräumen..."
rm -f /tmp/pidrive_rtlsdr.lock       2>/dev/null || true
rm -f /tmp/pidrive_rtlsdr_state.json 2>/dev/null || true
rm -f /tmp/pidrive_dab_welle.err     2>/dev/null || true
rm -f /tmp/pidrive_mpv.sock          2>/dev/null || true
ok "RTL-SDR State bereinigt"

# ------------------------------------------------------------------
# 6) Python-Cache bereinigen
# ------------------------------------------------------------------
info "Python-Cache entfernen..."
_INSTALL_DIR="${INSTALL_DIR:-}"
if [ -z "$_INSTALL_DIR" ]; then
    if [ -d "/home/pidrive/pidrive/pidrive" ]; then
        _INSTALL_DIR="/home/pidrive/pidrive"
    elif [ -d "/home/pi/pidrive/pidrive" ]; then
        _INSTALL_DIR="/home/pi/pidrive"
    elif [ -d "/opt/pidrive/pidrive" ]; then
        _INSTALL_DIR="/opt/pidrive"
    else
        warn "INSTALL_DIR nicht gefunden — Cache-Cleanup übersprungen"
        _INSTALL_DIR=""
    fi
fi
if [ -n "$_INSTALL_DIR" ]; then
    find "$_INSTALL_DIR/pidrive" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
    find "$_INSTALL_DIR/pidrive" -name "*.pyc" -delete 2>/dev/null || true
fi
ok "Python-Cache bereinigt"

# ------------------------------------------------------------------
# 7) snapd deaktivieren
# ------------------------------------------------------------------
if systemctl list-unit-files snapd.service 2>/dev/null | grep -q snapd.service; then
  info "snapd deaktivieren..."
  systemctl stop snapd    2>/dev/null || true
  systemctl disable snapd 2>/dev/null || true
  systemctl mask snapd    2>/dev/null || true
  ok "snapd deaktiviert und maskiert"
fi

# ------------------------------------------------------------------
# 8) PiDrive + System-PipeWire sauber neu starten
# ------------------------------------------------------------------
info "Dienste neu starten..."
systemctl daemon-reload
systemctl restart dbus 2>/dev/null || true; sleep 1
systemctl is-active bluetooth 2>/dev/null | grep -q active || systemctl start bluetooth 2>/dev/null || true
sleep 1
# Kein pulseaudio — System-PipeWire
systemctl enable pipewire pipewire-pulse wireplumber 2>/dev/null || true
systemctl restart pipewire 2>/dev/null || true; sleep 1
systemctl restart pipewire-pulse 2>/dev/null || true; sleep 1
systemctl restart wireplumber 2>/dev/null || true; sleep 1
systemctl restart raspotify 2>/dev/null || true
systemctl restart pidrive_core 2>/dev/null || true; sleep 2
systemctl restart pidrive_web 2>/dev/null || true
systemctl restart pidrive_avrcp 2>/dev/null || true
ok "Dienste neu gestartet"

# ------------------------------------------------------------------
# 9) Statusübersicht
# ------------------------------------------------------------------
echo
echo "=================================================="
echo " STATUS"
echo "=================================================="

echo
echo "Laufende PiDrive-relevante Dienste:"
systemctl --no-pager --type=service --state=running 2>/dev/null \
  | grep -E 'pidrive|bluetooth|pipewire|wireplumber|raspotify|dbus|wpa_supplicant|avahi' || true

echo
echo "PipeWire Sinks (PULSE_SERVER Compat):"
PULSE_SERVER=unix:/var/run/pulse/native pactl list sinks short 2>/dev/null \
  || echo "  (PipeWire-Pulse noch nicht bereit — nach Reboot prüfen)"

echo
echo "Relevante Prozesse:"
ps ax 2>/dev/null | grep -E 'pidrive|rtl_fm|welle-cli|mpv|pulseaudio|pipewire|librespot|bluetoothd' \
  | grep -v grep || true

echo
ok "Car-Only Cleanup abgeschlossen"
echo
warn "Optional: sudo reboot (User-Unit-Masking greift nach Login neu)"
echo
echo "Nach Reboot prüfen:"
echo "  systemctl is-active pipewire pipewire-pulse wireplumber pidrive_core"
echo "  PULSE_SERVER=unix:/var/run/pulse/native pactl list sinks short"
echo "  journalctl -u pidrive_core -n 50 --no-pager"
echo
echo "Optional — Pakete komplett entfernen:"
echo "  sudo apt purge -y cups cups-browsed modemmanager ofono dundee snapd"
echo "  sudo apt autoremove -y"
