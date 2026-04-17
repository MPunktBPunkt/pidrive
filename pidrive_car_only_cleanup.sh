#!/usr/bin/env bash
# pidrive_car_only_cleanup.sh — PiDrive Car-Only System Cleanup
# v0.8.11 — Zielarchitektur: dediziertes Car-Infotainment, kein Desktop-Pi
#
# Macht folgendes:
#   1) PiDrive-Dienste sicherstellen
#   2) Unnötige Desktop-/Raspbian-Dienste deaktivieren
#   3) User-Audio-Stack (PulseAudio/PipeWire) stilllegen
#   4) Altprozesse beenden + RTL-SDR-State bereinigen
#   5) snapd deaktivieren
#   6) PiDrive sauber neu starten
#
# Verwendung:
#   sudo bash ~/pidrive/pidrive_car_only_cleanup.sh
#
# Optional danach — aggressive Paketbereinigung:
#   sudo apt purge -y cups cups-browsed modemmanager ofono dundee snapd
#   sudo apt autoremove -y
#   sudo reboot
#
set -e

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; RED='\033[0;31m'; NC='\033[0m'
ok()   { echo -e "${GREEN}  ✓ $*${NC}"; }
warn() { echo -e "${YELLOW}  ⚠ $*${NC}"; }
info() { echo -e "${BLUE}  → $*${NC}"; }
err()  { echo -e "${RED}  ✗ $*${NC}"; }

echo
echo "=================================================="
echo " PiDrive Car-Only Cleanup v0.8.11"
echo " github.com/MPunktBPunkt/pidrive"
echo "=================================================="
echo

if [ "$EUID" -ne 0 ]; then
  err "Bitte mit sudo ausführen:"
  echo "  sudo bash ~/pidrive/pidrive_car_only_cleanup.sh"
  exit 1
fi

REAL_USER="${SUDO_USER:-pi}"

# ------------------------------------------------------------------
# 1) PiDrive-Dienste sicherstellen
# ------------------------------------------------------------------
info "PiDrive-Dienste aktivieren..."
for SVC in pidrive_core pidrive_display pidrive_web pidrive_avrcp rfkill-unblock bluetooth pulseaudio raspotify; do
  systemctl enable "$SVC" 2>/dev/null || true
done
ok "PiDrive-Dienste aktiviert"

# ------------------------------------------------------------------
# 2) Unnötige Standard-/Desktop-Dienste deaktivieren
# ------------------------------------------------------------------
info "Nicht benötigte Dienste deaktivieren..."
for SVC in \
  ModemManager \
  ofono \
  dundee \
  cups \
  cups-browsed \
  triggerhappy \
  avahi-daemon
do
  if systemctl list-unit-files 2>/dev/null | grep -q "^${SVC}\.service"; then
    systemctl stop "$SVC" 2>/dev/null || true
    systemctl disable "$SVC" 2>/dev/null || true
    ok "$SVC deaktiviert"
  fi
done
warn "avahi-daemon wurde deaktiviert — .local-Namensauflösung entfällt"
warn "Für SSH mit Hostname 'raspberrypi.local' avahi wieder aktivieren: systemctl enable --now avahi-daemon"

# ------------------------------------------------------------------
# 3) User-Audio-Stack stilllegen (wichtig für PiDrive Option B!)
# ------------------------------------------------------------------
info "Desktop-Audio-Stack für Benutzer ${REAL_USER} deaktivieren..."
for CMD in \
  "systemctl --user stop pulseaudio.service" \
  "systemctl --user stop pulseaudio.socket" \
  "systemctl --user disable pulseaudio.service" \
  "systemctl --user disable pulseaudio.socket" \
  "systemctl --user stop pipewire.service" \
  "systemctl --user stop pipewire.socket" \
  "systemctl --user stop pipewire-media-session.service" \
  "systemctl --user disable pipewire.service" \
  "systemctl --user disable pipewire.socket" \
  "systemctl --user disable pipewire-media-session.service"
do
  sudo -u "$REAL_USER" bash -c "$CMD" 2>/dev/null || true
done
ok "User-PulseAudio/PipeWire deaktiviert"
info "Nur noch systemweiter PulseAudio (pulseaudio.service) bleibt aktiv"

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
rm -f /tmp/pidrive_rtlsdr.lock      2>/dev/null || true
rm -f /tmp/pidrive_rtlsdr_state.json 2>/dev/null || true
rm -f /tmp/pidrive_dab_welle.err    2>/dev/null || true
rm -f /tmp/pidrive_mpv.sock         2>/dev/null || true
ok "RTL-SDR State bereinigt"

# ------------------------------------------------------------------
# 6) Python-Cache bereinigen
# ------------------------------------------------------------------
info "Python-Cache entfernen..."
find /home/pi/pidrive -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
find /home/pi/pidrive -name "*.pyc" -delete 2>/dev/null || true
ok "Python-Cache bereinigt"

# ------------------------------------------------------------------
# 7) snapd deaktivieren (ressourcenintensiv, für PiDrive nutzlos)
# ------------------------------------------------------------------
if systemctl list-unit-files 2>/dev/null | grep -q "^snapd\.service"; then
  info "snapd deaktivieren..."
  systemctl stop snapd    2>/dev/null || true
  systemctl disable snapd 2>/dev/null || true
  systemctl mask snapd    2>/dev/null || true
  ok "snapd deaktiviert und maskiert"
fi

# ------------------------------------------------------------------
# 8) PiDrive + Audio sauber neu starten
# ------------------------------------------------------------------
info "Dienste neu starten..."
systemctl daemon-reload
systemctl restart dbus       2>/dev/null || true; sleep 1
systemctl restart bluetooth  2>/dev/null || true; sleep 1
systemctl restart pulseaudio 2>/dev/null || true; sleep 1
systemctl restart raspotify  2>/dev/null || true; sleep 1
systemctl restart pidrive_core    2>/dev/null || true; sleep 2
systemctl restart pidrive_display 2>/dev/null || true
systemctl restart pidrive_web     2>/dev/null || true
systemctl restart pidrive_avrcp   2>/dev/null || true
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
  | grep -E 'pidrive|bluetooth|pulseaudio|raspotify|dbus|wpa_supplicant|dhcpcd' || true

echo
echo "PulseAudio Sinks (System):"
PULSE_SERVER=unix:/var/run/pulse/native pactl list sinks short 2>/dev/null \
  || echo "  (PulseAudio noch nicht bereit — nach Reboot prüfen)"

echo
echo "Relevante Prozesse:"
ps ax 2>/dev/null | grep -E 'pidrive|rtl_fm|welle-cli|mpv|pulseaudio|pipewire|librespot|bluetoothd' \
  | grep -v grep || true

echo
ok "Car-Only Cleanup abgeschlossen"
echo
warn "Empfehlung: sudo reboot  (damit alle Änderungen sauber greifen)"
echo
echo "Nach Reboot prüfen:"
echo "  PULSE_SERVER=unix:/var/run/pulse/native pactl list sinks short"
echo "  journalctl -u pidrive_core -n 50 --no-pager"
echo
echo "Optional — Pakete komplett entfernen:"
echo "  sudo apt purge -y cups cups-browsed modemmanager ofono dundee snapd"
echo "  sudo apt autoremove -y"
