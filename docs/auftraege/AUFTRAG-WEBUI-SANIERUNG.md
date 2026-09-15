# Arbeitsauftrag — WebUI-Sanierung, Scanner und FastScan

**Stand:** v0.11.127 · 2026-09-15

Adressat: Entwickler-Instanz am Repo `pidrive`.
Vorgänger: [AUFTRAG-MENUE-UND-GATEWAY.md](AUFTRAG-MENUE-UND-GATEWAY.md) (M0–M6 umgesetzt).

---

## 1. Anlass und Zielbild

Drei Beobachtungen des Eigentümers, alle im Code bestätigt:

1. Das WebUI hat **nie** den Status von PiDrive richtig angezeigt.
2. Bei der letzten Überarbeitung sind viele Funktionen weggefallen.
3. Der Scanner — ursprünglich gebaut, um Walkie-Talkie-Verkehr hörbar zu machen — ist
   nicht mehr verifizierbar, und der FastScan hat nie funktioniert.

Die statische Analyse hat für alle drei Punkte eindeutige Ursachen gefunden. Keiner der
Befunde ist eine Vermutung über Laufzeitverhalten; die tragenden Punkte sind mit
Datei und Zeile belegt.

**Das eigentliche Problem ist nicht die Menge der Fehler, sondern dass keiner davon
sichtbar wird.** Jeder einzelne kritische Befund steckt hinter einem stummen
`except: pass`, einem verschluckten Import oder einem Feld, das berechnet aber nicht
angezeigt wird. Ein `NameError`, der seit Wochen bei jedem Seitenaufruf auftritt,
erzeugt keine Log-Zeile und keine Fehlermeldung. Deshalb steht **W1 (Fehler sichtbar
machen) vor jeder inhaltlichen Reparatur** — sonst ist die nächste Regression genauso
unsichtbar wie diese.

Zielbild nach Abschluss:

- Das WebUI zeigt an, wenn der Core nicht läuft, statt alte Werte als frisch auszugeben.
- Kein Button führt ins Leere; ein statischer Test beweist das bei jedem Commit.
- Der Scanner ist ohne Fahrzeug über die CLI verifizierbar, inklusive Squelch-Öffnung.
- Der FastScan liefert eine nicht-leere, plausible Senderliste.

---

## 2. Belegstufen

Die Befunde sind unterschiedlich hart. Die Kennzeichnung ist verbindlich, weil sie
bestimmt, ob vor der Korrektur gemessen werden muss:

| Stufe | Bedeutung | Vorgehen |
|-------|-----------|----------|
| `[BELEGT]` | Im Quellcode nachgelesen und bestätigt | direkt korrigierbar |
| `[ANALYSE]` | Aus der Codeanalyse abgeleitet, plausibel, nicht zweitgeprüft | vor Korrektur kurz gegenlesen |
| `[MESSEN]` | Aussage über Funkverhalten (SNR, Squelch, Burst-Erfassung) | **nur** mit Hardware entscheidbar |

`[MESSEN]`-Punkte dürfen nicht „auf Verdacht" umparametriert werden. Sie brauchen
eine Vorher-Messung, sonst ist der Erfolg der Änderung nicht feststellbar.

---

## 3. Befunde — Statuskette

### S1 Aktualität wird berechnet, aber nirgends angezeigt `[BELEGT]` — kritisch

`web/app.py:278-280` liefert unter `/api/core` → `debug` die Felder `core_ready`,
`status_age` und `menu_age`. **Kein aktives Template liest sie.** Die Felder kommen nur
in `index_legacy.html`, `index_full.html` und `legacy/index_legacy.html` vor — keine
Route rendert diese Dateien.

`web/shared/files.py:10-17` (`read_json`) liefert bei fehlender oder defekter Datei
stumm `{}`. Bei vorhandener, aber veralteter Datei liefert es die alten Werte ohne
Markierung. `/tmp/pidrive_status.json` wird von tmpfs erst beim Reboot gelöscht.

**Folge:** Steht der Core, zeigt das WebUI den letzten Zustand vor dem Absturz
unbegrenzt als aktuell an — Sender, Lautstärke, BT-Gerät, DAB-Zustand. Es gibt keine
„Core offline"-Anzeige, obwohl `systemd/pidrive_web.service:6` genau das als Designziel
kommentiert. **Das ist die Hauptursache für „hat den Status nie richtig angezeigt".**

### S2 Der Core-Age-Indikator misst die Request-Zeit `[BELEGT]` — kritisch

`base.html:198` rechnet `Date.now()/1000 - j.ts`. `j.ts` ist `time.time()` im
Flask-Request (`app.py:268`), also die Uhrzeit der Anfrage — nicht die Änderungszeit der
Statusdatei. Der Wert wird bei jedem Poll neu gesetzt und ist deshalb **immer** ~0.0s,
auch bei totem Core.

Zweiter Fehler in derselben Zeile: `Date.now()` ist die Browser-Uhr, `j.ts` die Pi-Uhr.
Ein Pi ohne RTC startet im Auto auf falschem Datum, bis NTP greift — das ergibt
Anzeigen wie `Core -3847.2s`.

### S3 `processes` wird gelesen, aber nie geschrieben `[BELEGT]` — hoch

`status.py:162-166` befüllt die Prozessliste alle 5s. `ipc.write_status()` exportiert
das Feld nicht — in `ipc.py` kommt der Name `processes` überhaupt nicht vor. Gelesen wird
es trotzdem in `app.py:378` und `web/shared/view_model.py:212`.

**Folge:** Die Prozessliste ist dauerhaft leer. Man kann nicht sehen, ob `welle-cli`,
`rtl_fm` oder `mpv` läuft — genau die Information, die man beim Scanner-Debugging braucht.

### S4 Fünf Seiten haben keinen Refresh-Hook `[ANALYSE]` — hoch

`base.html:239` ruft `onBaseRefresh(...)` alle 1200ms. Definiert ist der Hook nur in
`index.html:450`, `bluetooth.html:144` und `audio.html:30`. Ohne Hook:
`rf-tools.html`, `diagnostics.html`, `avrcp.html`, `webradio-admin.html`,
`music-admin.html`.

**Folge:** Auf `/rf-tools` und `/avrcp` wird der Seiteninhalt einmal beim Laden befüllt
und dann nie wieder. Die Schnellstatus-Leiste oben aktualisiert — der Seiteninhalt
zeigt eingefrorene Werte, die wie Live-Daten aussehen. Das ist schlimmer als eine
leere Anzeige, weil es nicht auffällt.

### S5 Log-Viewer liest nicht existierende Felder `[ANALYSE]` — hoch

`/api/logs` (`app.py:417-439`) liefert `safe_run()`-Ergebnisse, also
`{ok, code, stdout, stderr, cmd}`. Gelesen werden `j.lines`, `j.log`, `j.text`
(`diagnostics.html:45`) bzw. `j.output` (`:51`, `:68`) und in `avrcp.html:23`.

**Folge:** `/diagnostics` zeigt statt Logs einen rohen JSON-Dump mit escapten
Zeilenumbrüchen, `/avrcp` ein leeres Log-Feld.

### S6 `dab_playback_state`: geschriebene und erwartete Werte weichen ab `[ANALYSE]` — mittel

Geschrieben (`modules/radio/dab_play.py`): `idle`, `partial_sync`, `locked`,
`pcm_error`, `starting`, `no_lock`, `exception`.
`base.html:216` zeigt den Chip nur für `no_lock`, `partial_sync`, `starting`, `locked`,
`pcm_only` — `pcm_only` wird nie geschrieben, `pcm_error` und `exception` fehlen in der
Liste. `index.html:480` blendet aus bei `playing`, `locked`, `pcm_seen` — `playing` und
`pcm_seen` werden nie geschrieben, dafür `idle`.

**Folge:** DAB-Abbrüche werden nicht signalisiert; im Normal-Leerlauf erscheint
stattdessen der Rohtext „idle" in Warnfarbe.

### S7 Dreistufiges BT-Icon aus dem falschen Feld `[ANALYSE]` — mittel

`ipc.py:75` schreibt `bt_on` mit dem Kommentar „Adapter-UP (dreistufiges BT-Icon)".
`base.html:189` liest aber `st.bt` und `st.bt_device`. Da `status.py:91` bei
verbundenem Gerät immer auch `bt_device` setzt, ist der `bt-on`-Zweig unerreichbar und
die CSS-Klasse `.flag.bt-on` (`css/layout.css:35`) nie aktiv. `bluetooth.html:140`
macht es richtig.

### S8 Throttling-Warnung meldet dauerhaft „OK" `[ANALYSE]` — mittel

`app.py:934-940` schreibt `disk_used`, `disk_avail`, `disk_pct`, `disk_warn`.
`diagnostics.html:59` liest `d.disk_total` (existiert nicht), `:60` liest `d.throttled`
— existiert ebenfalls nicht und wird dadurch **immer grün als „OK"** dargestellt.
Bei Unterspannung im Fahrzeug ist das die falsche Aussage am falschen Ort.

### S9 `/api/state` ist teuer und wird vierfach parallel gerufen `[ANALYSE]` — mittel

`build_view_model()` ruft `get_audio_debug()`, das bis zu 8 `pactl`-Subprozesse mit
`timeout=15` startet. Auf `/` rufen `loadFavorites()`, `loadDABStations()`,
`loadWebStations()` und `loadFMStations()` jeweils separat `/api/state`.

Aktuell durch S11 maskiert — die Subprozesse laufen wegen des `NameError` gar nicht an.
**Sobald S11 behoben ist, tritt das voll zutage.** Diese Reihenfolge ist einzuhalten:
S9 vor oder gleichzeitig mit S11.

### S10 `api-core.js` ist syntaktisch ungültig `[BELEGT]` — hoch, aber nicht die Ausfallursache

`web/static/js/api-core.js:42`:

```js
if (!r.ok) throw new Error(\`HTTP \${r.status}: \${url}\`);
```

Die Backslashes vor Backtick und `${` sind außerhalb eines Strings ungültig. Die Datei
wird beim Parsen **komplett** verworfen, inklusive `const PiDriveAPI = {...}` aus
Zeile 4. `base.html:102` bindet sie auf jeder Seite ein.

**Einordnung, die vom ursprünglichen Analysebefund abweicht:** `PiDriveAPI` wird
ausschließlich von `page-index.js` benutzt, und die Datei wird von keinem Template
geladen. Der Syntaxfehler bricht also **keine** derzeit funktionierende Anzeige — er
bedeutet, dass die gemeinsame JS-Schicht der letzten Überarbeitung nie gelaufen ist.

### S11 `web/shared/audio.py` ruft `safe_run` ohne Import `[BELEGT]` — kritisch

Die Datei importiert `json`, `os`, `subprocess` und die Konstanten. `safe_run` lebt in
`web/shared/system.py:35` und wird nie importiert — bei **11 Aufrufstellen**. Jeder
Aufruf wirft `NameError`, jeder steckt in einem stummen `except`.

**Folge:** `get_audio_debug()` liefert immer das leere Skelett (`pulse_active: false`,
`sinks: []`, `current_volume: "–"`). Das Audio-Debug-Cockpit auf `/audio`, `/api/audio`,
`/api/volume` und `vm.audio_debug` sind dauerhaft leer. Keine Fehlermeldung, kein Log.

### S12 `web/shared/view_model.py` nutzt `sys` ohne Import `[BELEGT]` — kritisch

Importiert werden `json`, `os`, `time` — `sys.path` wird in Zeile 145, 146, 155 und 156
benutzt. Der `NameError` wird gefangen und **als Datenobjekt zurückgegeben**.

**Folge:** `vm.dab_scan_debug` und `vm.spectrum_debug` enthalten konstant
`{"error": "name 'sys' is not defined"}`. Genau dieser String wird in der RF-Tools-Karte
„DAB Scan Diagnose" als JSON angezeigt.

### S13 Gemeinsame Ursache von S11 und S12 `[BELEGT]` — Erkenntnis, kein eigener Fehler

`pidrive/web/shared.py` und das Paket `pidrive/web/shared/` existieren gleichzeitig.
Python bevorzugt das Paket, `shared.py` ist vollständig toter Code. In der toten Datei
sind `safe_run` (Z. 118) und der `sys`-Import (Z. 19) vorhanden — **beim Zerlegen in das
Paket gingen genau diese zwei Imports verloren.**

Das erklärt, warum es „nach der letzten Überarbeitung" schlechter wurde. Die tote Datei
ist zusätzlich eine Wartungsfalle: ihr `ALLOWED_COMMANDS` ist älter und kennt
`vol_set`, `scanner_stop`, `favorites_play`, `favorites_add` nicht. Wer dort etwas
korrigiert, ändert nichts am laufenden System.

---

## 4. Befunde — verlorene Funktionen und tote Schichten

### V1 Die modulare JS-Schicht existiert nur auf dem Papier `[BELEGT]`

Sieben `page-*.js`-Dateien, davon sechs 8-Zeilen-Stubs mit
`// TODO: Seitenspezifische Initialisierung hier`. `page-index.js` ist die einzige mit
Inhalt — und wird von keinem Template geladen, weil `index.html:450` sein eigenes
`onBaseRefresh` inline definiert. Dazu ein Wrapper (`api-core.js`), der nicht parst.

`page-index.js` wäre bei Einbindung außerdem defekt: es liest `st.radio_playing`
(nie geschrieben — `ipc.py:82` schreibt `radio`), ruft `/api/favorites` (Route existiert
nicht) und adressiert Element-IDs, die nur in `index_legacy.html` vorkommen.

**Achtung bei der Bereinigung:** Würde `page-index.js` eingebunden, überschreibt seine
`DOMContentLoaded`-Zuweisung an `window.onBaseRefresh` die funktionierende
Funktionsdeklaration aus `index.html` und legt die Player-Anzeige komplett tot.
Die Datei darf nicht „testweise" aktiviert werden.

### V2 Etwa 18 backend-gestützte Funktionen sind aus der Oberfläche verschwunden `[ANALYSE]`

Beim Umbau von `index_legacy.html` auf `index.html` entfielen unter anderem:
Menü-Fernsteuerung, Audio-Debug-Cockpit, DAB-Scan-Diagnose, Spektrum-Analyzer,
FastScan, Systemdiagnose. **Die Backends existieren alle noch und sind erreichbar** —
es fehlt nur die Bedienoberfläche.

### V3 Die Menü-Fernsteuerung ist fast geschenkt `[BELEGT]` — höchster Nutzen pro Aufwand

`/api/core` liefert bereits den vollständigen Menüzustand: `path`, `nodes`, `cursor`,
`rev`, `can_back`, `categories`, `items` (`app.py:253-267`). `base.html` liest davon
schon `j.path` und `j.rev` für die Debug-Zeile.

Es braucht also **kein neues Backend** — nur wieder eine Oberfläche. Zusammen mit der
kopflosen Menü-API aus M2 ist das der schnellste Weg, das Menü ohne Fahrzeug bedienbar
und prüfbar zu machen. Das ist zugleich die Vorarbeit für `esp32.bt-gateway`.

### V4 Buttons, die ins Leere führen `[ANALYSE]`

| Stelle | Kommando/Route | Problem |
|---|---|---|
| `index.html:186-187` | `prev_station`, `next_station` | nicht in `ALLOWED_COMMANDS`; heißen dort `fm_prev`/`fm_next`/`dab_prev`/`dab_next` → HTTP 400 |
| `rf-tools.html:38` | `sendCmd('/api/ppm_calibrate')` | schickt einen URL-Pfad als Trigger-Kommando → verworfen |
| `rf-tools.html:35` | `vm.get('settings')` | Schlüssel existiert im ViewModel nicht → PPM zeigt immer den Default |
| `page-index.js:9` | `/api/favorites` | Route existiert nicht (Favoriten kommen über `/api/state`) |

### V5 Pfadfehler, die still „Erfolg" melden `[ANALYSE]`

- `app.py:479`: `_rtl_py = BASE_DIR / "modules" / "rtlsdr.py"` — die Datei liegt unter
  `modules/radio/rtlsdr.py`. Der Subprozess scheitert, der Endpunkt antwortet
  `{"ok": true}`.
- `app.py:459`: `/api/grep` zielt auf `BASE_DIR / "pidrive"` — verdoppelt das
  Pfadsegment, das Verzeichnis existiert nicht.

### V6 Blueprint-Import in `try/except` `[ANALYSE]`

`app.py` kapselt die Blueprint-Registrierung in ein `try/except`. Ein Importfehler in
einer der Dateien `routes_audio|bt|dab|music|webradio.py` nimmt still fünf
Routengruppen mit — die Seiten laden weiter, nur alle Aktionen liefern 404.
Angesichts von S11/S12 ist das kein theoretisches Risiko.

---

## 5. Befunde — Scanner

### C1 Der Suchlauf bricht bei jedem Aufruf in der ersten Iteration ab `[BELEGT]` — kritisch

`trigger/td_scanner.py:94-96` öffnet eine `source_state`-Transition und startet den
Scan **darin**:

```python
if source_state.begin_transition(f"scan_next:{b}", "scanner"):
    try:
        scanner.scan_next(b, S, settings)
```

`modules/radio/scanner.py:630-635` prüft genau diesen Zustand als Abbruchbedingung —
in der ersten Iteration der Kanalschleife:

```python
for _ in range(n):
    if (_scan_abort
            or (_src_state and _src_state.in_transition())
            or S.get("radio_type") not in ("", "SCANNER")):
        return None
```

`in_transition()` liefert 12 Sekunden lang `True` (`source_state.py:25`,
`STALE_TIMEOUT_S = 12.0`). `_src_state` ist hier **nicht** `None` —
`modules/source_state.py` existiert und td_scanner benutzt dasselbe Modulobjekt.
Identisch in `_scan_range` (`scanner.py:668-672`) und für `scan_prev`.

**Folge:** `scan_next`/`scan_prev` starten **kein einziges `rtl_fm`**, schreiben
`found: false` und die CLI meldet „✗ Kein aktiver Kanal gefunden". Das ist die direkte,
vollständige Erklärung für „konnte ich nicht mehr verifizieren".

### C2 Der Importbruch bei `modules/rtlsdr` und `modules/spectrum` `[BELEGT]` — kritisch

`pidrive/modules/rtlsdr.py` und `pidrive/modules/spectrum.py` **existieren nicht** —
nur `modules/radio/rtlsdr.py` und `modules/radio/spectrum.py`. Sechs Stellen importieren
trotzdem den alten Pfad und verschlucken den Fehler:

| Datei | Zeile |
|---|---|
| `modules/radio/dab_helpers.py` | 11 |
| `modules/radio/fm.py` | 18 |
| `modules/radio/rtlsdr.py` | 17 |
| `modules/radio/scanner.py` | 24, 34 |
| `modules/radio/spectrum.py` | 33 |

`from modules.radio import rtlsdr` setzt das Attribut auf dem Paket `modules.radio`,
nicht auf `modules` — der alte Import kann also nie gelingen.

**Folge:** `_rtlsdr` und `_spectrum` sind immer `None`. Damit entfallen: USB-Prüfung
(`scanner.py:313`), **Busy-Check und flock-Lock** (`:389-399`), `stop_process()`
(`:437-441`), Prozess-Tracking (`:411-413`) — und der komplette FFT-Pfad
(`_scan_list_spectrum`, `scanner.py:571-579`), inklusive der einzigen Stelle, die eine
Haltezeit nach Signalende implementiert. Der WebUI-Schalter `scanner_use_spectrum` ist
wirkungslos.

Die gesamte Lock-Infrastruktur in `rtlsdr.py:300-415` ist toter Code. DAB, FM und
Scanner konkurrieren unkoordiniert um den einen Stick; als einziger Schutz bleibt
`pkill -f rtl_fm`. `docs/archiv/MIGRATION_BACKLOG.md:51-56` behauptet, diese Umstellung
sei abgeschlossen.

> **Risiko bei der Korrektur — bitte nicht unterschätzen:** Diese sechs Zeilen zu
> reparieren ist keine Kosmetik. Es **aktiviert eine Sperrschicht, die noch nie im
> Betrieb gelaufen ist.** Danach können DAB, FM und Scanner sich gegenseitig
> verweigern, wo sie sich vorher stillschweigend überfahren haben. Die Änderung gehört
> in einen eigenen Commit mit anschließendem Quellenwechsel-Test (R5), nicht in ein
> Sammel-Refactoring.

### C3 Die Demod-Bandbreite ist um den Faktor 16 zu breit `[BELEGT]` / Wirkung `[MESSEN]`

`scanner.py:360`: `_rtl_sr = max(200000, int(bandwidth_hz) * 4)`.

Für PMR446 (`bw: 12500`), Freenet, LPD433, CB (`bw: 10000`) und VHF/UHF (`bw: 25000`)
ergibt das **immer** `-s 200000`. `rtl_fm` demoduliert dann 200 kHz für einen
12,5-kHz-Kanal, und die Squelch-Schwelle `-l` arbeitet auf der Breitband-RMS.

Der SNR-Verlust und das Squelch-Verhalten sind `[MESSEN]` — dass die Bandbreite nicht
zum Kanalraster passt, ist `[BELEGT]`. Erwartung: auch ein korrekt gefundener Kanal ist
nicht brauchbar hörbar. **Vor der Änderung eine Referenzaufnahme machen**, sonst ist die
Verbesserung nicht belegbar.

### C4 Das Detektionsfenster ist kürzer als die Anlaufzeit von `rtl_fm` `[ANALYSE]`/`[MESSEN]` — hoch

`_detect_signal_fast` (`scanner.py:473-486`) nutzt `timeout 0.40s`. `rtl_fm` braucht für
USB-Open, PLL-Tune und Puffer-Vorlauf typischerweise 0,5–1,5 s. Das Projekt selbst messt
an anderen Stellen mit 1,5 s (`fm.py:407`) bzw. 5 s (`rtlsdr.py:445`).

Erwartung: die Vorprüfung liefert auch bei starkem Signal 0 Bytes. **Diese Zeit ist auf
der Zielhardware zu messen, nicht zu schätzen** — sie bestimmt direkt die Sweep-Dauer.

### C5 VHF/UHF-Sweeps laufen über jedes Timeout und haben Abtastlücken `[ANALYSE]` — hoch

`step_fast = 0.1` MHz ergibt 380 Schritte für VHF (136–174 MHz) und 700 für UHF
(400–470 MHz), pro Schritt mindestens ein `rtl_fm`-Start → mehrere Minuten. Der
CLI-Watcher bricht nach 150 s ab (`cli/service.py:589`) und meldet immer Timeout.
Zusätzlich ist `fast_bw` dort nur 50 kHz bei 100-kHz-Schritt — **die Hälfte des Bands
wird nie abgetastet.**

### C6 Es gibt keinen fortlaufenden Scan und keine Haltezeit `[BELEGT]` — hoch

`scan_next` (`scanner.py:904`) ist ein Einmal-Durchlauf: bei Treffer wird getunt, dann
endet die Funktion. Es existiert kein Thread und keine Schleife, die nach Trägerabfall
weitersucht.

**Ein „Scanner" im funktechnischen Sinn — durchlaufendes Absuchen, Aufschalten, nach
Signalende weiterlaufen — ist nicht implementiert.** Das ist der eigentliche
Funktionswunsch, und es ist ein Neubau, keine Korrektur. Der Zustandsautomat dafür
existiert in `spectrum.py:460-536`, ist aber über C2 nicht erreichbar.

> **Zuschnitt (E2):** Der Eigentümer hat entschieden, dass ein **Einzelscan genügt**.
> C6 ist damit dokumentiert, aber **nicht beauftragt**. Der Befund bleibt hier stehen,
> damit er bei einer späteren Erweiterung nicht neu erarbeitet werden muss.

### C7 Transitions-Handhabung ist fehlerhaft `[ANALYSE]` — mittel

- `scanner.py:320` ruft `begin_transition("scanner", reason="user_select")`; die
  Signatur ist `begin_transition(owner, target, timeout_s)` (`source_state.py:100`) und
  kennt kein `reason`. Der `TypeError` wird verschluckt.
- `stop()` setzt `_scan_abort = True` und ruft `end_transition()` (`:461-465`).
  `play_freq` ruft `stop(S)` (`:324`) — jedes Tunen beendet also die von td_scanner
  geöffnete Transition, die dann in `td_scanner.py:99-100` ein zweites Mal geschlossen
  wird.

### C8 Falsche Kanaldaten `[ANALYSE]` — mittel

- **CB-Nummerierung:** `CB_CHANNELS` (`scanner.py:63-108`) listet erst 41–80, dann 1–40.
  `set_channel` rechnet über den Listenindex (`:829-831`) — `scanner cb ch 1` landet auf
  „CB Kanal 41" bei 26.565 MHz.
- **CB nur FM:** `BANDS["cb"]` kennt keinen Modulationsmodus, `play_freq` wählt für
  alles unter 150 kHz `-M fm` (`:362`). CB-AM auf den Kanälen 1–40 ist nicht hörbar.
- **Freenet unvollständig:** 4 statt 6 Kanäle — 149.10000 und 149.11250 MHz fehlen
  (`:50-55`, ebenso `spectrum.py:198-203`).

### C9 Squelch-Änderung greift bei den Kanalbändern nicht `[ANALYSE]` — mittel

`td_scanner.py:228-234` ruft `scanner.set_freq(band, …)`. `set_freq` (`:879-883`) bricht
ab, wenn das Band nur `channels` und kein `band`-Dict hat — das trifft auf pmr446,
freenet, lpd433 und cb zu. Ein neuer Squelch wirkt nur bei VHF, UHF und FM. Genau die
Bänder, um die es geht, sind ausgenommen.

### C10 WebUI-Einstellungen erreichen den laufenden Core nicht `[ANALYSE]` — mittel

`app.py:636` schreibt `settings.json`. `main_core.py:592/596` lädt die Settings
**einmalig** beim Start; ein Reload im Hauptloop existiert nicht. `scanner_squelch`,
`scanner_gain` und `scanner_use_spectrum` wirken erst nach Core-Neustart. Nur der
Trigger `set_scanner_squelch:` aktualisiert das Live-Dict.

Nebenbefund — drei verschiedene Defaults: `settings.py:47` = 25,
`config/settings.json:16` = 10, WebUI-Slider = 50 bei Bereich 0–100
(`index.html:293-296`).

### C11 Scanner-Status ist nicht abfragbar `[ANALYSE]` — hoch für die Verifikation

`cli.py:1301` liest `r["scanner"]` aus `pidrive_status.json` — **kein Producer schreibt
diesen Schlüssel.** `pidrivectl scanner` ohne Argument meldet immer „Scanner: inaktiv".

Damit fehlt genau das, was zum Verifizieren nötig wäre: eine Anzeige, ob der Squelch
öffnet, auf welcher Frequenz, mit welcher Bytemenge. Zusammen mit S3 (leere
Prozessliste) ist der Scanner blind bedienbar, aber nicht beobachtbar.

### C12 Tote Prüfungen und ungenutzte Variablen `[ANALYSE]` — niedrig

`is_rtlsdr_available()`, `is_rtlfm_available()` und `check_hardware()`
(`scanner.py:288-305`) haben keinen Aufrufer. Fehlt `rtl_fm`, läuft `Popen` in einen
`FileNotFoundError`, der als Log-Zeile endet — ohne Meldung an die Oberfläche.
Ebenfalls unbenutzt: `_detect_signal`, `_freq_input`, `sr`, `_sc`, `_ppm_arg`,
`_gain_arg`, `_sq_arg`, `_sc_mpv_env`, `_sc_mpv_prefix`.

Das `pkill`-Muster (`:445`) nennt `--really-quiet`, gestartet wird mit `--no-terminal`
(`:376`) — greift nur dank der breiteren Regel in `:443`.

### C13 PMR446 und LPD433 werden im Menü nie als aktiv markiert `[ANALYSE]` — niedrig

`menu_builder.py:270-273` prüft `band_id.upper() in S["radio_station"].upper()`. Die
Labels lauten „PMR Kanal 3 (446.03125 MHz)" bzw. „LPD K01" — die Strings „PMR446" und
„LPD433" kommen darin nicht vor.

### C14 Der Scan-Startindex ist bandübergreifend `[ANALYSE]` — niedrig

`_scan_list` liest und schreibt den globalen Schlüssel `scan_idx` (`:626`, `:647`). Nach
einem PMR446-Scan startet der CB-Scan an dessen Index.

### C15 Klarstellung: `modules/scanner.py` ist harmlos `[BELEGT]`

Die Datei ist ein 5-Zeilen-Compat-Shim, der sich selbst in `sys.modules` durch
`modules.radio.scanner` ersetzt. Es gibt **keinen** inhaltlichen Zweitcode. Nur die Doku
driftet: `MIGRATION_BACKLOG.md:36` behauptet, die Datei sei gelöscht.

Nicht zu verwechseln mit C2 — dort fehlen die Dateien wirklich.

### C16 Lokaler Import legt `source_state` in `td_hardware` lahm `[BELEGT]` — kritisch

**Am Fahrzeug-Pi nachgewiesen.** `pidrivectl test all` vom 2026-09-15 12:11 meldet:

```
✗ annot access free variable 'source_state' where it is not associated
  with a value in enclosing scope
```

Ursache: `trigger/td_hardware.py` importiert `source_state` in Zeile 13 modulweit —
und in **Zeile 383** ein zweites Mal *innerhalb* der Funktion:

```python
elif cmd == "library_stop":
    from modules import local_player as _lp
    from modules import source_state        # ← Zeile 383
```

Die Datei enthält genau **eine** Funktion, `handle()` in Zeile 20. Eine Zuweisung an
`source_state` irgendwo in dieser Funktion macht den Namen für den **gesamten**
Funktionskörper lokal. Der modulweite Import aus Zeile 13 ist damit unerreichbar.

Betroffen sind alle Zugriffe in `handle()`:

| Zeile | Kontext | Wirkung |
|---|---|---|
| 42 | in `_spotify_toggle()` | Spotify **aus** → Fehler, kein `commit_source("idle")` |
| 73 | in `_spotify_toggle()` | Spotify **ein** → Fehler, Quelle wird nie `spotify`, `radio_playing` bleibt `False` |
| 315, 332, 334, 351 | in `_radio_stop()` | `radio_stop` bricht in Zeile 315 ab — **nichts wird gestoppt** |
| 388 | direkt in `handle()` | funktioniert, weil Zeile 383 unmittelbar davor läuft |

**Sichtbare Fehlfunktion:** Der Stop-Befehl stoppt nicht. Webradio, DAB, FM und Scanner
laufen weiter, die Metadaten werden nicht geleert, und die Quelle bleibt auf dem alten
Wert stehen. Spotify startet, wird aber nie als aktive Quelle registriert. Da beides in
`bg()`-Threads läuft, landet die Ausnahme im Log statt im Vordergrund — und dort sieht
sie niemand.

**Korrektur:** Zeile 383 löschen. Eine Zeile.

**Vorgezogen:** Das gehört in W1, nicht in W5 — es ist ein akuter Funktionsausfall und
zugleich der Beweis für die Kernaussage dieses Auftrags.

**Die anderen lokalen Imports sind geprüft und unkritisch.** Entscheidend ist nicht, ob
ein Modul doppelt importiert, sondern **welcher Name gebunden wird**:

| Stelle | Anweisung | Gebundener Name | Bewertung |
|---|---|---|---|
| `trigger/td_hardware.py:383` | `from modules import source_state` | `source_state` | **fehlerhaft** — kollidiert mit Zeile 13 |
| `trigger/td_radio.py:287` | `import modules.source_state as _sst_fm` | `_sst_fm` | unkritisch |
| `modules/audio.py:97` | `… as _src_state` | `_src_state` | unkritisch |
| `modules/webradio.py:109` | `… as _ss_wr` | `_ss_wr` | unkritisch |
| `modules/radio/dab_helpers.py:15` | `… as _src_state` | `_src_state` | unkritisch |
| `modules/radio/dab_play.py:170` | `… as _sst` | `_sst` | unkritisch |
| `modules/radio/scanner.py:29` | `… as _src_state` | `_src_state` | unkritisch |
| `diagnose.py:700` | `from modules.source_state import load_snapshot_file, snapshot` | nur die zwei Funktionen | unkritisch |

Nur `td_hardware.py:383` bindet den nackten Namen `source_state` lokal. Als Regel für
`pidrivectl webui check` bzw. einen Lint-Schritt: **ein funktionslokaler Import, der
denselben Namen bindet wie ein modulweiter Import derselben Datei, ist immer ein
Fehler.** Diese Prüfung ist statisch und billig — und sie hätte diesen Ausfall sofort
gefunden.

---

## 6. Befunde — FastScan und Spektrum

**Einordnung:** FastScan ist nicht halbfertig. Backend, Endpunkte und Persistenz sind
vollständig gebaut und korrekt verdrahtet; `install.sh:151/184/1008` installiert und
prüft `rtl-sdr` und `numpy`. **Es ist an drei Stellen falsch parametriert** — und die
Fehler sind so gebaut, dass das Ergebnis per Konstruktion leer bleibt.

### F1 `min_hits` ist arithmetisch unerreichbar `[BELEGT]` — kritisch

`spectrum.py:911`: `min_hits = max(1, int(len(centers) * 0.3))`

Bei den Defaults 87,5–108,0 MHz mit 1,0-MHz-Schritt entstehen 21 Fenster →
`min_hits = int(21 * 0.3) = 6`. Bei `sample_rate_hz = 2048000` deckt ein Fenster
±1,024 MHz ab; bei 1,0-MHz-Schritt liegt jede Frequenz in genau 2, höchstens 3 Fenstern.

**`hits ≤ 3 < 6` — `candidates` ist immer leer.** Die UI zeigt konsequent
„✓ 0 bestätigt, N schwach". Und weil `get_confirmed_stations` (`:819-824`) genau dieses
bereits gefilterte Feld liest, liefert `/api/spectrum/stations` **immer** eine leere
Liste, unabhängig vom übergebenen `min_hits`.

Die Korrektur muss `min_hits` aus der tatsächlichen Fensterüberlappung ableiten
(`sample_rate / step`), nicht aus der Fensteranzahl.

### F2 Auflösung und Peak-Suche passen nicht zum Messziel `[ANALYSE]` — kritisch

`capture_spectrum` rechnet **eine** FFT über alle Samples (`:858`). Bei
`sample_count = 131072` sind das 65 536 Bins, im Snapshot mit Default 262144 sogar
131 072 → `bin_hz ≈ 15,6 Hz`. `_find_peaks` (`:788`) sucht lokale Maxima über
`mean + 8 dB` mit `min_distance_bins = 8` ≈ 125 Hz, maximal 20 Peaks.

Ein FM-Rundfunksender ist 200 kHz breit — in dieser Auflösung kein Peak, sondern ein
Plateau aus tausenden Bins. Die 20 „Peaks" sind Rauschspitzen darauf, ihre Frequenz
streut über den ganzen Sender, und `_dedupe_peaks` verteilt sie auf mehrere
0,1-MHz-Buckets. **Das zersplittert die `hits` zusätzlich und verschärft F1.** Eine
Mittelung über Zeit gibt es nicht — es ist ein einzelner 32–64-ms-Schnappschuss.

Sinnvoll sind Bin-Breiten um 10–25 kHz, also FFTs von 128–256 Bins über 2,048 MHz,
gemittelt über viele Blöcke (Welch), statt einer 131 072-Punkt-FFT über einen
Einzelschuss. Das löst F8 (Antwortgröße) und F9 (Laufzeit) mit.

### F3 `band=pmr446|freenet` endet immer im Fehler `[BELEGT]` — hoch, billigste Korrektur

`app.py:699-701` liest `result.watch_seconds`. `DetectionResult` (`spectrum.py:148-157`)
hat dieses Feld **nicht** — nur `watch_started_ts` und `watch_ended_ts`. Zusätzlich wird
in Zeile 699 eine Liste von `PeakCandidate`-Dataclasses direkt an `jsonify` übergeben,
was ebenfalls scheitert.

Beides landet im `except` (`app.py:719-720`) und liefert
`{"ok": false, "error": "'DetectionResult' object has no attribute 'watch_seconds'"}` —
**nachdem** der Stick bereits 2,5 s belegt war. Betroffen: „Einmal messen (PMR446)" und
die Analyzer-Modi pmr446/freenet.

**Das sind zwei Zeilen. Danach liefert der PMR446-Pfad erstmals überhaupt eine
Antwort.** Damit anfangen.

### F4 Die reale Beobachtungszeit liegt im Millisekundenbereich `[ANALYSE]`/`[MESSEN]` — hoch

`watch_channels` (`:554`) läuft `watch_seconds = 2.5` und ruft pro Frame `capture_iq`,
das **jedes Mal einen neuen `rtl_sdr`-Prozess startet** (`:295-309`). Angefordert werden
`max(20480, fft_size*2)` Samples, aber `compute_frame` schneidet auf `self.fft_size` ab
(`:356`) — und das ist 512 (`_DEFAULT_FFT_SIZE:694`).

Also **512 von 20 480 Samples ≈ 2 ms Signal pro Frame, der Rest wird verworfen.** Bei
0,7–1,5 s Prozess-Overhead bleiben in 2,5 s etwa 2–3 Frames, zusammen ~6 ms
Beobachtung. Ein Sprechfunk-Burst wird so praktisch nie erfasst.

Nebenbei: `profile.fft_size = 2048` (`:181`) wird nur für `sample_count` und das
Debug-JSON verwendet, nicht für die FFT — das gespeicherte `fft_size` ist falsch.

### F5 Der DC-Offset erzeugt permanente Falschtreffer `[ANALYSE]` — hoch

`compute_center_for_channels` (`:239-242`) legt die Mitte auf **446,0500 MHz** (PMR)
bzw. **149,05625 MHz** (Freenet) — genau dort sitzt der DC-/LO-Spike des RTL-SDR.
`map_channel_bins` (`:409-423`) nimmt Bins inklusiv, und 446,0500 ist exakt die
gemeinsame Grenze von Kanal 4 und Kanal 5.

**Folge:** PMR 4/5 bzw. Freenet K3 werden permanent als „aktiv" gemeldet. Korrektur:
Mitte um eine halbe Kanalbreite versetzen.

### F6 Kein Ressourcenschutz gegen laufendes DAB/FM `[BELEGT]` — hoch

`spectrum.py:33` ist dieselbe Bruchstelle wie C2. Die Busy-Prüfungen in
`capture_spectrum` (`:829-834`) und `RTLSDRBackend.capture_iq` (`:284-292`, inklusive
`wait_until_free`) werden komplett übersprungen. Ein Sweep startet 21 Mal `rtl_sdr` auf
dem Stick, während DAB oder FM läuft — beide Seiten scheitern.

### F7 Der „Snapshot"-Button startet einen vollen Sweep `[ANALYSE]` — mittel

`captureSpectrum()` (`index_legacy.html:1652-1656`) sendet weder `mode` noch
`center_mhz`. `app.py:664` setzt `mode = args.get("mode", "fm_sweep")` — Default ist
**fm_sweep**; und `app.py:716` liest `center_mhz`, nicht `center`. Der Button startet
also einen 21-Fenster-Sweep bei vollständig ignoriertem Eingabefeld, wartet blind 35 s
und rendert dann `c.power_db`, ein Feld, das der fm_sweep-Output nicht hat (dort `db`).
Der neuere Analyzer schickt `sample_rate_hz`, das `app.py:717` nicht durchreicht.

### F8 Antwortgröße `[ANALYSE]` — mittel

Im Snapshot-Modus enthält das Ergebnis `spectrum_db` mit bis zu 131 072 Float-Werten —
in der HTTP-Antwort, in `/tmp/pidrive_spectrum.json` und damit in **jedem**
`/api/spectrum/last` und jedem Dashboard-Rendering (`view_model.py:209`, `app.py:374`).
Mehrere MB JSON pro Poll auf einem Pi 3B.

### F9 Keine Fortschrittsanzeige, kein Abbruch `[ANALYSE]` — mittel

`sweep_fm_band` läuft synchron im Flask-Request-Thread. Kein Job-State, kein
`ipc.write_progress` (anders als DAB), keine Abbruchmöglichkeit. Client-seitig nur ein
statischer Text. `/api/spectrum/last` zeigt erst nach Abschluss etwas, weil
`save_last_spectrum` nur am Ende läuft (`:934`). Der Sweep bricht nicht ab — er
blockiert sichtlos.

### F10 Kleinere Punkte `[ANALYSE]` — niedrig

- `_u8_iq_to_complex_legacy` (`:746-755`) ist eine Python-Schleife über 65 536 bis
  262 144 Samples, obwohl die vektorisierte numpy-Variante im gleichen Modul steht
  (`:339-347`).
- `which_tools()` (`rtlsdr.py:89-91`) prüft `rtl_sdr` nicht; im Legacy-Pfad wird ein
  fehlendes Binary nur als generischer `str(e)` gemeldet.
- `copy.replace` (`spectrum.py:719`, `:737`) gibt es erst ab Python 3.13 — auf Pi OS
  Bookworm (3.11) wirft das `AttributeError`. Betrifft `watch_pmr446`/`watch_freenet`,
  die derzeit keinen Aufrufer haben.

### F11 Ergebnisse wandern nicht in die Senderliste `[ANALYSE]` — mittel

`get_confirmed_stations` wird nur von `/api/spectrum/stations` gelesen. Kein Aufruf
schreibt in den `StationStore` oder `fm_stations.json` — das füllt nur `fm.scan`
(`fm.py:388`). Ein Sweep-Ergebnis ist auch bei Erfolg eine Sackgasse.

### F12 Kein CLI-Zugang `[BELEGT]`

In `cli/cli.py` existiert kein `spectrum`-Parser; `modules/radio/spectrum.py` hat keinen
`__main__`-Block. Ohne Browser bleibt nur `curl` oder
`python3 modules/radio/rtlsdr.py --active`.

---

## 7. Arbeitspakete

Reihenfolge ist verbindlich. W0 und W1 sind blockierend.

**Eine Abweichung von der Nummerierung:** Die Punkte 1–3 aus W7 (Zustandsmaschine,
Stufe 1) werden **vor W5** gezogen, weil die Scanner-Korrekturen C1 und C7 genau in
diesem Modul sitzen. Tatsächliche Reihenfolge: W0 → W1 → W2 → W3 → W4 → W7/Stufe 1 →
W5 → W6 → W7/Rest → W8 …

### W0 Sicherheitsnetz — blockierend, vor jeder Änderung

Analog zu M0 aus dem Menü-Auftrag. Ohne diesen Schritt ist nicht feststellbar, ob eine
Reparatur etwas repariert.

1. `docs/FEATURES.md` um einen Abschnitt „WebUI" erweitern: **jede** Seite, jede Karte,
   jeder Button — mit zugehöriger Route bzw. Kommando und Soll-Verhalten. Was heute
   defekt ist, wird als defekt eingetragen, nicht weggelassen.
2. Route-/Kommando-Inventar als Maschinen-lesbare Referenz erzeugen
   (`tests/webui/routes.json`): alle Flask-Routen, alle `ALLOWED_COMMANDS`, alle
   Präfixe.
3. `pidrivectl webui check` implementieren (siehe §8) und in `pidrivectl test all`
   aufnehmen.

**Abnahme:** `pidrivectl webui check` läuft und meldet die in §4/V4 genannten Treffer.
Ein Test, der die bekannten Fehler nicht findet, ist nicht fertig.

### W1 Fehler sichtbar machen — blockierend

Das ist der Kern des Auftrags. Alle kritischen Befunde waren unsichtbar.

1. **Import-Selbsttest** `pidrivectl webui selftest`: importiert jedes
   `web.shared.*`-Modul und ruft jede öffentliche Funktion einmal mit Default-Argumenten
   auf. `NameError`, `ImportError` und `AttributeError` werden als Fehler gemeldet, nicht
   geschluckt. Hätte S11, S12 und F3 sofort gefunden.
2. **Stumme `except` entschärfen:** jedes `except Exception` in `web/shared/*` und
   `modules/radio/*` protokolliert mindestens einmal pro Prozesslauf auf WARN-Level mit
   Modul, Funktion und Ausnahmetext. Bewusst geduldete Ausnahmen werden im Code
   begründet. Verboten bleibt: `except: pass` ohne Kommentar.
3. **Fehlgeschlagene Importe melden:** die `try/except ImportError`-Blöcke in
   `modules/radio/*` setzen ein Feld `degraded_imports` im Status. Die Oberfläche zeigt
   es an. Damit wäre C2 seit Wochen sichtbar gewesen.
4. **Blueprint-Import entkapseln** (V6): Registrierungsfehler gehören in das Log und in
   eine Warnung auf jeder Seite, nicht in ein stilles `except`.

**Abnahme:** `pidrivectl webui selftest` findet die bekannten `NameError` **vor** ihrer
Behebung. Erst dann W2 beginnen.

### W2 Statuskette reparieren

1. **Aktualität aus dem Dateialter** (S1, S2): `/api/core` liefert `status_age` und
   `menu_age` auf oberster Ebene, aus `file_age()` — nicht aus der Request-Zeit.
   `base.html` zeigt bei `status_age > 3s` einen sichtbaren Hinweis „Core antwortet
   nicht (letzter Stand vor Xs)" und graut die betroffenen Anzeigen aus.
   Browser-Uhrzeit nicht mehr für Differenzen verwenden.
2. **Leerer Status ist unterscheidbar von leeren Werten**: `read_json` gibt neben den
   Daten einen Fehlergrund zurück (fehlend / defekt / veraltet). Die Oberfläche
   unterscheidet „Core läuft, Wert leer" von „kein Status".
3. `READY_FILE` im `finally` des Core löschen (`main_core.py:741-746`) — sonst ist
   `core_ready` nach dem ersten Boot bis zum Reboot dauerhaft `true` und als
   Lebendigkeitssignal untauglich.
4. `processes` in `ipc.write_status()` exportieren (S3). Doppelten Schlüssel
   `dab_sync_seen` (`ipc.py:99`/`:104`) bereinigen.
5. `onBaseRefresh` für die fünf Seiten ohne Hook (S4) — oder den Abschnitt sichtbar als
   „Momentaufnahme, Stand HH:MM:SS" kennzeichnen. Eingefrorene Werte ohne Kennzeichnung
   sind nicht zulässig.
6. Feldnamen geradeziehen: S5 (`stdout`), S6 (`dab_playback_state`), S7 (`bt_on`),
   S8 (`disk_total`, `throttled` — bis dahin darf die Throttling-Karte **nicht** grün
   anzeigen).
7. `/api/state` entlasten (S9): ein Aufruf pro Seitenladung, Listen über eigene, billige
   Endpunkte. **Vor** oder **mit** W3 erledigen, nicht danach.

### W3 Tote Schichten bereinigen

1. `pidrive/web/shared.py` löschen (S13) — vorher prüfen, ob `ALLOWED_COMMANDS` dort
   Einträge hat, die im Paket fehlen.
2. `api-core.js:42` korrigieren (S10).
3. Für die sechs `page-*.js`-Stubs und `page-index.js` entscheiden: entweder mit Inhalt
   füllen oder löschen. **`page-index.js` nicht einbinden, ohne das inline
   `onBaseRefresh` aus `index.html` vorher zu entfernen** (V1) — sonst ist die
   Player-Anzeige tot.
4. Pfadfehler V5 korrigieren; beide Endpunkte müssen im Fehlerfall `ok: false` liefern.
5. V4 abarbeiten: `prev_station`/`next_station` auf die tatsächlichen Kommandos
   abbilden, PPM-Feld an `/api/runtime` hängen, „Auto-Kalibrieren" auf die Route statt
   auf `sendCmd` legen, `/api/favorites` entweder anlegen oder den Aufruf entfernen.

### W4 Importbruch RTL-SDR — eigener Commit

Die sechs Stellen aus C2 auf `modules.radio` umstellen. **Jede Stelle einzeln prüfen**
— `modules/radio/rtlsdr.py:17` importiert aus demselben Paket und ist gesondert zu
betrachten.

Danach zwingend R5 (Quellenwechsel) fahren. Wird die Sperre scharf und blockiert
legitime Wechsel, ist das ein **neuer** Fehler in der Sperrlogik und keine Regression
dieses Auftrags — aber er muss vor W5 behoben sein.

`MIGRATION_BACKLOG.md:36/51-56/80-81` und `modules/audio.py:59` (behauptet
`--ao=alsa`, tatsächlich `--ao=pulse`) im selben Commit korrigieren.

### W5 Scanner hörbar machen

1. **C1 beseitigen.** Empfehlung: `begin_transition` erst **nach** dem Scan aufrufen,
   wenn der Zielkanal bekannt ist. Der Guard in `_scan_list`/`_scan_range` hat einen
   Sinn — ihn zu entfernen macht den Scan gegenüber echten Quellenwechseln blind. Die
   Alternative (Transition mit Eigentümer-Erkennung) ist aufwendiger, aber korrekter;
   Entscheidung siehe E3.
2. **C3:** `-s` aus der Kanalbandbreite ableiten statt fest 200 kHz. Vorher
   Referenzaufnahme (`[MESSEN]`).
3. **C4:** Detektionsfenster auf einen gemessenen Wert setzen, mindestens 1,5 s.
4. **C7, C9** korrigieren.
5. **C5:** Sweep beschleunigen. Der tragfähige Weg ist **ein** offener `rtl_fm`-Prozess
   mit Frequenzumstimmung statt N Neustarts — löst C4 und C5 gemeinsam und ist die
   Voraussetzung für C6. `fast_bw` an den Schritt anpassen, damit keine Lücken bleiben.
6. **C8** (CB-Nummerierung, CB-AM, Freenet-Kanäle), **C13**, **C14**.
7. **C12:** `check_hardware()` beim Scan-Start aufrufen und das Ergebnis in die
   Oberfläche geben. `pkill`-Muster an die tatsächliche Kommandozeile anpassen.

**C6 (fortlaufender Scan) ist laut E2 nicht Teil dieses Auftrags.** Ziel ist der
Einzelscan: Kanal finden, aufschalten, fertig. Kein Scan-Thread, keine Haltezeit, kein
Weiterlaufen nach Trägerabfall — auch nicht als Nebenprodukt.

**Leitband ist PMR446** (E5/E9). Die Abnahme erfolgt dort; Korrekturen an CB, Freenet,
LPD433 und VHF/UHF werden umgesetzt, aber nicht als verifiziert ausgewiesen.

### W6 Scanner beobachtbar machen

1. `scanner`-Schlüssel in `write_status` schreiben (C11): aktives Band, Frequenz,
   Kanalname, Squelch-Schwelle, letzte Bytemenge, Scan-Fortschritt.
2. `pidrivectl scanner <band> scan --verbose` gibt pro geprüftem Kanal Frequenz,
   Bytemenge und Entscheidung aus. **Das ist das Werkzeug, mit dem der Eigentümer
   „hörbar" endlich selbst verifizieren kann** — ohne Fahrzeug, ohne Browser.
3. Suchlauf-Button in der WebUI (fehlt heute komplett) und die fehlenden
   Menüeinträge: `scanner_stop`, `scan_setch`, `scan_setfreq`, `scan_step`, Squelch —
   alle sind in `td_scanner.py` implementiert, aber im Menü nicht erreichbar.

### W7 Zustandsmaschine — Stufe 1 und 2

Vollständige Analyse und Zielbild:
[../architektur/ZUSTANDSMASCHINE.md](../architektur/ZUSTANDSMASCHINE.md).
Dort sind die Befunde Z1–Z10 belegt; hier stehen nur die Arbeitsschritte.

**Terminlage:** Die Punkte 1–3 von Stufe 1 sind **Voraussetzung für W5**, weil die
Korrekturen C1 und C7 genau in diesem Modul sitzen. Sie werden vorgezogen und
gemeinsam mit W5 abgenommen. Punkt 4 und Stufe 2 folgen nach W6.

Kernaussage der Analyse: `modules/source_state.py` ist laut eigenem Kopfkommentar ein
**Zustandsspiegel, kein Regler** — es gibt keine Übergangstabelle und keine Validierung.
Die Korrektheit liegt bei rund 50 Aufrufstellen. Dazu existieren **drei parallele
Sperrschichten** (`source_state.transition`, `main_core._SCAN_LOCK`,
`main_core._SOURCE_SWITCH_LOCK`) und eine vierte, tote (RTL-SDR-`flock`, Befund C2).

#### Stufe 1 — Sichtbarkeit und Wahrheit

1. **Abgelehnte Wechsel melden (Z2).** 17 der 19 `begin_transition`-Aufrufstellen
   ignorieren den Rückgabewert `False` — das Kommando verschwindet stumm. Die
   Referenzform existiert bereits in `trigger/td_radio.py:96-101`: Meldung an den
   Nutzer, Nebensperre freigeben, Abbruch. **Dieses Muster auf alle Stellen anwenden,
   kein neues erfinden.**
2. **`in_transition()` reparieren statt überstimmen (Z3).** Die Funktion gibt nach
   Ablauf der Zeitschranke `False` zurück, ohne den Zustand zu bereinigen. Dadurch
   sagt Python „keine Transition", während die Datei weiter `transition: true` führt —
   und das WebUI liest die Datei. Nach der Änderung müssen Speicher und Datei
   übereinstimmen.
3. **Stale-Check periodisch aufrufen (Z3).** `_check_stale_transition()` läuft heute
   nur aus `commit_source()` und `end_transition()`. Stirbt der Eigentümer, ruft
   niemand mehr commit oder end — der beworbene Watchdog greift genau im Krisenfall
   nie. Aufruf in die Core-Hauptschleife aufnehmen.
4. **Übergangshistorie (Z10).** Ringpuffer der letzten 20 Übergänge in `STATE` und in
   der Statusdatei: Eigentümer, Ziel, Ergebnis, Dauer. Etwa 30 Zeilen — und der
   wirksamste Einzelhebel für Fehler, die nur im Fahrzeug auftreten. Über
   `pidrivectl source history` ausgeben.

Stufe 1 ändert **keine** Semantik der Quellenwechsel. Sie ist ohne Fahrzeug abnehmbar.

#### Stufe 2 — Bluetooth als Quelle

`bt` wird committet wie jede andere Quelle (Z1). Heute kommt `bt` in **keinem**
`commit_source`-Aufruf vor — die im Fahrzeug wichtigste Quelle existiert im
Quellenmodell nicht, sondern nur in den Parallelfeldern `bt_state`, `bt_link_state`,
`bt_audio_state`.

Vor der Umsetzung ist festzulegen, welcher Zustand „BT ist die aktive Quelle"
bedeutet — die Verbindung allein genügt nicht, es braucht den Audio-Pfad (E10).
`bt_link_state` und `bt_audio_state` bleiben als Detailzustand erhalten.

Damit entfällt die Notwendigkeit, im WebUI zwei Zustandswelten zu verrechnen (Befund
S7). Und es ist die Vorarbeit für `esp32.bt-gateway`, das ebenfalls eine Quelle wird.

#### Nicht in diesem Auftrag

Stufe 3 aus dem Architekturdokument: Eigentümerprüfung in `end_transition()`,
Übergangstabelle, Zusammenführung der Sperrschichten, Zeitschranken pro
Operationstyp. Begründung: die Eigentümerprüfung setzt eine Konvention für `owner`
voraus (Z6 — heute übergeben fünf Aufrufstellen fünf verschiedene Bedeutungen), und
die Zusammenführung der Sperrschichten ist ein Eingriff, der eigene Fahrzeugtests
braucht.

**Ausnahme:** `scanner.py:320` ruft `begin_transition("scanner", reason="user_select")`
mit einem nicht existierenden Schlüsselwort. Der `TypeError` wird verschluckt, die
Transition also **nie** geöffnet. Das ist mit C7 in W5 zu beheben, nicht erst in
Stufe 3.

### W8 FastScan korrigieren

1. **F3 zuerst** — zwei Zeilen, danach antwortet der PMR446-Pfad überhaupt erst.
2. **F1:** `min_hits` aus der Fensterüberlappung ableiten.
3. **F5:** Mittenfrequenz um eine halbe Kanalbreite versetzen.
4. **F2:** FFT-Größe von der Sample-Anzahl entkoppeln, über Blöcke mitteln.
5. **F4:** einen `rtl_sdr`-Prozess offen halten statt pro Frame neu zu starten;
   `fft_size` konsistent aus dem Profil nehmen.
6. **F7, F8, F9, F11, F10.**

### W9 Verlorene Funktionen zurückholen

Priorität nach Nutzen: **Menü-Fernsteuerung zuerst** (V3 — Backend existiert, reine
Oberfläche, zugleich Vorarbeit für `esp32.bt-gateway`), dann Systemdiagnose,
Audio-Cockpit, DAB-Scan-Diagnose, Spektrum-Analyzer.

Die Reihenfolge der restlichen Punkte legt der Eigentümer fest (E6). `index_legacy.html`
ist dabei Referenz für den Funktionsumfang, **nicht** Vorlage für die Umsetzung.

### W10 Settings-Reload

C10: Reload von `settings.json` im Core-Hauptloop bei geänderter `mtime`, oder ein
Trigger `settings_reload`. Die drei divergierenden Squelch-Defaults auf einen Wert
bringen.

### W11 Dokumentation nachziehen

`docs/FEATURES.md` auf den Ist-Stand nach W1–W10. `docs/architektur/ZUSTANDSMASCHINE.md`
um die Ergebnisse von W7 ergänzen. Archiv-Behauptungen korrigieren (C2,
C15). Dieses Dokument mit Abnahmeergebnissen ergänzen — nicht überschreiben.

---

## 8. CLI- und Testoberfläche

Neue Befehle. Jeder Befund aus §3–§6 muss durch genau einen Test abgedeckt sein.

| Befehl | Zweck | Deckt ab |
|---|---|---|
| `pidrivectl webui check` | statisch: jedes `sendCmd`-Argument in `ALLOWED_COMMANDS`, jede `fetch`-URL hat eine Route, jedes im Template gelesene Statusfeld wird von `write_status` geschrieben | V4, S3, S5–S8 |
| `pidrivectl webui selftest` | importiert alle `web.shared.*`, ruft jede öffentliche Funktion einmal | S11, S12, V6 |
| `pidrivectl webui routes` | Liste aller Routen mit Methode und Herkunft (App/Blueprint) | V6 |
| `pidrivectl scanner status` | aktives Band, Frequenz, Squelch, letzte Bytemenge | C11 |
| `pidrivectl scanner <band> scan --verbose` | Kanal, Bytemenge, Entscheidung pro Schritt | C1, C3, C4 |
| `pidrivectl spectrum snapshot --center <MHz>` | Einzelmessung ohne Browser | F7, F12 |
| `pidrivectl spectrum sweep [--start --stop --step]` | FM-Sweep mit Fortschritt auf stdout | F1, F2, F9, F12 |
| `pidrivectl spectrum watch <pmr446\|freenet>` | Kanalaktivität über N Sekunden | F3, F4, F5 |
| `pidrivectl source state` | `source_current`, `transition`, `owner`, Alter — und ob Speicher und Datei übereinstimmen | Z3 |
| `pidrivectl source history` | letzte 20 Übergänge mit Eigentümer, Ziel, Ergebnis, Dauer | Z10 |

`pidrivectl webui check` ist der wichtigste Punkt der Liste. Es ist das Werkzeug, das
„Buttons gehen ins Leere" dauerhaft verhindert — analog zu `menu lint` aus M0. In
`pidrivectl test all` aufnehmen.

---

## 9. Regressionsmatrix

| ID | Prüfung | Abnahmekriterium |
|---|---|---|
| R1 | `pidrivectl webui check` | 0 Treffer; bekannte Fehler vor der Behebung gefunden |
| R2 | `pidrivectl webui selftest` | 0 Fehler; alle `web.shared`-Funktionen aufrufbar |
| R3 | Core beenden, WebUI beobachten | binnen 3s sichtbarer Hinweis „Core antwortet nicht"; keine alten Werte als frisch |
| R4 | Jede Seite laden, Browser-Konsole | keine Fehler, kein `SyntaxError`, kein undefiniertes Symbol |
| R5 | DAB → FM → Scanner → DAB | jeder Wechsel gelingt, kein Stick-Konflikt, kein Dauer-Lock |
| R6 | `pidrivectl scanner pmr446 ch 1` | tunt auf 446.00625 MHz, Audio hörbar, Bandbreite ≤ 25 kHz |
| R7 | `pidrivectl scanner pmr446 scan --verbose` | prüft **alle** Kanäle; bei aktivem Sender Treffer, sonst begründeter Durchlauf |
| R8 | `pidrivectl spectrum sweep` | nicht-leere `candidates`-Liste, plausible Frequenzen |
| R9 | `pidrivectl spectrum watch pmr446` | antwortet ohne Fehler; keine Dauer-Aktivität auf Kanal 4/5 |
| R10 | Menü-Fernsteuerung im Browser | Navigation und Aktivierung wie über `pidrivectl menu goto/activate` |
| R11 | `pidrivectl menu verify` | unverändert grün — der Menü-Vertrag aus M0 bleibt gültig |
| R12 | Zwei Quellenwechsel kurz hintereinander auslösen | der zweite wird **sichtbar** abgelehnt („Blockiert"), nicht stumm verworfen (Z2) |
| R13 | Quellenmodul während einer Transition abwürgen | binnen Zeitschranke räumt der periodische Stale-Check auf; Datei und `in_transition()` sagen dasselbe (Z3) |
| R14 | `pidrivectl source history` nach R5 | zeigt die Übergänge von R5 lückenlos mit Dauer (Z10) |
| R15 | `pidrivectl test all` | grün, inklusive R1, R2 und R12 |

R6 ist der erste sinnvolle Meilenstein: der Direktbetrieb ist **schon heute** der einzige
funktionierende Pfad zum Lautsprecher (abgesehen von der Bandbreite). Damit lässt sich
die Audiokette isoliert verifizieren, bevor der Suchlauf angefasst wird.

---

## 9.2 Hardware-Verifikation am Fahrzeug-Pi

Ab 2026-09-15 steht ein echter Pi zur Verfügung. Jede Änderung wird **dort** verifiziert,
nicht nur lokal.

| | |
|---|---|
| Host | `192.168.178.105` |
| Benutzer | `pidrive` |
| Passwort | beim Eigentümer erfragen — **nicht** in dieses Repo schreiben |
| Version bei Übernahme | `0.11.127`, `pidrivectl test all` = 20 bestanden / 2 Fehler / 29 Warnungen / 68,7 s |

**Erste Maßnahme:** SSH-Schlüssel einrichten und Passwort-Anmeldung abschalten. Der Pi
hängt im Heimnetz, und das WebUI auf Port 8080 hat keine Authentifizierung (Befund in
§4). Ein triviales Passwort auf demselben Host ist damit die zweite offene Tür.

### H0 Deploy-Gleichstand — blockierend, vor allem anderen

**Der Pi läuft mit hoher Wahrscheinlichkeit nicht den Code aus dem Repo.**

Beleg: `test_suite.py:849` ruft `test_menu()` als **ersten** Test in `run_all()` auf, und
`test_menu()` gibt in Zeile 798 unbedingt `_section("MENU", "📋")` aus — der Import in
Zeile 799 ist nicht in ein `try` gefasst, ein Importfehler würde also den ganzen Lauf
abbrechen. In der Referenzausgabe vom 2026-09-15 12:11 fehlt der MENU-Abschnitt
vollständig; die Ausgabe beginnt mit SYSTEM. Der Lauf ist aber vollständig
durchgelaufen. Daraus folgt: das installierte `test_suite.py` kennt `test_menu()` nicht.

Beide Seiten melden `0.11.127` — die Versionsdatei wurde bei der Menü-Arbeit (M0–M6)
also nicht angehoben. Die Versionsnummer taugt damit **nicht** als Gleichstandsprüfung.

Vor jeder Messung:

```bash
# auf dem Pi
cd <pidrive-repo> && git rev-parse --short HEAD && git status --short
grep -c "def test_menu" pidrive/test_suite.py     # muss 1 sein
systemctl status pidrive_core pidrive_web --no-pager | head -5
```

Der Commit muss dem entsprechen, gegen den entwickelt wird. Ergebnis in
`docs/ABNAHMEN.md` protokollieren — **jede** Messung nennt den Commit-Hash, sonst ist
sie nicht zuordenbar.

Zusätzlich: `VERSION` bei jeder funktionalen Änderung anheben, sonst wiederholt sich
dieses Problem bei jeder Abnahme.

### H1 Baseline vor der ersten Änderung

```bash
pidrivectl test all 2>&1 | tee /tmp/baseline_$(date +%F_%H%M).log
cp /tmp/pidrive_test_results.json /tmp/baseline_results.json
cp /tmp/pidrive_status.json /tmp/pidrive_source_state.json /tmp/pidrive_menu.json /tmp/baseline/
```

Ohne Baseline ist später nicht unterscheidbar, was die Änderung bewirkt hat und was
vorher schon kaputt war. Die Referenzausgabe oben ist die Baseline **des alten Stands**
und damit nur eingeschränkt verwendbar (siehe H0).

### H2 Sofort verifizierbare Einzelbefunde

Diese Befunde sind am Schreibtisch belegt und am Pi in Minuten nachweisbar. Sie sind
der schnellste Weg, den statischen Befund gegen die Realität zu prüfen.

| ID | Befund | Prüfung am Pi | Erwartung vor der Korrektur |
|----|--------|---------------|------------------------------|
| H2.1 | Closure-Fehler `source_state` (§5/C16) | `echo radio_stop > /tmp/pidrive_cmd`, dann `journalctl -u pidrive_core -n 30` | Fehler „cannot access free variable" **und** Radio spielt weiter |
| H2.2 | dito, Spotify-Pfad | `echo spotify_toggle > /tmp/pidrive_cmd` | derselbe Fehler; `source_current` wird **nicht** `spotify` |
| H2.3 | Throttling-Anzeige (S8) | `vcgencmd get_throttled` gegen die Karte „Systemressourcen" im WebUI | CLI meldet `0x50000`, WebUI meldet grün „OK" |
| H2.4 | Statusalter (S1/S2) | `systemctl stop pidrive_core`, WebUI 60 s beobachten | „Core 0.0s", alte Werte bleiben als frisch stehen |
| H2.5 | `api-core.js` (S10) | Browser-Konsole auf jeder Seite | `SyntaxError`, `PiDriveAPI` undefiniert |
| H2.6 | Audio-Debug leer (S11) | `curl -s localhost:8080/api/audio` | `pulse_active:false`, `sinks:[]` trotz laufendem PipeWire |
| H2.7 | DAB-Diagnose (S12) | `curl -s localhost:8080/api/dab/scan/last` | `{"error":"name 'sys' is not defined"}` |
| H2.8 | Prozessliste (S3) | `curl -s localhost:8080/api/runtime \| grep processes` | leer, obwohl `welle-cli` läuft |
| H2.9 | Scanner-Abbruch (C1) | `pidrivectl scanner pmr446 scan`, parallel `journalctl -f -u pidrive_core` | „Scanner scan-list: abgebrochen" in der **ersten** Iteration; kein `rtl_fm` in `ps` |
| H2.10 | Bandbreite (C3) | `pidrivectl scanner pmr446 ch 1`, dann `ps aux \| grep rtl_fm` | `-s 200000` statt ≤ 25000 |
| H2.11 | FastScan leer (F1) | `curl -s 'localhost:8080/api/spectrum/stations'` | immer `[]` |
| H2.12 | Watch-Fehler (F3) | `curl -s -X POST 'localhost:8080/api/spectrum/capture?band=pmr446'` | `'DetectionResult' object has no attribute 'watch_seconds'` |
| H2.13 | Menü-Trigger blockiert (§4) | `curl -s -X POST localhost:8080/api/cmd -H 'Content-Type: application/json' -d '{"cmd":"activate:1"}'` | HTTP 400 „Befehl nicht erlaubt", obwohl der Core es kann |
| H2.14 | Webradio ignoriert Route | `pidrivectl audio route klinke` bei verbundenem BT, dann Webradio starten | spielt trotzdem über Bluetooth |
| H2.15 | Settings-Reload (C10) | Squelch im WebUI ändern, `pidrivectl scanner status` | Wert wirkt erst nach Core-Neustart |
| H2.16 | MPRIS nur bei Menü-`rev` | DAB spielen, Titelwechsel abwarten, BMW-Display beobachten | Display friert zwischen zwei Tastendrücken ein |

H2.16 braucht das Fahrzeug. Alle anderen gehen am Schreibtisch.

### H3 Was `pidrivectl test all` heute **nicht** abdeckt

Vorhanden sind `test_menu`, `test_system`, `test_audio`, `test_bluetooth`,
`test_mpris2_push`, `test_webradio`, `test_fm`, `test_scanner_fm`, `test_dab`,
`test_dab_scan`, `test_spotify`, `test_avrcp_inject`, `test_log_summary`
(`test_suite.py:122-833`).

Nicht abgedeckt:

| Lücke | Warum das zählt |
|---|---|
| **WebUI komplett** | Kein Routen-, Whitelist- oder Import-Test. Alle S-Befunde wären aufgefallen. → W0/W1 mit `webui check` und `webui selftest` |
| **Scanner-Schmalband** | `test_scanner_fm("103.0")` prüft ausschließlich den WBFM-Pfad (`test_suite.py:486`). PMR446, Freenet, CB, LPD433, VHF, UHF sind ungetestet — genau die Bänder, um die es geht |
| **Suchlauf** | Kein Test ruft `scan_next`. C1 wäre seit Wochen aufgefallen |
| **Spektrum / FastScan** | Kein Test, kein CLI-Einstieg (F12) |
| **Zustandsmaschine** | Keine Prüfung von Quellenwechseln, Transitionen, Ablehnungen. H2.1/H2.2 zeigen, was dadurch durchrutscht |
| **Lautstärke** | `set_volume`, `volume_up/down` ungetestet |
| **Audio-Route** | Kein Test schaltet `klinke`/`bt`/`hdmi` um und prüft, wo der Ton landet (H2.14) |
| **Lokale Bibliothek / USB** | Keine Wiedergabeprüfung |
| **Settings-Persistenz** | Kein Test für Schreiben, Neuladen, Wirksamkeit (C10) |
| **Menü live** | `test_menu` prüft nur den Offline-Referenzbaum. Die Live-Navigation über `goto:`/`activate:` wird nicht geprüft |

### H4 Qualitätsmängel der Testausgabe

Die Ausgabe sieht gründlich aus, trägt aber wenig Entscheidungsinformation.

1. **Ein Test, der nicht fehlschlagen kann.** `→ AVRCP-Inject: 0 Events verarbeitet
   (erwartet ≥0)` — die Bedingung „≥ 0" ist immer wahr. Entweder eine echte
   Mindestzahl fordern oder den Test ehrlich als „nicht abgedeckt" ausweisen.
2. **29 Warnungen sind kein Signal.** Bei dieser Menge liest niemand mehr hin. Warnungen
   müssen in zwei Klassen zerfallen: „Umgebung fehlt, Test nicht möglich" (BT nicht
   gepairt, kein DAB-Signal) und „Funktion verhält sich falsch". Nur letztere dürfen
   `⚠` heißen.
3. **Abgeschnittene Logzeilen.** `annot access free variable …`, `-09-15 12:12:42 …`,
   `] DAB DLS poller: …` — der Zeilenanfang wird weggeschnitten. Bei genau der Zeile,
   die den einzigen echten Fehler enthält, kostet das die Diagnose. Feste
   Zeichen-Offsets durch Feld-Parsing ersetzen.
4. **Erfundenes Vokabular.** `state=pcm_ok` sieht wie ein Systemzustand aus, ist aber ein
   Eigenbegriff des Tests (`test_suite.py:553`). Das echte `dab_playback_state` kennt
   `pcm_ok` nicht. Damit ist die Ausgabe nicht mit Log und WebUI korrelierbar — und es
   ist ein **drittes** Vokabular neben denen aus Befund S6.
5. **„Hörtest" ist keine Prüfung.** `→ Scanner läuft (5s Hörtest)` besteht, sobald der
   Prozess startet. Ersetzen durch eine objektive Größe: Bytes am `rtl_fm`-Ausgang,
   RMS-Pegel oder `sink_input`-Existenz.
6. **„Kein Signal" und „kaputt" sind nicht unterscheidbar.** `⚠ Kein mux.json nach 22s`
   kann Empfangslage oder Defekt sein. Der Test braucht eine Gegenprobe auf einem
   Kanal mit bekanntem Signal, sonst ist das Ergebnis wertlos.
7. **Grün trotz fragwürdigem Zustand.** `✓ Sink: alsa_output.platform-fe00b840.mailbox…
   SUSPENDED` — ein suspendierter Fallback-Sink wird als Erfolg gemeldet, ohne zu
   prüfen, ob das das gewünschte Ziel ist.
8. **Fehlerzählung nicht nachvollziehbar.** Die Zusammenfassung nennt 2 Fehler, der
   Log-Abschnitt listet einen. Jeder gezählte Fehler braucht eine eindeutige,
   auffindbare Zeile.
9. **Kein Exit-Code-Vertrag dokumentiert.** Für `pidrivectl test all` in einer
   Automatisierung muss gelten: 0 = alles grün, ≠ 0 = mindestens ein Fehler. Warnungen
   beeinflussen den Code nicht.
10. **Keine Umgebungsangabe im Kopf.** Commit-Hash, `git status`-Sauberkeit und
    Laufzeitumgebung gehören in die erste Zeile jeder Ausgabe — sonst wiederholt sich
    H0.

### H5 Neue Tests, die mit den Arbeitspaketen entstehen

Jedes Arbeitspaket liefert seinen Test mit. Keine Korrektur ohne zugehörige Prüfung.

| Test | Paket | Prüft |
|---|---|---|
| `test_webui_check` | W0 | Routen, Whitelist, Statusfelder statisch (R1) |
| `test_webui_selftest` | W1 | alle `web.shared`-Funktionen aufrufbar (R2) |
| `test_status_staleness` | W2 | Core anhalten → Hinweis erscheint (R3, H2.4) |
| `test_source_reject` | W7 | zweiter Wechsel wird sichtbar abgelehnt (R12) |
| `test_source_recovery` | W7 | abgewürgte Transition wird aufgeräumt (R13) |
| `test_source_history` | W7 | Historie lückenlos (R14) |
| `test_scanner_narrowband` | W5 | PMR446 Kanal 1: Bandbreite, Bytes, Pegel (R6) |
| `test_scanner_scan` | W5/W6 | Suchlauf prüft **alle** Kanäle (R7) |
| `test_spectrum_sweep` | W8 | nicht-leere Kandidatenliste (R8) |
| `test_spectrum_watch` | W8 | antwortet; keine Dauer-Aktivität auf PMR 4/5 (R9) |
| `test_audio_route` | — | Route umschalten, Ziel-Sink prüfen (H2.14) |
| `test_volume` | — | `set_volume` wirkt auf den aktiven Sink |
| `test_settings_reload` | W10 | Änderung wirkt ohne Core-Neustart (H2.15) |

Alle in `run_all()` aufnehmen — und zwar so, dass ein fehlender Test auffällt: `run_all()`
prüft am Ende, dass jeder registrierte Test auch eine Ausgabezeile erzeugt hat. Genau
das hätte H0 sofort sichtbar gemacht.

---

## 10. Was ausdrücklich nicht zu tun ist

1. **Keine Neuentwicklung der WebUI.** Die Befunde sind Reparaturen an vorhandenem,
   funktionierendem Backend. Ein dritter Umbau nach `index_legacy` → `index` würde die
   nächsten 18 Funktionen kosten.
2. **Kein Sammel-Commit.** W4 (RTL-SDR-Sperre) und W5 (Scanner-Parameter) müssen
   einzeln nachvollziehbar sein, weil beide das Laufzeitverhalten der Funkhardware
   ändern.
3. **Keine `[MESSEN]`-Punkte ohne Messung umparametrieren.** Bandbreite, Squelch-Schwelle
   und Detektionsfenster werden gemessen, nicht geschätzt. Vorher-Werte protokollieren.
4. **Keine stummen `except` neu einführen.** Auch nicht „vorübergehend".
5. **`page-index.js` nicht einbinden**, solange V1 nicht abgearbeitet ist.
6. **Keine Änderungen am Menü-Vertrag aus M0.** `pidrivectl menu verify` muss grün
   bleiben; die Menü-Fernsteuerung nutzt die vorhandene API, sie erweitert sie nicht.
7. **Keine Arbeit an `esp32.bt-gateway`** aus diesem Auftrag heraus. Die Schnittstelle
   ist dort dokumentiert, die Reihenfolge steuert der Eigentümer.
8. **`index_legacy.html` nicht löschen**, bis W9 abgeschlossen ist — es ist die einzige
   Referenz für den verlorenen Funktionsumfang.

---

## 11. Entscheidungen beim Eigentümer

### Entschieden (2026-09-15)

| ID | Frage | Entscheidung |
|---|---|---|
| **E1** | Reihenfolge | **Erst Statuskette.** W0 → W1 → W2 → W3, danach W4–W6. Begründung: ohne funktionierende Statusanzeige ist am Scanner nichts beobachtbar. |
| **E2** | Rang des Scanners | **Einzelscan genügt.** Kanal finden, aufschalten, fertig. **C6 (fortlaufender Scan mit Haltezeit) ist damit nicht Teil dieses Auftrags** — auch nicht „wenn es sich anbietet". Folgefrage E4 entfällt. |
| **E3** | C1-Korrektur: Transition nach dem Scan oder Eigentümer-Erkennung im Guard? | **Kurzfristig die Transition nach dem Scan öffnen.** Die Eigentümerprüfung ist die sachlich richtige Lösung, setzt aber eine Konvention für `owner` voraus (Z6: fünf Aufrufstellen, fünf Bedeutungen). Sie gehört damit in Stufe 3 der Zustandsmaschine, nicht in W5. |
| **E9** | Messmittel | **PMR446-Handfunkgerät vorhanden.** Damit sind C3, C4 und F4 auf PMR446 belegbar. CB, Freenet, LPD433 und VHF/UHF haben **keinen** Referenzsender — Korrekturen dort bleiben unverifiziert und sind als solche zu kennzeichnen. |

**Folge für den Zuschnitt:** PMR446 ist das Leitband (E5 damit beantwortet). C8 (CB-Nummerierung,
CB-AM) und die fehlenden Freenet-Kanäle bleiben im Auftrag, weil es klare Datenfehler
sind — sie werden korrigiert, aber nicht abgenommen. Kein `[MESSEN]`-Punkt darf auf
einem Band ohne Referenzsender als erledigt gelten.

### Offen

| ID | Frage | Hintergrund |
|---|---|---|
| E10 | Was bedeutet „BT ist die aktive Quelle"? | Voraussetzung für W7/Stufe 2. Verbindung allein genügt nicht — es braucht den Audio-Pfad. Vorschlag: `bt_audio_state` hat einen Sink **und** A2DP liefert Daten. Entscheidung erst zu Beginn von Stufe 2 nötig. |
| E6 | Welche der ~18 verlorenen Funktionen kommen zurück, in welcher Reihenfolge? | Empfehlung: Menü-Fernsteuerung zuerst (V3, Backend fertig, Nutzen für das Gateway). Entscheidung erst nach W3 nötig. |
| E7 | Ist das WebUI im Fahrzeug bedienbar oder nur Werkstatt-Werkzeug? | Bestimmt, wie viel Aufwand in Touch-Bedienung und Ladezeiten fließt. |
| E8 | Darf `pidrive/web/shared.py` gelöscht werden? | Toter Code (S13), aber die Löschung ist unumkehrbar. Empfehlung: löschen, Historie bleibt in git. |

---

## 12. Definition of Done

- W0 und W1 abgeschlossen; `pidrivectl webui check` und `webui selftest` in
  `pidrivectl test all`.
- Alle `[BELEGT]`-Befunde behoben oder mit Begründung zurückgestellt.
- Alle `[MESSEN]`-Befunde **auf PMR446** mit Vorher-/Nachher-Wert in `docs/ABNAHMEN.md`.
  Für Bänder ohne Referenzsender (CB, Freenet, LPD433, VHF/UHF) wird der Stand
  ausdrücklich als „umgesetzt, unverifiziert" protokolliert — nicht als erledigt.
- R1–R15 grün; R6 und R7 mit protokollierter Messung gegen das PMR446-Handfunkgerät.
- W7/Stufe 1 abgeschlossen: keine `begin_transition`-Aufrufstelle ohne Behandlung von
  `False`; Speicher und Zustandsdatei stimmen überein; Übergangshistorie vorhanden.
- `docs/architektur/ZUSTANDSMASCHINE.md` um die Ergebnisse ergänzt; Stufe 3 bleibt
  dort als offener Punkt stehen.
- C6 bleibt offen und ist kein Abnahmekriterium (E2).
- `docs/FEATURES.md` auf Ist-Stand; dieses Dokument mit Abnahmeergebnissen ergänzt.
- Kein neues `except: pass` ohne Begründung im Diff.
