#!/usr/bin/env bash
# Auf dem Proxmox-Host (oder wo /dev/sdX für den Lexar-Stick existiert) ausführen.
# Löscht den Stick komplett, legt eine FAT32-Partition an, kopiert F1-MP3s.
set -euo pipefail

SRC="${SRC:-}"
if [[ -z "$SRC" ]]; then
  for cand in \
    /home/martin/projects/pidrive/docs/betrieb/artifacts-2026-10-07-feld/feld-s2-prep/f1-stick \
    /var/lib/lxc/*/rootfs/home/martin/projects/pidrive/docs/betrieb/artifacts-2026-10-07-feld/feld-s2-prep/f1-stick \
    /var/lib/vz/root/*/home/martin/projects/pidrive/docs/betrieb/artifacts-2026-10-07-feld/feld-s2-prep/f1-stick
  do
    # shellcheck disable=SC2086
    for d in $cand; do
      if [[ -f "$d/F1-5MB_128k.mp3" && -f "$d/F1-100MB_128k.mp3" ]]; then
        SRC="$d"
        break 2
      fi
    done
  done
fi
[[ -n "$SRC" && -d "$SRC" ]] || {
  echo "F1-MP3s nicht gefunden. SRC=/pfad/zu/f1-stick $0" >&2
  exit 1
}

echo "Quelle: $SRC"
ls -lah "$SRC"/F1-*.mp3

# Lexar ~30G — NIEMALS den 16M PiDrive-ESP (VENDOR PIDRIVE / 16M)
mapfile -t CANDS < <(lsblk -ndo NAME,SIZE,MODEL,VENDOR,TYPE | awk '
  $NF=="disk" && $2 ~ /G/ && ($0 ~ /Lexar/ || $0 ~ /Flash/) {print $1}
')
if [[ ${#CANDS[@]} -eq 0 ]]; then
  echo "Kein Lexar/Flash-Stick gefunden. lsblk:" >&2
  lsblk -o NAME,SIZE,MODEL,VENDOR,TRAN,TYPE >&2
  exit 1
fi
if [[ ${#CANDS[@]} -gt 1 ]]; then
  echo "Mehrere Kandidaten: ${CANDS[*]} — DISK=sdX setzen" >&2
  exit 1
fi
DISK="/dev/${CANDS[0]}"
SIZE=$(lsblk -ndo SIZE "$DISK")
MODEL=$(lsblk -ndo MODEL "$DISK")
echo "Ziel: $DISK  ($SIZE $MODEL)"

# Sicherheit: nicht nvme, nicht <1G
[[ "$DISK" == /dev/sd* ]] || { echo "nur /dev/sd* erlaubt"; exit 1; }
BYTES=$(blockdev --getsize64 "$DISK")
if (( BYTES < 2000000000 || BYTES > 128000000000 )); then
  echo "Größe unplausibel ($BYTES B) — Abbruch" >&2
  exit 1
fi

if [[ "${YES:-}" == "1" ]]; then
  echo "YES=1 — lösche $DISK ohne Rückfrage"
else
  read -r -p "Stick $DISK komplett löschen und F1 schreiben? [y/N] " ans
  [[ "$ans" == "y" || "$ans" == "Y" ]] || exit 0
fi

umount "$DISK"* 2>/dev/null || true
wipefs -a "$DISK"
dd if=/dev/zero of="$DISK" bs=1M count=10 status=none
parted -s "$DISK" mklabel msdos mkpart primary fat32 1MiB 100%
sleep 1
PART="${DISK}1"
# warte auf Partitionsknoten
for _ in $(seq 1 20); do [[ -b "$PART" ]] && break; sleep 0.2; done
[[ -b "$PART" ]] || { echo "Partition $PART fehlt"; lsblk "$DISK"; exit 1; }

mkfs.vfat -F 32 -n F1STICK "$PART"
MNT=$(mktemp -d /mnt/f1stick.XXXXXX)
mount "$PART" "$MNT"
cp -v "$SRC"/F1-5MB_128k.mp3 "$SRC"/F1-100MB_128k.mp3 "$SRC"/F1-INDEX.json "$SRC"/F1-STICK.md "$MNT"/
sync
ls -lah "$MNT"
umount "$MNT"
rmdir "$MNT"
echo "OK — Stick F1STICK bereit (ohne USB-1.1-Hub; den brauchst du erst am Auto)."
