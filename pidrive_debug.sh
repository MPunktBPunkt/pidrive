#!/usr/bin/env bash
# PiDrive Debug Script v0.6.0
# Sammelt alle relevanten Diagnose-Informationen
# Aufruf: sudo bash ~/pidrive/pidrive_debug.sh
# Ergebnis: /tmp/pidrive_debug_DATUM.log

set -u
OUT="/tmp/pidrive_debug_$(date +%Y%m%d_%H%M%S).log"

run() { echo; echo "### CMD: $*"; eval "$@" 2>&1; }
section() { echo; echo "=================================================="; echo "$1"; echo "=================================================="; }

{
  echo "PiDrive Debug Report v0.6.0"
  echo "Generated: $(date -Is)"
  echo "Host: $(hostname)"
  echo "Kernel: $(uname -a)"

  section "SYSTEM BASICS"
  run "id"
  run "uptime"
  run "systemctl --version | head -2"

  section "VERSION / REPO"
  run "cat /home/pi/pidrive/pidrive/VERSION 2>/dev/null || echo 'VERSION nicht gefunden'"
  run "git -C /home/pi/pidrive log --oneline -n 5 2>/dev/null || echo 'kein git'"
  run "head -3 /home/pi/pidrive/pidrive/main_core.py 2>/dev/null"
  run "head -3 /home/pi/pidrive/pidrive/main_display.py 2>/dev/null"

  section "CORE SERVICE (pidrive_core)"
  run "systemctl status pidrive_core.service --no-pager -l"
  run "systemctl show pidrive_core -p MainPID -p ActiveState -p ExecStart -p WorkingDirectory"

  CORE_PID="$(systemctl show -p MainPID --value pidrive_core.service 2>/dev/null || echo 0)"
  echo "Core PID: ${CORE_PID}"

  if [[ -n "${CORE_PID}" && "$CORE_PID" != "0" ]]; then
    section "CORE PROZESS (PID $CORE_PID)"
    run "readlink -f /proc/$CORE_PID/exe"
    run "tr '\\0' ' ' < /proc/$CORE_PID/cmdline; echo"
    run "ps -o pid,ppid,tty,stat,cmd -p $CORE_PID"
  fi

  section "DISPLAY SERVICE (pidrive_display)"
  run "systemctl status pidrive_display.service --no-pager -l"
  run "systemctl show pidrive_display -p MainPID -p ActiveState -p Environment"

  DISP_PID="$(systemctl show -p MainPID --value pidrive_display.service 2>/dev/null || echo 0)"
  if [[ -n "${DISP_PID}" && "$DISP_PID" != "0" ]]; then
    section "DISPLAY PROZESS (PID $DISP_PID)"
    run "readlink -f /proc/$DISP_PID/exe 2>/dev/null"
    echo "### SDL Environment:"
    cat /proc/$DISP_PID/environ 2>/dev/null | tr '\0' '\n' | grep SDL || echo "keine SDL Vars"
  fi

  section "ALTER MONOLITHISCHER SERVICE"
  run "systemctl is-active pidrive.service 2>/dev/null || echo 'nicht vorhanden (korrekt)'"

  section "IPC STATUS (/tmp/ Dateien)"
  run "ls -la /tmp/pidrive_*.json /tmp/pidrive_cmd 2>/dev/null || echo 'keine IPC-Dateien'"
  run "cat /tmp/pidrive_status.json 2>/dev/null || echo 'status.json fehlt'"
  run "cat /tmp/pidrive_menu.json 2>/dev/null || echo 'menu.json fehlt'"

  section "RC-LOCAL STATUS"
  run "systemctl status rc-local.service --no-pager -l"
  run "cat /etc/rc.local 2>/dev/null"

  section "FRAMEBUFFER / FBCP"
  run "ls -l /dev/fb0 /dev/fb1 2>/dev/null"
  echo "### fb0: $(cat /sys/class/graphics/fb0/virtual_size 2>/dev/null), bpp=$(cat /sys/class/graphics/fb0/bits_per_pixel 2>/dev/null)"
  echo "### fb1: $(cat /sys/class/graphics/fb1/virtual_size 2>/dev/null), bpp=$(cat /sys/class/graphics/fb1/bits_per_pixel 2>/dev/null)"
  echo "### fbcp: $(pgrep -a fbcp 2>/dev/null || echo 'nicht aktiv (korrekt fuer v0.6.0)')"

  section "VTCONSOLE STATUS"
  echo "### vtcon0/bind: $(cat /sys/class/vtconsole/vtcon0/bind 2>/dev/null)"
  echo "### vtcon1/bind: $(cat /sys/class/vtconsole/vtcon1/bind 2>/dev/null)"
  run "cat /boot/cmdline.txt 2>/dev/null | grep -o 'fbcon=[^ ]*' || echo 'kein fbcon= Parameter'"

  section "TTY / VT BASICS"
  run "fgconsole 2>/dev/null || echo 'N/A'"
  run "cat /sys/class/tty/tty0/active 2>/dev/null || true"

  section "JOURNAL: CORE SERVICE"
  run "journalctl -u pidrive_core -b --no-pager -n 50"

  section "JOURNAL: DISPLAY SERVICE"
  run "journalctl -u pidrive_display -b --no-pager -n 30"

  section "PIDRIVE LOG (letzte 30 Zeilen)"
  run "tail -30 /var/log/pidrive/pidrive.log 2>/dev/null || echo 'Log nicht gefunden'"

  section "ZUSAMMENFASSUNG"
  echo "=== v0.6.0 Architektur ==="
  echo "- pidrive_core: $(systemctl is-active pidrive_core 2>/dev/null)"
  echo "- pidrive_display: $(systemctl is-active pidrive_display 2>/dev/null)"
  echo "- IPC status.json: $(test -f /tmp/pidrive_status.json && echo 'vorhanden' || echo 'FEHLT')"
  echo "- fbcp: $(pgrep fbcp >/dev/null 2>&1 && echo 'LAEUFT (nicht noetig)' || echo 'inaktiv (korrekt)')"
  echo "- SDL_FBDEV=/dev/fb1: $(systemctl show pidrive_display -p Environment 2>/dev/null | grep -o 'SDL_FBDEV=[^ ]*' || echo 'nicht gesetzt')"
  echo ""
  echo "=== Quick-Tests ==="
  echo "Core Trigger:  echo 'down' > /tmp/pidrive_cmd"
  echo "Status lesen:  cat /tmp/pidrive_status.json"
  echo "Display Test:  sudo SDL_FBDEV=/dev/fb1 SDL_VIDEODRIVER=fbcon SDL_AUDIODRIVER=dummy"
  echo "               SDL_VIDEO_FBCON_KEEP_TTY=1 python3 -c"
  echo "               \"import pygame,time; pygame.display.init();"
  echo "               s=pygame.display.set_mode((480,320),0,16); s.fill((255,0,0));"
  echo "               pygame.display.flip(); print('ROT OK'); time.sleep(5)\""

} | tee "$OUT"

echo
echo "Report gespeichert: $OUT"
