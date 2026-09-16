#!/bin/bash
# PiDrive: WLAN-Netz dauerhaft anlegen (z. B. Handy-Hotspot im Fahrzeug)
#
# Legt ein Netz so an, dass der Pi sich automatisch verbindet, sobald es in
# Reichweite ist. Bedient beide Stacks: NetworkManager und wpa_supplicant.
#
# Das Passwort wird NICHT im Repository gespeichert — es wird als Argument
# uebergeben oder abgefragt. Bitte auch nicht in die Shell-History schreiben
# (fuehrendes Leerzeichen bei bash/HISTCONTROL=ignorespace, oder interaktiv).
#
# Aufruf:
#   sudo bash scripts/wifi-add-network.sh                 # SSID pidrive, Passwort wird abgefragt
#   sudo bash scripts/wifi-add-network.sh pidrive         # dito
#   sudo bash scripts/wifi-add-network.sh MeinNetz        # andere SSID
#
# Pruefen danach:
#   nmcli -t -f NAME,AUTOCONNECT,AUTOCONNECT-PRIORITY connection show   # NetworkManager
#   sudo wpa_cli -i wlan0 list_networks                                 # wpa_supplicant
set -euo pipefail

SSID="${1:-pidrive}"
PSK="${2:-}"
WLAN_IF="${PIDRIVE_WLAN_IF:-wlan0}"

# Hotspot bewusst NIEDRIGER priorisieren als das Heimnetz: steht zuhause das
# Handy mit aktivem Hotspot herum, soll der Pi trotzdem das Heim-WLAN nehmen
# und keine Mobildaten verbrauchen.
PRIORITY="${PIDRIVE_WIFI_PRIORITY:--10}"

log()  { echo "[wifi-add] $*"; }
die()  { echo "[wifi-add] FEHLER: $*" >&2; exit 1; }

if [ "$(id -u)" -ne 0 ]; then
    echo "Bitte mit sudo ausführen:"
    echo "  sudo bash $(readlink -f "$0" 2>/dev/null || echo "$0")"
    exit 1
fi

# ── Passwort einlesen und pruefen ─────────────────────────────────────────
if [ -z "$PSK" ]; then
    read -r -s -p "Passwort für SSID '$SSID' (8-63 Zeichen): " PSK
    echo
fi

_len=${#PSK}
if [ "$_len" -lt 8 ] || [ "$_len" -gt 63 ]; then
    die "Passwort ist $_len Zeichen lang. WPA2-PSK verlangt 8 bis 63 Zeichen —
        das ist eine Protokollgrenze, keine Einstellung. Kürzere Passwörter
        lehnt auch die Hotspot-Funktion von Android/iOS ab."
fi

if [ ! -d "/sys/class/net/$WLAN_IF" ]; then
    log "WARNUNG: Interface $WLAN_IF fehlt — Konfiguration wird trotzdem angelegt"
fi

# ── Weg 1: NetworkManager ─────────────────────────────────────────────────
if systemctl is-active --quiet NetworkManager 2>/dev/null; then
    log "Stack: NetworkManager"

    if nmcli -t -f NAME connection show 2>/dev/null | grep -qx "$SSID"; then
        log "Verbindung '$SSID' existiert — wird aktualisiert (kein Duplikat)"
        nmcli connection modify "$SSID" \
            wifi.ssid "$SSID" \
            wifi-sec.key-mgmt wpa-psk \
            wifi-sec.psk "$PSK" \
            connection.autoconnect yes \
            connection.autoconnect-priority "$PRIORITY"
    else
        log "Verbindung '$SSID' neu anlegen"
        nmcli connection add type wifi \
            con-name "$SSID" \
            ifname "$WLAN_IF" \
            ssid "$SSID" \
            -- \
            wifi-sec.key-mgmt wpa-psk \
            wifi-sec.psk "$PSK" \
            connection.autoconnect yes \
            connection.autoconnect-priority "$PRIORITY"
    fi

    log "Angelegt. Priorität $PRIORITY (niedriger als Heimnetz mit Standard 0)."
    nmcli -t -f NAME,TYPE,AUTOCONNECT,AUTOCONNECT-PRIORITY connection show \
        | grep "^${SSID}:" || true

# ── Weg 2: wpa_supplicant ─────────────────────────────────────────────────
else
    log "Stack: wpa_supplicant"
    CONF="/etc/wpa_supplicant/wpa_supplicant.conf"
    [ -f "$CONF" ] || die "$CONF nicht gefunden — WLAN-Stack unklar, nichts geändert"

    command -v wpa_passphrase >/dev/null 2>&1 \
        || die "wpa_passphrase fehlt (Paket wpasupplicant)"

    if grep -q "ssid=\"$SSID\"" "$CONF"; then
        log "SSID '$SSID' steht bereits in $CONF — keine Änderung"
        log "Zum Ersetzen den Block dort manuell entfernen und erneut aufrufen."
    else
        cp -a "$CONF" "${CONF}.bak.$(date +%Y%m%d%H%M%S)"
        log "Sicherung: ${CONF}.bak.*"

        # wpa_passphrase erzeugt den Hash; die Klartextzeile wird verworfen,
        # damit das Passwort nicht im Klartext in der Datei landet.
        {
            echo ""
            echo "# PiDrive: Handy-Hotspot im Fahrzeug (angelegt $(date -Iseconds))"
            wpa_passphrase "$SSID" "$PSK" \
                | grep -vE '^\s*#psk=' \
                | sed -e 's/^network={/network={/' \
                      -e "/^}/i\\\tscan_ssid=1\n\tpriority=$PRIORITY"
        } >> "$CONF"

        chmod 600 "$CONF"
        log "Block angefügt, Rechte auf 600 gesetzt"
    fi

    if command -v wpa_cli >/dev/null 2>&1; then
        wpa_cli -i "$WLAN_IF" reconfigure >/dev/null 2>&1 \
            && log "wpa_supplicant neu eingelesen" \
            || log "WARNUNG: reconfigure fehlgeschlagen — greift beim nächsten Start"
    fi

    wpa_cli -i "$WLAN_IF" list_networks 2>/dev/null || true
fi

unset PSK

echo
log "Fertig. Der Pi verbindet sich automatisch, sobald '$SSID' in Reichweite ist."
log "Gegenprobe mit eingeschaltetem Hotspot:"
log "  iwgetid -r ; ip -4 addr show $WLAN_IF"
