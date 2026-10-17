# Favoriten-Layout — Leseverhalten Lab (L3-Bänder korrigiert)

- FW aus status-after / Artifact · Soft-Cycle + Host-ls
- Geometrie: Root 33–64, Favoriten-DIR 65–72, Menue-DIR 73–80, fav0 ab 81

| Phase | READ10 | file_slot | meta/dir | file-bands | bands |
|-------|-------:|----------:|---------:|------------|-------|
| A_soft_cycle_alone | 44 | 11 | 10 | file_fav0 | `boot:3, dir_favoriten:1, fat:4, file_fav0:11, other:23, root:2` |
| B_root_ls_only | 64 | 11 | 45 | file_fav0 | `boot:1, dir_favoriten:3, dir_menue:2, fat:5, file_fav0:11, other:8, root:34` |
| C_favoriten_ls_plus_head | 64 | 23 | 29 | file_fav0,file_fav1,file_fav2 | `dir_favoriten:1, dir_menue:2, fat:3, file_fav0:15, file_fav1:4, file_fav2:4, other:12, root:23` |

## Beobachtung

- **A Soft-Cycle allein:** Linux liest trotzdem **fav0**-Bytes (221184 B) — typischer Eager-Probe des ersten Files, nicht aller Stationen.
- **B nur Root-ls:** Host sieht Ordner `Favoriten`/`Menue`; Capture: DIR-Hits + weiterhin fav0-Probe (11 file reads), **kein** fav1/fav2.
- **C Favoriten + Head-dd:** file reads **23**, Bands **['file_fav0', 'file_fav1', 'file_fav2']** (alle drei Stationen).

## Fazit

Ja, geändertes Leseverhalten auf Lab-Linux:
1. Root-Ebene = Ordner; kein sofortiges Auslesen aller drei Stationen.
2. Erst beim Betreten von Favoriten (+ Head-READ) erscheinen fav1/fav2.
3. Soft-Cycle/Kernel scannt weiterhin **fav0** aggressiv (erstes File) — das ist Host-Verhalten, kein NBT. Am Auto erwarten wir: Autoplay erst nach Einstieg in Favoriten bzw. „Alle Titel“.

C−A file_slot Δ = 12; C trifft alle drei Stationen: **True**
