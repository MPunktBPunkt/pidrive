# Zustandsmaschine — Quellenwechsel und Transitionen

**Stand:** v0.11.143 · 2026-09-19

Referenz für `modules/source_state.py`. Historischer Auftrag:
[../archiv/auftraege/AUFTRAG-WEBUI-SANIERUNG.md](../archiv/auftraege/AUFTRAG-WEBUI-SANIERUNG.md), W7.

CLI: `pidrivectl source state` · `pidrivectl source history`.

---

## 1. Spiegel, kein Regler

`source_state` speichert den gemeinsamen Zustand (`STATE` + `/tmp/pidrive_source_state.json`).
Es gibt keine formale Übergangstabelle — Korrektheit liegt bei den Aufrufern.

## 2. Felder

| Feld | Bedeutung |
|------|-----------|
| `source_current` / `source_previous` | aktuelle / vorherige Quelle |
| `transition` / `owner` / `source_target` / `since` | laufende Transition |
| `dab_playback_state` | idle\|starting\|locked\|no_lock\|failed |
| `playback_epoch` | UI leert Meta bei Wechsel |
| `play_gen` | **v0.11.143** — invalidiert in-flight play_*/stop |

## 3. Transition

```
begin_transition(owner, target) → True
commit_source(quelle)
end_transition()
```

Bei blockiertem `begin`: `radio_stop` nutzt `force_end_transition` und commitet idle.
Stale-Watchdog räumt Transitionen >12 s ab.

## 4. play_gen (Race-Schutz)

Jeder User-Intent (`play_dab`/`play_fm`/`play_web`/`radio_stop`) ruft `bump_play_gen()` auf.
Lange bg-Threads prüfen `is_play_gen(gen)` und committen nicht mehr, wenn veraltet.
Früher Commit vor DAB-Lock-Wait bleibt (UI wechselt sofort).

Typische Smoke-Zeiten (Pi, indoor, DAB ohne Sync OK): FM first/switch &lt;1 s, dab→fm &lt;2 s, dab→stop &lt;2 s.

## 5. WebUI Listen-Klick

Senderlisten nutzen **data-Attribute + Event-Delegation** (`bindStationClicks`).
Früher kaputt: `onclick="fn(${JSON.stringify(...)})"` in doppelten Quotes → Attr endete bei erstem `"`.

Favoriten (Index) waren davon nicht betroffen.

## 6. Tests

- `pidrivectl webui smoke` / Diagnose-Tab / `test all`
- `tools/webui_live_smoke.py` prüft kaputte onclick-Patterns

## Verweise

- [../FEATURES.md](../FEATURES.md) F-056, F-099, F-100
- [../betrieb/SPECTRUM-CLI.md](../betrieb/SPECTRUM-CLI.md)
