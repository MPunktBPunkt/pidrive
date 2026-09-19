#!/bin/bash
# bmw_avrcp_probe.sh — Phase-(-1)-Messung: oeffnet das NBT Evo den AVRCP-Browsing-Kanal?
#
# Umsetzung von Paket G1 in docs/archiv/auftraege/AUFTRAG-MENUE-UND-GATEWAY.md.
# Diese Messung entscheidet im Gateway-Repo ueber A17 (Bluetooth-Stack) und A18
# (Menue-Transport) und laeuft mit vorhandener Hardware — kein ESP32 noetig.
#
# Das Skript nimmt auf und fuehrt durch die Bedienschritte. Die Auswertung macht
# tools/bmw_avrcp_analyze.py, damit der Interpretationsschluessel getrennt von der
# Messung liegt und der Mitschnitt jederzeit neu ausgewertet werden kann.
#
# Aufruf:
#   sudo ./tools/bmw_avrcp_probe.sh                  # MAC aus bluetoothctl
#   sudo ./tools/bmw_avrcp_probe.sh AA:BB:CC:DD:EE:FF
#   sudo ./tools/bmw_avrcp_probe.sh --dauer 900 AA:BB:CC:DD:EE:FF
#
# Ergebnis liegt danach in $OUTDIR und wird als docs/fahrzeug/BMW-AVRCP-PROBE.md
# eingecheckt.

set -uo pipefail

DAUER=600
BMW_MAC=""
OUTBASE="/var/log/pidrive"

while [ $# -gt 0 ]; do
    case "$1" in
        --dauer)  DAUER="${2:-600}"; shift 2 ;;
        --out)    OUTBASE="${2:-/var/log/pidrive}"; shift 2 ;;
        -h|--help)
            sed -n '2,25p' "$0" | sed 's/^# \{0,1\}//'
            exit 0 ;;
        *) BMW_MAC="$1"; shift ;;
    esac
done

# ── Vorbedingungen ──────────────────────────────────────────────────────────

fehlt=""
for w in btmon bluetoothctl python3; do
    command -v "$w" >/dev/null 2>&1 || fehlt="$fehlt $w"
done
if [ -n "$fehlt" ]; then
    echo "FEHLER: fehlende Werkzeuge:$fehlt" >&2
    echo "        btmon und bluetoothctl kommen aus dem Paket 'bluez'." >&2
    exit 1
fi

if [ "$(id -u)" != "0" ]; then
    echo "FEHLER: btmon braucht Root (CAP_NET_RAW auf dem HCI-Monitor-Socket)." >&2
    echo "        Nochmal mit sudo starten." >&2
    exit 1
fi

# sdptool ist in neueren BlueZ-Versionen nicht mehr enthalten. Kein Abbruch —
# der verlaesslichste Browsing-Hinweis steckt ohnehin im btmon-Mitschnitt.
HAVE_SDPTOOL=0
command -v sdptool >/dev/null 2>&1 && HAVE_SDPTOOL=1

# ── BMW-MAC bestimmen ───────────────────────────────────────────────────────

if [ -z "$BMW_MAC" ]; then
    # Erstes gepaartes Geraet, das nach einem Fahrzeug aussieht, sonst das erste.
    BMW_MAC="$(bluetoothctl devices Paired 2>/dev/null \
        | grep -iE 'bmw|nbt|idrive|mein auto|my car' \
        | head -1 | awk '{print $2}')"
fi
if [ -z "$BMW_MAC" ]; then
    BMW_MAC="$(bluetoothctl devices Paired 2>/dev/null | head -1 | awk '{print $2}')"
fi
if [ -z "$BMW_MAC" ]; then
    echo "FEHLER: kein gepaartes Geraet gefunden und keine MAC angegeben." >&2
    echo "        Verfuegbar:" >&2
    bluetoothctl devices 2>/dev/null | sed 's/^/          /' >&2
    exit 1
fi

BMW_NAME="$(bluetoothctl info "$BMW_MAC" 2>/dev/null \
    | sed -n 's/^\s*Name:\s*//p' | head -1)"
[ -z "$BMW_NAME" ] && BMW_NAME="(unbekannt)"

# ── Ausgabeverzeichnis ──────────────────────────────────────────────────────

TS="$(date +%Y%m%d_%H%M%S)"
if ! mkdir -p "$OUTBASE" 2>/dev/null; then
    OUTBASE="/tmp"
    echo "Hinweis: $OUTBASE nicht beschreibbar, weiche auf /tmp aus." >&2
fi
OUTDIR="$OUTBASE/bmw_probe_$TS"
mkdir -p "$OUTDIR/sdp" || { echo "FEHLER: $OUTDIR nicht anlegbar." >&2; exit 1; }

SNOOP="$OUTDIR/bmw_probe.btsnoop"
MARKER="$OUTDIR/schritte.json"
TEXT="$OUTDIR/mitschnitt.txt"
REPORT="$OUTDIR/BMW-AVRCP-PROBE.md"
JSONOUT="$OUTDIR/befunde.json"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ANALYZER="$SCRIPT_DIR/bmw_avrcp_analyze.py"

# ── Bedienschritte protokollieren ───────────────────────────────────────────
# Jeder Schritt bekommt einen Zeitstempel. Die Auswertung ordnet damit die
# beobachteten PDUs dem jeweiligen Bedienschritt zu — sonst weiss man am Ende
# nicht, welche Handlung im iDrive welche PDU ausgeloest hat.

echo '{ "bmw_mac": "'"$BMW_MAC"'", "bmw_name": "'"$BMW_NAME"'", "schritte": [' > "$MARKER"
MARKER_ERSTER=1

marke() {
    local name="$1"
    [ "$MARKER_ERSTER" = "0" ] && echo "," >> "$MARKER"
    printf '  { "ts": %s, "name": "%s" }' "$(date +%s.%N)" "$name" >> "$MARKER"
    MARKER_ERSTER=0
}

marker_schliessen() {
    echo "" >> "$MARKER"
    echo "] }" >> "$MARKER"
}

# ── Aufraeumen ──────────────────────────────────────────────────────────────

BTMON_PID=""
aufraeumen() {
    if [ -n "$BTMON_PID" ] && kill -0 "$BTMON_PID" 2>/dev/null; then
        kill -TERM "$BTMON_PID" 2>/dev/null
        wait "$BTMON_PID" 2>/dev/null
    fi
}
trap 'echo ""; echo "Abbruch — Mitschnitt wird gesichert."; aufraeumen; marker_schliessen; auswerten; exit 130' INT TERM

auswerten() {
    [ -s "$SNOOP" ] || { echo "Kein Mitschnitt entstanden." >&2; return; }

    echo ""
    echo "---- Auswertung -----------------------------------------------"
    # Dekodierten Text mitschreiben: die Auswertung laeuft damit auch spaeter
    # auf einem Rechner ohne btmon.
    btmon -r "$SNOOP" -T > "$TEXT" 2>/dev/null || true

    if [ -f "$ANALYZER" ]; then
        python3 "$ANALYZER" "$SNOOP" \
            --marker "$MARKER" \
            --sdp-dir "$OUTDIR/sdp" \
            --json "$JSONOUT" \
            --markdown "$REPORT"
        RC=$?
    else
        echo "WARNUNG: $ANALYZER fehlt — nur Rohdaten gesichert." >&2
        RC=4
    fi

    echo ""
    echo "Alles unter: $OUTDIR"
    echo "  btsnoop:   $(basename "$SNOOP")"
    echo "  Text:      $(basename "$TEXT")"
    [ -f "$REPORT" ] && echo "  Bericht:   $(basename "$REPORT")"
    echo ""
    echo "Naechster Schritt: Abschnitte '-1.3 SDP' und '-1.4 Sichtpruefung' im"
    echo "Bericht ausfuellen, dann als docs/fahrzeug/BMW-AVRCP-PROBE.md einchecken."
    return $RC
}

# ── Los ─────────────────────────────────────────────────────────────────────

# Ausgaben bewusst in ASCII: sudo setzt die Locale je nach Konfiguration
# zurueck, und dann wird aus Rahmengrafik Kauderwelsch.
cat <<EOF

================================================================
  BMW-AVRCP-Probe - Phase (-1)
================================================================

  Fahrzeug:  $BMW_NAME  [$BMW_MAC]
  Dauer:     ${DAUER}s
  Ablage:    $OUTDIR

  Gemessen wird, ob das Fahrzeug den AVRCP-Browsing-Kanal oeffnet und
  benutzt. Das Ergebnis entscheidet A17 und A18 im Gateway-Repo.

  Ein negatives Ergebnis ist wertvoll: es spart die Entscheidung fuer
  einen aufwendigen Stackwechsel.

EOF

read -r -p "  Zuendung an und bereit? [Enter] " _ || true

echo ""
echo "---- Mitschnitt laeuft -----------------------------------------"
btmon -w "$SNOOP" > /dev/null 2>&1 &
BTMON_PID=$!
sleep 1

if ! kill -0 "$BTMON_PID" 2>/dev/null; then
    echo "FEHLER: btmon startet nicht. Laeuft schon eine Instanz?" >&2
    exit 1
fi
marke "aufnahme_start"

# ── SDP-Records (-1.3) ──────────────────────────────────────────────────────

echo "  [1/7] SDP-Records auslesen ..."
marke "sdp"
if [ "$HAVE_SDPTOOL" = "1" ]; then
    sdptool browse "$BMW_MAC" > "$OUTDIR/sdp/bmw_browse.txt"  2>&1 || true
    sdptool browse local      > "$OUTDIR/sdp/local_browse.txt" 2>&1 || true
    sdptool records "$BMW_MAC" > "$OUTDIR/sdp/bmw_records.txt" 2>&1 || true
else
    echo "        sdptool fehlt — SDP wird aus dem btsnoop ausgewertet." \
        > "$OUTDIR/sdp/HINWEIS.txt"
fi
# bluetoothctl kennt zumindest die UUIDs, unabhaengig von sdptool.
bluetoothctl info "$BMW_MAC" > "$OUTDIR/sdp/bluetoothctl_info.txt" 2>&1 || true

# ── Gefuehrte Bedienschritte (G1 Schritt 4) ─────────────────────────────────

schritt() {
    local nr="$1" name="$2" text="$3"
    echo ""
    echo "  [$nr/7] $text"
    marke "$name"
    read -r -p "        erledigt? [Enter] " _ || true
}

schritt 2 "verbinden" \
    "Verbindung aufbauen lassen (bzw. 'pidrivectl bt reconnect')."
schritt 3 "multimedia_menu" \
    "Am iDrive: Multimedia -> Bluetooth oeffnen."
schritt 4 "titelliste" \
    "Bei LAUFENDER Wiedergabe das iDrive-Steuerrad drehen, so dass die Liste
        erscheint (die Geste, die bei Radio/USB die Senderliste zeigt).
        Falls keine Liste kommt: Medienliste / Titelliste im Menue oeffnen.
        << WICHTIGSTER SCHRITT >>  Bitte notieren, WAS auf dem Schirm erschien:
        Liste mit Eintraegen / leere Liste / nichts aenderte sich."
schritt 5 "tasten" \
    "Skip vor, Skip zurueck, Play/Pause am Lenkrad druecken."
schritt 6 "quellenwechsel" \
    "Quelle wechseln (Radio -> Bluetooth -> Radio -> Bluetooth)."
schritt 7 "zuendzyklus" \
    "Zuendung aus, 10 s warten, Zuendung an, Verbindung abwarten."

echo ""
echo "  Restaufnahme laeuft. Gern im iDrive weiter navigieren."
echo "  Abbruch mit Strg-C — der Mitschnitt bleibt erhalten."
echo ""

ENDE=$(( $(date +%s) + DAUER ))
while [ "$(date +%s)" -lt "$ENDE" ]; do
    REST=$(( ENDE - $(date +%s) ))
    printf "\r  noch %4ds " "$REST"
    sleep 2
    kill -0 "$BTMON_PID" 2>/dev/null || { echo ""; echo "btmon beendet sich vorzeitig." >&2; break; }
done
printf "\r%*s\r" 20 ""

marke "aufnahme_ende"
aufraeumen
marker_schliessen
auswerten
exit $?
