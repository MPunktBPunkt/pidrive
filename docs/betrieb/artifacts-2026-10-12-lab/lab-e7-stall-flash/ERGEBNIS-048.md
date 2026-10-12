# Lab-Flash Stall-Build 0.4.48-dev · 2026-10-12

**ESP:** `.88` · OTA von `0.4.47-dev` → **`0.4.48-dev`**

## Warum

Busy-Retry (`return 0`) re-entered `onRead` mit `offset==0` und resetete `stallCmdT0_` → `stallMaxMs` wirkungslos.

## Ergebnis

| Check | Wert |
|-------|------|
| OTA | OK |
| `version` | `0.4.48-dev` |
| Fix verifiziert | L3: `timeouts>0`, `waitMsMax≈maxMs` |

SHA256: `ad17086530fac0c90f833269641dd23849840a7783cee5c62483c0dff195ac2a`

Tests: [`../lab-e7-ladder/ERGEBNIS.md`](../lab-e7-ladder/ERGEBNIS.md)
