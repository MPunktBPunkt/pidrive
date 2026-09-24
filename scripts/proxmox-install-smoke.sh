#!/bin/bash
# Soft-Smoke: Debian-12-LXC auf Proxmox anlegen und PiDrive-Installer laufen lassen.
# NUR auf dem Proxmox-Host ausführen (braucht pct/pveam).
set -euo pipefail

CTID="${PIDRIVE_SMOKE_CTID:-120}"
HOSTNAME="${PIDRIVE_SMOKE_HOSTNAME:-pidrive-install-smoke}"
BRIDGE="${PIDRIVE_SMOKE_BRIDGE:-vmbr0}"
STORAGE="${PIDRIVE_SMOKE_STORAGE:-local-lvm}"
TEMPLATE_STORAGE="${PIDRIVE_SMOKE_TEMPLATE_STORAGE:-local}"
MEMORY="${PIDRIVE_SMOKE_MEMORY:-1024}"
CORES="${PIDRIVE_SMOKE_CORES:-2}"
# Installer-Quelle: GitHub main oder lokaler Pfad (wird per pct push kopiert)
INSTALL_SRC="${PIDRIVE_SMOKE_INSTALL_SRC:-github}"
KEEP="${PIDRIVE_SMOKE_KEEP:-0}"

die() { echo "ERROR: $*" >&2; exit 1; }
need() { command -v "$1" >/dev/null || die "$1 nicht gefunden — auf dem PVE-Host ausfuehren"; }

need pct
need pveam

TEMPLATE=$(pveam list "$TEMPLATE_STORAGE" 2>/dev/null | awk '/debian-12-standard.*amd64/ {print $1; exit}')
if [[ -z "${TEMPLATE:-}" ]]; then
    echo "→ lade debian-12 Template..."
    pveam update
    REL=$(pveam available --section system | awk '/debian-12-standard.*amd64/ {print $2; exit}')
    [[ -n "$REL" ]] || die "kein debian-12 Template in pveam available"
    pveam download "$TEMPLATE_STORAGE" "$REL"
    TEMPLATE="${TEMPLATE_STORAGE}:vztmpl/${REL}"
fi
echo "Template: $TEMPLATE"

if pct status "$CTID" &>/dev/null; then
    echo "→ CT $CTID existiert — stop + destroy"
    pct stop "$CTID" 2>/dev/null || true
    pct destroy "$CTID" --purge 1 2>/dev/null || pct destroy "$CTID"
fi

echo "→ create CT $CTID ($HOSTNAME)"
pct create "$CTID" "$TEMPLATE" \
    --hostname "$HOSTNAME" \
    --memory "$MEMORY" \
    --cores "$CORES" \
    --rootfs "${STORAGE}:8" \
    --net0 "name=eth0,bridge=${BRIDGE},ip=dhcp" \
    --features nesting=1 \
    --unprivileged 1 \
    --ostype debian \
    --start 1

# DHCP / Netzwerk kurz warten
for i in $(seq 1 30); do
    if pct exec "$CTID" -- bash -c 'ip -4 -o addr show scope global | grep -q inet'; then
        break
    fi
    sleep 2
done
pct exec "$CTID" -- bash -c 'ip -4 -br a; ping -c1 -W2 8.8.8.8 >/dev/null && echo net_ok || echo net_warn'

echo "→ Basis-Pakete + User pidrive"
pct exec "$CTID" -- bash -c '
set -e
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq sudo curl ca-certificates git
id pidrive >/dev/null 2>&1 || useradd -m -s /bin/bash pidrive
echo "pidrive ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/pidrive-smoke
chmod 440 /etc/sudoers.d/pidrive-smoke
'

if [[ "$INSTALL_SRC" == "github" ]]; then
    echo "→ Installer von GitHub (main)"
    pct exec "$CTID" -- bash -c '
set -e
curl -fsSL https://raw.githubusercontent.com/MPunktBPunkt/pidrive/main/install.sh -o /tmp/install.sh
bash /tmp/install.sh
' || die "Installer fehlgeschlagen"
else
    [[ -f "$INSTALL_SRC" ]] || die "INSTALL_SRC Datei fehlt: $INSTALL_SRC"
    echo "→ Installer lokal: $INSTALL_SRC"
    pct push "$CTID" "$INSTALL_SRC" /tmp/install.sh
    # Wenn Installer lokal ist, Repo ggf. noch von GitHub — Script klont selbst
    pct exec "$CTID" -- bash /tmp/install.sh || die "Installer fehlgeschlagen"
fi

echo "→ Assertions"
pct exec "$CTID" -- bash -c '
set -e
systemctl is-active pidrive_core
systemctl is-active pidrive_web
command -v pidrivectl
pidrivectl version || true
curl -sf -o /dev/null -w "web:%{http_code}\n" --max-time 5 http://127.0.0.1:8080/
systemctl is-enabled pidrive_pump >/dev/null && echo pump_enabled || echo pump_missing
systemctl is-enabled pidrive_pump_bridge >/dev/null && echo bridge_enabled || echo bridge_missing
test -f /etc/systemd/journald.conf.d/pidrive.conf && echo journald_ok
command -v ffmpeg >/dev/null && echo ffmpeg_ok
echo SMOKE_OK
'

IP=$(pct exec "$CTID" -- hostname -I 2>/dev/null | awk '{print $1}')
echo ""
echo "Soft-Smoke OK — CT $CTID ($HOSTNAME) IP=${IP:-?}"
echo "  WebUI: http://${IP:-127.0.0.1}:8080"
if [[ "$KEEP" != "1" ]]; then
    echo "→ KEEP=0 — stop+destroy CT $CTID (PIDRIVE_SMOKE_KEEP=1 zum Behalten)"
    pct stop "$CTID"
    pct destroy "$CTID" --purge 1
else
    echo "→ CT behalten (PIDRIVE_SMOKE_KEEP=1)"
fi
