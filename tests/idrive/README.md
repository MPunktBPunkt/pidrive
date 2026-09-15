# PiDrive iDrive-Skripte (M6)

**Stand:** v0.11.127 · 2026-09-15

Skripte speisen AVRCP-**Events** ein (nicht fertige Trigger) — dieselbe Ebene wie
`avrcp_trigger.handle_avrcp` / `map_event` inkl. Double-Tap (1,2 s).

```bash
# Couch / CI (ohne Core): lokales MenuState + Menü-Kontext
pidrivectl idrive script tests/idrive/rockfm.txt --offline

# Auf dem Pi mit laufendem Core
pidrivectl idrive next
pidrivectl idrive script tests/idrive/rockfm.txt
```

## Syntax

| Zeile | Bedeutung |
|-------|-----------|
| `next` / `previous` / `play` / `pause` / `stop` / `vol_up` / `vol_down` | Event |
| `sleep 0.5` | Pause in Sekunden |
| `expect key=value` | Prüfung nach Schritt |
| `reset` | Offline-State zurücksetzen |
| `# …` | Kommentar |

Expect-Keys: `selected`, `activated`, `path_contains`, `radio_type`, `station` (live).
