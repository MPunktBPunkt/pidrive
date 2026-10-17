# Play-Guess Favoriten (Lab M22)

FW `0.4.53-dev` · SG_IO Head 16 Blöcke @ `lba0` · Stall enable false

| uid | path | Δguess | playing | id3 |
|---|---|---:|---|---|
| fav0 | `FAVORITEN/01.MP3` | 1 | fav0 | True |
| fav1 (direkt nach fav0) | `FAVORITEN/02.MP3` | 0 | — | True |
| fav1 allein nach Remount | `FAVORITEN/02.MP3` | 1 | fav1 | True |

**any_guess:** True — Favoriten-Pfad armiert Play-Guess weiterhin (R30).  
Zwischen Tips Remount/`lab/stop` nötig, sonst `already_playing`/Cooldown.  
Feld Bayern mit `playGuessCount=0` bleibt anomaly — vor Stall-Leiter am NBT Head-Guess erzwingen.
