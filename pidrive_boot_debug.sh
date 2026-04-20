#!/usr/bin/env bash
# PiDrive Boot Debug Snapshot (v0.9.0)
# Sammelt beim Boot Audio/BT/RTL-Parameter
# systemd oneshot: pidrive_boot_debug.service
# Manuell: sudo bash ~/pidrive/pidrive_boot_debug.sh

OUT="/tmp/pidrive_boot_debug_$(date +%Y%m%d_%H%M%S).log"
PA="PULSE_SERVER=unix:/var/run/pulse/native"

{
  echo "====== PiDrive Boot Debug v0.9.0 ======"
  echo "Generated: $(date -Is)"
  echo "Uptime: $(uptime)"
  echo

  echo "=== SERVICES ==="
  systemctl --no-pager status pidrive_core pidrive_display pidrive_web \
    pulseaudio bluetooth raspotify 2>/dev/null | grep -E "●|Active:|Main PID" || true
  echo

  echo "=== PULSE_SERVER in Core Service ==="
  grep "PULSE_SERVER" /etc/systemd/system/pidrive_core.service 2>/dev/null \
    && echo "✓ gesetzt" || echo "✗ FEHLT — kein Ton möglich!"
  echo

  echo "=== AUDIO PROCESSES ==="
  ps ax -o pid=,user=,cmd= | egrep 'mpv|librespot|rtl_fm|welle-cli|pulseaudio|pipewire|pidrive' \
    | grep -v grep || echo "(keine)"
  echo

  echo "=== PULSEAUDIO SINKS ==="
  $PA pactl list sinks short 2>/dev/null || echo "(PulseAudio nicht erreichbar)"
  echo

  echo "=== PULSEAUDIO SINK INPUTS ==="
  $PA pactl list sink-inputs short 2>/dev/null || echo "(keine)"
  echo

  echo "=== amixer numid=3 (Pi 3B Ausgang) ==="
  amixer -c 0 cget numid=3 2>/dev/null | grep "values=" || echo "(nicht lesbar)"
  echo "  0=Auto, 1=Klinke, 2=HDMI"
  echo

  echo "=== BLUETOOTH ==="
  hciconfig hci0 2>/dev/null | head -4 || echo "(kein hci0)"
  bluetoothctl paired-devices 2>/dev/null || echo "(keine gepairten Geräte)"
  echo

  echo "=== RTL-SDR USB ==="
  lsusb | grep -iE "rtl|2832|2838|0bda" || echo "(kein RTL-SDR)"
  echo

  echo "=== SETTINGS ==="
  python3 -c "
import json, sys
try:
    s = json.load(open('/home/pi/pidrive/pidrive/config/settings.json'))
    keys = ['audio_output','volume','fm_gain','dab_gain','scanner_gain','ppm_correction','scanner_squelch','last_source','bt_last_name']
    for k in keys:
        print(f'  {k}: {s.get(k, \"(nicht gesetzt)\")}')
except Exception as e:
    print(f'  Fehler: {e}')
" 2>/dev/null
  echo

  echo "=== AUDIO STATE ==="
  python3 -c "import json; d=json.load(open('/tmp/pidrive_audio_state.json')); print(json.dumps(d,indent=2))" \
    2>/dev/null || echo "(nicht vorhanden)"
  echo

  echo "=== CORE LOG (letzte 20 Zeilen) ==="
  journalctl -u pidrive_core -n 20 --no-pager 2>/dev/null || \
    tail -20 /var/log/pidrive/pidrive.log 2>/dev/null || echo "(kein Log)"
  echo

  echo "=== UNTERSPANNUNG ==="
  vcgencmd get_throttled 2>/dev/null || echo "(vcgencmd nicht verfügbar)"
  echo "  0x0=OK  0x50000=Unterspannung aufgetreten + Throttling"
  echo

} | tee "$OUT"

echo
echo "Debug-Snapshot gespeichert: $OUT"
