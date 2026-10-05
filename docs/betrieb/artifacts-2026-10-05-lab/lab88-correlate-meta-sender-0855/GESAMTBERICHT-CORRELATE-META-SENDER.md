# Lab Correlate Meta vs Sender · 2026-10-05

**ESP:** `.88` · **Artefakt:** `lab88-correlate-meta-sender-0855/`  
**Anschluss an:** [`lab88-menu-page-0816/`](../lab88-menu-page-0816/GESAMTBERICHT-MENU-PAGE-AV-PREP.md)

## Ergebnis **PASS**

| Phase | Menü | `stream.active` | Correlate |
|-------|------|-----------------|-----------|
| Meta (Negativ) | Favoriten/Quellen/Stop | **false** (12 s) | PASS — kein Live-Producer |
| Sender (Positiv) | Rock/Bayern/BOB | **true**, `liveBytes` steigt | PASS |

Hinweis: `liveBytes` auf Meta kann historisch hoch sein (`streamBytes−underruns`); entscheidend ist **`active=false`** und keine neue Producer-Füllung.

## Abend

Erst HU-Sender-Seite → Correlate/Ohr. Meta-Seite = Negativkontrolle (wie Feld 07:52).
