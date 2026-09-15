#!/usr/bin/env bash
# PiDrive — Spotify-Diagnose (lesend, keine Aenderungen)
#
# Klaert, warum PiDrive nicht in der Spotify-App erscheint.
# Deutungsschluessel siehe docs/auftraege/AUFTRAG-SPOTIFY-UND-TESTKETTE.md §11
#
# Aufruf:  bash tools/spotify_diag.sh
# Nur lesende Kommandos — sicher im Fahrzeug ausfuehrbar.

echo "=== 1. Dienste: laeuft ueberhaupt etwas? ==="
for svc in raspotify librespot; do
    printf '%-12s aktiv=%-12s eingeschaltet=%s\n' \
        "$svc" \
        "$(systemctl is-active  "$svc" 2>&1)" \
        "$(systemctl is-enabled "$svc" 2>&1)"
done

echo
echo "=== 2. Warum nicht aktiv? (letzte Meldungen) ==="
for svc in raspotify librespot; do
    if systemctl cat "$svc" >/dev/null 2>&1; then
        echo "--- $svc ---"
        journalctl -u "$svc" -n 15 --no-pager 2>&1 | tail -15
    else
        echo "--- $svc: keine Unit installiert ---"
    fi
done

echo
echo "=== 3. Zugangsdaten (kontobasierter Weg haengt daran) ==="
ls -l /var/cache/librespot/ 2>&1

echo
echo "=== 4. Konfiguration (ohne Kommentare) ==="
if [ -r /etc/raspotify/conf ]; then
    grep -vE '^[[:space:]]*#|^[[:space:]]*$' /etc/raspotify/conf 2>&1
else
    echo "/etc/raspotify/conf nicht lesbar oder nicht vorhanden"
fi

echo
echo "=== 5. mDNS-Umfeld (fuer die Discovery-Entscheidung) ==="
echo "avahi-daemon: $(systemctl is-active avahi-daemon 2>&1)"
echo "Listener auf 5353:"
ss -lunp 2>/dev/null | grep 5353 || echo "  keiner"

echo
echo "=== 6. Was PiDrive selbst glaubt ==="
pidrivectl now 2>&1 | head -20

echo
echo "=== 7. Metadaten-Hook ==="
ls -l /usr/local/bin/spotify_event.sh 2>&1
echo "--- /tmp/spotify_status ---"
cat /tmp/spotify_status 2>&1 | head -10
