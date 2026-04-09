#!/usr/bin/env bash
# PiDrive Debug Script — sammelt alle relevanten Diagnose-Informationen
# Aufruf: sudo bash ~/pidrive/pidrive_debug.sh
# Ergebnis: /tmp/pidrive_debug_DATUM.log

set -u

SERVICE="pidrive.service"
OUT="/tmp/pidrive_debug_$(date +%Y%m%d_%H%M%S).log"

run() { echo; echo "### CMD: $*"; eval "$@" 2>&1; }
section() { echo; echo "=================================================="; echo "$1"; echo "=================================================="; }

{
  echo "PiDrive Debug Report"
  echo "Generated: $(date -Is)"
  echo "Host: $(hostname)"
  echo "Kernel: $(uname -a)"

  section "SYSTEM BASICS"
  run "id"
  run "uptime"
  run "systemctl --version | head -2"
  run "cat /etc/os-release | grep -E 'NAME|VERSION'"

  section "SERVICE STATUS"
  run "systemctl status $SERVICE --no-pager -l"
  run "systemctl show $SERVICE -p Id -p LoadState -p ActiveState -p SubState -p MainPID -p ExecStart -p User -p WorkingDirectory -p Type -p TTYPath -p StandardInput -p StandardOutput -p StandardError -p PAMName -p FragmentPath"
  run "systemctl cat $SERVICE"

  PID="$(systemctl show -p MainPID --value $SERVICE 2>/dev/null || echo 0)"
  echo; echo "Detected MainPID: ${PID:-<empty>}"

  section "VERSION / REPO"
  run "cat /home/pi/pidrive/pidrive/VERSION 2>/dev/null || echo 'VERSION nicht gefunden'"
  run "git -C /home/pi/pidrive log --oneline -n 5 2>/dev/null || echo 'kein git'"
  run "git -C /home/pi/pidrive status --short 2>/dev/null || true"
  run "head -5 /home/pi/pidrive/pidrive/main.py 2>/dev/null"
  run "head -5 /home/pi/pidrive/pidrive/launcher.py 2>/dev/null"

  section "RC-LOCAL STATUS"
  run "systemctl status rc-local.service --no-pager -l"
  run "cat /etc/rc.local 2>/dev/null || echo 'nicht gefunden'"

  section "TTY / VT BASICS"
  run "ls -l /dev/tty1 /dev/tty2 /dev/tty3 /dev/console 2>/dev/null"
  run "fgconsole 2>/dev/null || echo 'fgconsole fehlt'"
  run "cat /sys/class/tty/tty0/active 2>/dev/null || true"
  run "cat /sys/class/vtconsole/vtcon0/bind 2>/dev/null || true"
  run "cat /sys/class/vtconsole/vtcon1/bind 2>/dev/null || true"

  section "LOGINCTL / SESSIONS"
  run "loginctl list-sessions"
  run "loginctl"

  section "GETTY STATUS"
  for tty in tty1 tty2 tty3; do
    echo "### getty@$tty: $(systemctl is-active getty@$tty.service 2>/dev/null) / $(systemctl is-enabled getty@$tty.service 2>/dev/null)"
  done

  if [[ -n "${PID:-}" && "$PID" != "0" ]]; then
    section "PROZESS-DETAILS (PID $PID)"
    run "ps -o pid,ppid,tty,stat,user,cmd -p $PID"
    run "tr '\\0' ' ' < /proc/$PID/cmdline; echo"
    run "readlink -f /proc/$PID/exe"
    run "ls -l /proc/$PID/cwd"
    run "grep -E '^(Name|State|Pid|PPid|Uid|Gid)' /proc/$PID/status"

    section "SDL ENVIRONMENT (PID $PID)"
  run "cat /proc/$PID/environ | tr '\0' '\n' | grep SDL || echo 'keine SDL Variablen'"
  echo "### vtcon0/bind: $(cat /sys/class/vtconsole/vtcon0/bind 2>/dev/null || echo 'N/A')"
  echo "### vtcon1/bind: $(cat /sys/class/vtconsole/vtcon1/bind 2>/dev/null || echo 'N/A')"
  if cat /proc/$PID/environ 2>/dev/null | tr '\0' '\n' | grep -q "FBCON_KEEP_TTY=1"; then
    echo "### SDL_VIDEO_FBCON_KEEP_TTY=1: OK"
  else
    echo "### SDL_VIDEO_FBCON_KEEP_TTY=1: FEHLT!"
  fi

  section "PROZESS FDs (PID $PID) — KRITISCH"
    echo "### fd 0 (stdin):"
    ls -l /proc/$PID/fd/0 2>/dev/null
    readlink -f /proc/$PID/fd/0 2>/dev/null && echo " ← stdin Ziel"
    echo "### fd 1 (stdout):"
    ls -l /proc/$PID/fd/1 2>/dev/null
    echo "### fd 2 (stderr):"
    ls -l /proc/$PID/fd/2 2>/dev/null
    echo "### controlling terminal (tty_nr aus /proc/PID/stat):"
    awk '{tty=$7; printf "tty_nr=%d (minor=%d = tty%d)\n", tty, tty%256, tty%256}' /proc/$PID/stat 2>/dev/null

    section "PROZESS-BAUM"
    run "pstree -ap $PID 2>/dev/null || ps -ef | grep -E 'pidrive|python' | grep -v grep"
  else
    section "PROZESS-DETAILS"
    echo "Service hat keine laufende MainPID."
  fi

  section "JOURNAL: SERVICE (letzte 100 Zeilen)"
  run "journalctl -u $SERVICE -b --no-pager -n 100"

  section "JOURNAL: PAM / SESSION / TTY"
  run "journalctl -b --no-pager | grep -iE 'pam|session.*tty|logind.*tty' | tail -50"
  run "journalctl -u $SERVICE -b --no-pager | grep -iE 'pam|session|hup|sighup|vt' | tail -20"

  section "CHVT TEST"
  echo "fgconsole vorher: $(fgconsole 2>/dev/null || echo 'unbekannt')"
  echo "Versuche: timeout 5 chvt 3"
  timeout 5 chvt 3 2>&1 && echo "chvt 3: OK" || echo "chvt 3: FEHLER/TIMEOUT (rc=$?)"
  echo "fgconsole nachher: $(fgconsole 2>/dev/null || echo 'unbekannt')"

  section "FRAMEBUFFER / FBCP"
  run "ls -l /dev/fb0 /dev/fb1 2>/dev/null"
  run "ps -ef | grep fbcp | grep -v grep"
  for fb in 0 1; do
    echo "### fb$fb:"
    cat /sys/class/graphics/fb$fb/virtual_size 2>/dev/null || echo "N/A"
    echo "bpp: $(cat /sys/class/graphics/fb$fb/bits_per_pixel 2>/dev/null || echo 'N/A')"
  done

  section "PIDRIVE LOG (letzte 30 Zeilen)"
  run "tail -30 /var/log/pidrive/pidrive.log 2>/dev/null || echo 'Log nicht gefunden'"

  section "ZUSAMMENFASSUNG"
  echo "- fd0=/dev/null  → TTY nicht gebunden, PAMName greift nicht"
  echo "- fd0=/dev/tty3  → TTY korrekt, weiter zu Session/VT prüfen"
  echo "- TTY=? in ps    → kein Terminal am Prozess"
  echo "- Keine PAM-Logs → PAMName wirkt nicht, User/root/PAM-Stack prüfen"
  echo "- v0.4.x im Log  → alter Code läuft, git pull + daemon-reload nötig"

} | tee "$OUT"

echo
echo "Report gespeichert: $OUT"
echo "Sende dieses File beim nächsten Debug-Session mit."
