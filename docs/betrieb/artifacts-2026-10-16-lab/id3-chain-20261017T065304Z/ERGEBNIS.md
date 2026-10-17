# ID3-Kette Lab — Ergebnis

- **ok:** True
- Menü: `[('fav0', 'Rock Antenne'), ('fav1', 'Rock Antenne Bayern'), ('fav2', 'Radio BOB!'), ('pump:page_next', 'Menue')]`
- Stall: `False` (aus — Soft-Cycle-Gate)
- FW `id3Len`: **3200**
- Host-Head via **SG_IO** `@LBA 81`: starts ID3=**True**, parsed **3200**, PDSQ@3204
- first16: `49443303000000001876544954320000`
- ESP Δbytes=8192 Δreads=2 play=fav0 und=0
- Capture READ10: 64

## Kette
1. `menu_set` (Struktur) + Remount
2. Capture `ram_local`
3. `audio_start` + sticky ID3 (3200) + Audio-Prefill
4. Host **SG_IO READ10** Dateikopf (nicht gecachtes `read()`)

## Zum ersten OTG-Steck
Ja: Host liest zuerst MBR/FAT/DIR (= Menüstruktur). Stall dort bremst die UI.
ID3 greift erst beim Dateikopf-READ. Stall und Soft-Cycle nicht mischen.

## Lesson
os.read(/dev/sda) was page-cached (ESP saw 0). SG_IO/O_DIRECT required for real MSC path.
