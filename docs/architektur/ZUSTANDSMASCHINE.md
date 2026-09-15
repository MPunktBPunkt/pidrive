# Zustandsmaschine — Quellenwechsel und Transitionen

**Stand:** v0.11.132 · 2026-09-15

Referenz für `modules/source_state.py` und die daran hängenden Koordinierungsschichten.
Dieses Dokument beschreibt den **Ist-Zustand**, benennt die Lücken und definiert ein
gestuftes Zielbild. Die Arbeitspakete dazu stehen in
[../auftraege/AUFTRAG-WEBUI-SANIERUNG.md](../auftraege/AUFTRAG-WEBUI-SANIERUNG.md), W7.

CLI-Diagnose: `pidrivectl source state` · `pidrivectl source history`.

Zeilenangaben unten teils noch auf Stand v0.11.127; bei Abweichung Code lesen.

---

## 1. Was das Modul ist — und was nicht

`modules/source_state.py` bezeichnet sich in Zeile 2 selbst korrekt als
**„Zustandsspiegel (kein Regler)"**. Das ist die wichtigste Aussage über die
Architektur, und sie wird in der Praxis regelmäßig anders verstanden.

Es gibt **keine** Zustandsmaschine im formalen Sinn:

- keine Aufzählung erlaubter Zustände,
- keine Übergangstabelle,
- keine Prüfung, ob ein Übergang zulässig ist,
- keine Validierung der Quellennamen — `commit_source("irgendwas")` wird akzeptiert.

Das Modul ist ein gemeinsames Dictionary (`STATE`, Zeile 27-43) mit einem `RLock` und
einem Dateischreiber nach `/tmp/pidrive_source_state.json`.

**Folge:** Die gesamte Korrektheit liegt bei den Aufrufern — rund 50 Stellen in
`trigger/*`, `modules/*` und `main_core.py`. Jede historisch beobachtete „Lücke"
entstand an dieser Nahtstelle, nicht im Modul selbst.

---

## 2. Zustandsfelder

| Feld | Setzer | Gelesen von | Anmerkung |
|---|---|---|---|
| `source_current` | `commit_source()` | UI, `menu_builder`, Trigger | 8 mögliche Werte, nicht validiert |
| `source_previous` | `commit_source()` automatisch | `previous_source()` | für Rückkehr nach Fehler |
| `source_target` | `begin_transition()` | UI (`index.html:474`) | während der Transition |
| `transition` | `begin/end/force_end` | UI, `in_transition()` | Stale: Z3 behoben (Stufe 1) |
| `owner` | `begin_transition()` | Log, UI | keine Namenskonvention (Z6) |
| `since` | `begin_transition()` | Stale-Berechnung | — |
| `audio_route` | `set_audio_route()` | UI, `diagnose.py:734` | — |
| `bt_state` | `set_bt_state()` | `bt_connected()` | `idle`/`connected` |
| `bt_link_state` | `set_bt_link_state()` | `bluetooth.html:124` | Log-Beschriftung falsch (Z8) |
| `bt_audio_state` | `set_bt_audio_state()` | `bluetooth.html:125` | — |
| `boot_phase` | `set_boot_phase()` | UI | 5 Aufrufe in `main_core` |
| `transition_count` | `begin_transition()` | Diagnose | — |
| `stale_cleared` | Watchdog, Override | Diagnose | — |
| `dab_playback_state` | **niemand** | — | totes Feld (Z7) |
| `playback_epoch` | `commit_source()` bei Wechsel | `index.html:457` | — |

---

## 3. Das Transitionsprotokoll

**Vorgesehen:**

```
begin_transition(owner, target) → True
    … Arbeit …
commit_source(neue_quelle)
end_transition()
```

Bei `begin_transition() == False` läuft schon eine Transition; der Aufrufer **muss**
abbrechen und das dem Nutzer melden.

**Tatsächlich:**

| Kennzahl | Wert |
|---|---|
| `commit_source`-Aufrufe | 34 |
| `begin_transition`-Aufrufe | 15 |
| davon mit Behandlung von `False` | **2** |
| `force_end_transition`-Aufrufe | **0** |

Mehr als die Hälfte aller Quellenwechsel läuft also ohne jede Transition — inklusive
der Erhöhung von `playback_epoch` und der Fortschreibung von `source_previous`.

### Die zwei vorbildlichen Aufrufstellen

`trigger/td_radio.py:96-101` ist die vollständige Referenzform — Ablehnung erkannt,
Nutzer informiert, Nebensperre freigegeben, Abbruch:

```python
if not source_state.begin_transition(owner, "dab"):
    ipc.write_progress("DAB+ Suchlauf", "Blockiert", color="orange")
    _time_mod.sleep(2)
    ipc.clear_progress()
    _scan_end()
    return
```

`trigger/td_nav.py:164-165` ist die zweite: es prüft die Nebensperre und liest über
`_source_switch_info()` aus, **wer** blockiert.

Alle übrigen 17 Stellen haben kein `else`.

---

## 4. Drei parallele Sperrschichten

Historisch gewachsen. Keine ist maßgeblich, keiner der Pfade nutzt alle.

| Schicht | Ort | Art | Aufrufer |
|---|---|---|---|
| 1 — Transition | `source_state.py:100` | Hinweisflag in Datei, 12s Verfall | 15 |
| 2 — Scan-Sperre | `main_core.py:40-58` | echtes `threading.Lock` | 3 (`td_radio`: DAB×2, FM) |
| 3 — Source-Switch | `main_core.py:70-96` | echtes `threading.Lock`, `blocking=False` | 1 (`td_nav.py:164`) |
| 4 — RTL-SDR-`flock` | `modules/radio/rtlsdr.py:300-415` | Dateisperre | **0 — unerreichbar** |

**Zu Schicht 4 (Nachtrag 2026-09-15):** Sie ist nicht unfertig, sondern **durch einen
Importfehler unerreichbar**. `acquire_runtime_lock()`, `release_runtime_lock()`,
`acquire_lock()` und `start_process()`/`stop_process()` sind vollständig implementiert.
Es fehlen die Kompatibilitäts-Shims `modules/rtlsdr.py` und `modules/spectrum.py`,
weshalb `_rtlsdr` bei allen Konsumenten `None` ist und jede Nutzung hinter `if _rtlsdr:`
übersprungen wird. Ursache, Wirkung und Behebung als Befund C2 / Paket **W4** in
[../auftraege/AUFTRAG-WEBUI-SANIERUNG.md](../auftraege/AUFTRAG-WEBUI-SANIERUNG.md) —
dort auch der Beleg, dass dadurch ein DAB-Scan bei laufender Wiedergabe fälschlich
„kein Signal" meldet.

Dazu als fünfte Zeitschranke die Trigger-Entprellung (`main_core.py:104`) und als
zweiter Zustandsspiegel `status.S` → `/tmp/pidrive_status.json`.

**Welcher Pfad nutzt was:**

| Pfad | Schichten |
|---|---|
| Menü-Quellenwechsel (`td_nav`) | 1 + 3 |
| DAB-/FM-Suchlauf (`td_radio`) | 1 + 2 |
| Scanner (`td_scanner`) | nur 1 |
| Bluetooth (`td_hardware`) | keine für die Quelle selbst |

Schicht 2 und 3 sind offensichtlich entstanden, **weil** Schicht 1 als Mutex nicht
trägt. Schicht 1 wurde dabei nicht ersetzt, sondern überlagert.

Schicht 2 und 3 werden per Abhängigkeitsinjektion in die Trigger gegeben
(`main_core.py:154-171` → `trigger/trigger_dispatcher.py:37-42` → `td_nav`, `td_radio`).
`td_radio.py:17` hält dafür einen Platzhalter `lambda source: True` — bleibt die
Injektion aus, erlaubt die Scan-Sperre **alles**, ohne Hinweis.

---

## 5. Quellenmodell

Tatsächlich committete Quellennamen (alle als Literal, kein Aufruf mit Variable):

| Quelle | Commits |
|---|---|
| `idle` | 11 |
| `scanner` | 10 |
| `dab` | 6 |
| `webradio` | 6 |
| `fm` | 4 |
| `local` | 2 |
| `library` | 1 |
| `spotify` | 1 |

**`bt` kommt nicht vor — an keiner Stelle.** Bluetooth-Audio wird ausschließlich über
die Parallelfelder `bt_state`, `bt_link_state` und `bt_audio_state` geführt.

---

## 6. Lücken

### Z1 Bluetooth ist keine Quelle `[BELEGT]` — konzeptionell die größte Lücke

Die im Fahrzeug wichtigste Quelle existiert im Quellenmodell nicht. `source_current`
steht während einer laufenden A2DP-Wiedergabe auf `idle` oder auf der vorher aktiven
Quelle.

**Folgen:** Das WebUI muss zwei Zustandswelten selbst verrechnen — daraus entsteht
unter anderem das defekte dreistufige BT-Icon. `previous_source()` kann nach einem
BT-Abbruch nicht sinnvoll zurückkehren. Und: **`esp32.bt-gateway` wird eine Quelle
sein — es gibt derzeit keinen Platz dafür.**

### Z2 Abgelehnte Wechsel verschwinden stumm `[BEHOBEN v0.11.130 / Stufe 1]`

**War:** Aufrufer ignorierten `begin_transition() == False` → stumme Ablehnung.
**Jetzt:** Aufrufer melden Blockade (Progress/UI); `pidrivectl source state` zeigt
laufende Transition. Historischer Befund bleibt relevant für Regressionstests (R12).

### Z3 Der Watchdog läuft nicht, und `in_transition()` repariert nicht `[BEHOBEN v0.11.130 / Stufe 1]`

**War:** `_check_stale_transition()` nur aus commit/end; `in_transition()` gab nach
Timeout `False` ohne Datei zu bereinigen → Speicher ≠ WebUI-Datei.

**Jetzt:** `in_transition()` räumt Stale auf (Datei=Speicher); periodischer
`check_stale_transition()` in der Core-Hauptschleife (~0,5 s).

### Z4 `end_transition()` prüft den Eigentümer nicht `[BELEGT]` — hoch

Jeder kann jede Transition beenden. Konkreter Fall: `scanner.stop()` ruft
`end_transition()` (`scanner.py:461-465`), `play_freq` ruft `stop(S)` (`:324`) — jedes
Tunen beendet also die von `td_scanner` geöffnete Transition, die dann im `finally`
(`td_scanner.py:100`) ein zweites Mal beendet wird.

Schicht 3 hat dasselbe Problem in anderer Form: `_source_switch_end()`
(`main_core.py:84-92`) gibt bei `locked()` frei, und ein `threading.Lock` lässt sich in
Python auch von einem fremden Thread freigeben.

### Z5 `force_end_transition()` hat null Aufrufer `[BELEGT]` — mittel

Die in Zeile 10 angekündigte Fehler-Wiederherstellung für `except`-Blöcke existiert als
Funktion, wird aber nirgends benutzt. Die Wiederherstellung nach Ausnahmen verlässt
sich stattdessen auf `finally: end_transition()` — was wegen Z4 die falsche Transition
treffen kann.

### Z6 Keine Konvention für `owner` `[BELEGT]` — blockiert die Reparatur von Z4

| Aufrufstelle | Übergebener `owner` | Bedeutung |
|---|---|---|
| `td_scanner.py:94` | `scan_next:pmr446` | Kommandoname |
| `td_radio.py:202` | `webui` | Herkunft der Anforderung |
| `td_hardware.py:315` | `trigger:radio_stop` | Präfix + Kommando |
| `td_nav.py:169` | Variable | wechselnd |
| `scanner.py` | `scanner` | Subsystem — früher ungültiges `reason=` (C7/W5 behoben) |

Früher öffnete `play_freq` die Transition wegen `TypeError` nie; das ist behoben.
Eigentümerstrings bleiben uneinheitlich — deshalb ist die Eigentümerprüfung (Z4)
weiterhin Stufe-3-Material.

### Z7 `dab_playback_state` ist ein totes Feld mit falschem Vertrag `[BELEGT]` — mittel

Deklariert in Zeile 41 mit dem Wertekommentar
`idle | starting | locked | no_lock | failed`. Es existiert **kein Setter** und keine
Zuweisung. `modules/radio/dab_play.py` schreibt den Zustand stattdessen nach `status.S`
— und dort zusätzlich die Werte `partial_sync`, `pcm_error` und `exception`, die im
Kommentar fehlen, während `failed` nie geschrieben wird.

Ein totes Feld, dessen Wertebereich verbindlich aussieht und falsch ist. Zwei Stellen
im WebUI prüfen gegen unvollständige Wertelisten (Befund S6 im WebUI-Auftrag).

### Z8 Zeitschranke ohne Bezug zur Operation `[BELEGT]` — mittel

`begin_transition(owner, target, timeout_s=STALE_TIMEOUT_S)` nimmt eine Zeitschranke —
**kein einziger Aufrufer übergibt sie.** Ein 0,2-Sekunden-Kanalwechsel und eine
BT-Kopplung bekommen dieselben 12 Sekunden.

Dauert eine legitime Operation länger, lässt der Override in Zeile 116-120 den nächsten
Eigentümer herein, während der erste noch arbeitet. Die Zeitschranke **erzeugt** dann
die Kollision, die sie verhindern soll.

### Z9 Kleinere Fundstellen `[BELEGT]` — niedrig

- `set_bt_link_state()` loggt in Zeile 216 mit der Beschriftung `bt_state` statt
  `bt_link_state` — beim Log-Lesen genau dann irreführend, wenn man dieses Subsystem
  untersucht.
- `get_bt_link_state()` (Z. 229) und `get_bt_audio_state()` (Z. 233) greifen ohne
  `_LOCK` zu, entgegen der Konvention aller anderen Lesefunktionen.
- `main_core.py:80`: `_time_mod.time() if "_time_mod" in dir() else 0.0` — `dir()` ohne
  Argument liefert innerhalb einer Funktion nur die **lokalen** Namen. Die Bedingung ist
  immer falsch, `started_ts` der Schicht 3 bleibt dauerhaft `0.0`; jede
  Altersberechnung darauf ist wertlos.
- `_write_state_file()` (Z. 74) protokolliert Schreibfehler, lässt den Zustand aber
  auseinanderlaufen: `STATE` im Speicher ist aktuell, die Datei nicht — und das WebUI
  liest nur die Datei.
- Jeder `set_*`-Aufruf schreibt die komplette JSON-Datei neu; keine Entprellung.

### Z10 Keine Übergangshistorie `[BEHOBEN v0.11.130 / Stufe 1]`

Ringpuffer der letzten Übergänge in `STATE` / Statusdatei;
`pidrivectl source history` listet sie. Zähler `transition_count` / `stale_cleared`
bleiben.

---

### Z11 Belegter Ausfall am Fahrzeug-Pi `[BEHOBEN v0.11.128 / C16]`

**War:** `td_hardware.py` Shadowing von `source_state` → `radio_stop`/Spotify tot.
**Jetzt:** Closure behoben; Abnahme in `docs/ABNAHMEN.md`.

---

## 7. Was tragfähig ist

Das Modul ist handwerklich sauberer als seine Nutzung:

- `RLock` statt `Lock` — Wiedereintritt aus verschachtelten Aufrufen ist abgedeckt.
- Atomares Schreiben über `os.replace()` — keine halben Dateien für die Leseseite.
- `source_previous` und `playback_epoch` sind sinnvolle, korrekt gepflegte Felder.
- `transition_count` und `stale_cleared` sind brauchbare Diagnosezähler.
- **Die richtige Aufrufform existiert schon im Repo** (`td_radio.py:96-101`,
  `td_nav.py:164-165`). Es braucht kein neues Muster, nur seine Anwendung.

---

## 8. Zielbild — gestuft

Entscheidung des Eigentümers (2026-09-15): **gestuftes Vorgehen.** Stufe 1 und 2 werden
umgesetzt, Stufe 3 später entschieden.

### Stufe 1 — Sichtbarkeit und Wahrheit (Z2, Z3, Z10) — ✅ erledigt v0.11.130

1. Aufrufstellen behandeln `begin_transition() == False` (Progress „Blockiert“).
2. `in_transition()` bereinigt abgelaufenen Zustand — Speicher und Datei gleich.
3. Periodischer Stale-Check in der Core-Hauptschleife.
4. Ringpuffer + `pidrivectl source state|history`.

Stufe 1 ändert **keine** Semantik der Quellenwechsel — sie macht nur sichtbar, was
passiert. Abnahme: `docs/ABNAHMEN.md`.

### Stufe 2 — Bluetooth als Quelle (Z1)

`bt` wird eine reguläre Quelle mit `commit_source("bt")`. Die Felder `bt_link_state`
und `bt_audio_state` bleiben als Detailzustand erhalten, verlieren aber ihre Rolle als
Ersatz-Quellenmodell. Voraussetzung dafür ist eine Festlegung, welcher Zustand
„BT ist die aktive Quelle" bedeutet — Verbindung allein genügt nicht, es braucht den
Audio-Pfad.

Diese Stufe ist die Vorarbeit für `esp32.bt-gateway`.

### Stufe 3 — später zu entscheiden

- Eigentümerprüfung in `end_transition()` — **setzt Z6 voraus**: erst braucht `owner`
  eine Konvention (Vorschlag: `subsystem:kommando`), dann ist die Prüfung möglich.
- Übergangstabelle mit erlaubten Wechseln und Validierung der Quellennamen.
- Zusammenführung der Sperrschichten 1–3 auf eine, und Anschluss der toten Schicht 4
  (RTL-SDR-`flock`, siehe Befund C2 im WebUI-Auftrag).
- Zeitschranken pro Operationstyp statt pauschal 12 Sekunden (Z8).
- `dab_playback_state` entweder mit Setter versehen oder entfernen (Z7).

---

## 9. Verweise

- [../auftraege/AUFTRAG-WEBUI-SANIERUNG.md](../auftraege/AUFTRAG-WEBUI-SANIERUNG.md)
  — Arbeitspaket W7, sowie die Befunde C1, C7 (Scanner) und S6, S7 (WebUI-Anzeige),
  die alle in diesem Modul wurzeln.
- [ARCHITECTURE.md](ARCHITECTURE.md) — Gesamtstruktur, IPC-Dateien.
- [RUNTIME_FLOWS.md](RUNTIME_FLOWS.md) — Laufzeitpfade der Quellenwechsel.
