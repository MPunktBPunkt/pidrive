> **Arbeitsauftrag — Spektrumanzeige zurückholen, AVRCP-Tab zur Messbühne ausbauen**
> Stand: 2026-09-16 · Basis: v0.11.138 (`251742d`) · Befund-Präfixe: **SA** und **AV**

---

## 0. Zweck und Abgrenzung

Zwei Wünsche des Betreibers, beide mit demselben Muster: **die Messfunktion existiert
bereits vollständig, es fehlt ausschließlich die Darstellung.**

1. **Teil A — Spektrum.** Der Betreiber hat in der welle.io-DAB-Diagnose ein Spektrum
   gesehen und sich eine allgemeine Funktion gewünscht, um selbst Peaks zu sehen.
2. **Teil B — AVRCP.** Der AVRCP-Tab soll taugen, um die Rückgaben des BMW zu prüfen.

Die Befunde tragen eigene Präfixe **SA** (Spektrum-Analysator) und **AV** (AVRCP), damit
keine Nummer mit S, V, C, F, W, Z, E, H, R, M, G, B, K, D, N, MD, SP, TK oder Q kollidiert.

**Dateibesitz.** Es gilt weiter *ein Schreiber pro Datei*. Dieses Dokument gehört zu
keinem laufenden Paket einer anderen Instanz. Berührt werden sollen:

| Datei | berührt von | Konflikt? |
|---|---|---|
| `pidrive/modules/radio/spectrum.py` | [AUFTRAG-FUNKPFAD.md](AUFTRAG-FUNKPFAD.md) (K1) | **ja** — K1 zuerst, siehe §3 |
| `pidrive/web/templates/rf-tools.html` | [AUFTRAG-WEBUI-SANIERUNG.md](AUFTRAG-WEBUI-SANIERUNG.md) (W3) | prüfen |
| `pidrive/web/templates/avrcp.html` | — | nein |
| `pidrive/web/app.py` | W1/W3 | prüfen |
| `pidrive/integration/avrcp_trigger.py` | — | nein |
| `pidrive/mpris2.py` | [AUFTRAG-QUELLENSTART-UND-SUCHLAUFANZEIGE.md](AUFTRAG-QUELLENSTART-UND-SUCHLAUFANZEIGE.md) (Q-M) | **ja** — Q-M ist eingebaut, nur additiv ergänzen |

---

# TEIL A — SPEKTRUM

## 1. Befunde

### SA1 — welle-cli kann ein Spektrum, aber nur über DAB-Kanäle `[BELEGT]`

`welle-cli -c 10B -w 8000` startet einen Webserver. `GET /spectrum` liefert das Spektrum
in Dezibel als Folge von Float-Werten; daneben gibt es `/constellation`,
`/impulseresponse`, `/nullspectrum`, `/fic` und `/mux.json`. Genau die Ansicht, die der
Betreiber in der welle.io-Diagnose gesehen hat, samt fertiger Oberfläche.

Die Abstimmung läuft jedoch über **DAB-Kanalnamen**: `POST /channel` nimmt Werte wie
`12A`, intern über `getChannelForFrequency`. Damit ist der erreichbare Bereich auf Band III
(174–240 MHz) und L-Band beschränkt. Die Bänder, um die es dem Betreiber geht, liegen
außerhalb:

| Band | Frequenz | mit welle-cli erreichbar |
|---|---|---|
| PMR446 | 446,0–446,2 MHz | nein |
| LPD433 | 433,05–434,79 MHz | nein |
| Freenet | 149,0–149,1 MHz | nein |
| CB | 26,9–27,4 MHz | nein |
| DAB Band III | 174–240 MHz | ja |

**Folgerung: welle-cli ist als Allzweck-Analysator nicht brauchbar.** Der Webmodus wird im
Projekt derzeit nirgends genutzt (kein `-w` in `modules/radio/`). Zusätzlich belegt
welle-cli den RTL-SDR, solange es läuft — ein Diagnose-Webserver und eine
PiDrive-Messung können nicht gleichzeitig laufen.

### SA2 — die allgemeine Funktion ist bereits vollständig implementiert `[BELEGT]`

`spectrum.py:834` `capture_spectrum(center_mhz, sample_rate_hz, sample_count, ppm, gain,
peak_threshold_db)` misst auf **beliebiger** Mittenfrequenz und liefert:

| Feld | Inhalt |
|---|---|
| `spectrum_db` | die vollständige Kurve in dB |
| `center_mhz`, `sample_rate_hz`, `bin_hz` | Achsenbezug |
| `peaks` | erkannte Spitzen mit `freq_mhz` und `db` |
| `sample_count_iq`, `ppm`, `gain`, `ts` | Messbedingungen |

`save_last_spectrum(result)` legt das Ergebnis ab, `/api/spectrum/last` gibt es heraus.
**Der Wunsch „selbst Peaks sehen" ist datenseitig erfüllt.** Es fehlt der Zeichencode.

### SA3 — der Zeichencode existiert, aber nur im verworfenen Altstand `[BELEGT]`

| Fundstelle | Inhalt |
|---|---|
| `index_legacy.html:601` | Betriebsart-Auswahl `saMode` (Snapshot / Sweep) mit `saUpdateMode()` |
| `index_legacy.html:682` | `<canvas id="saCanvas" width="680" height="130">` |
| `index_legacy.html:2305` | `saRenderTrace(data)` — Kurvenzeichnung |
| `index_legacy.html:2316` | liest `data.spectrum_db` als Bin-Quelle |
| `index_legacy.html:2419` | `saRenderPeakBars(data)` — Balken-Rückfall ohne Kurve |

Im heutigen Stand steht dagegen in `rf-tools.html:32` ein `<pre id="specPre">`, das in
Zeile 80 mit `JSON.stringify(j, null, 2)` gefüllt wird. **Ein `<pre>` kann kein Bild
zeigen** — das fehlende Spektrum ist also kein Darstellungsfehler, sondern eine bei der
Überarbeitung verlorene Funktion.

### SA4 — drei unvereinbare Antwortformen an einem Endpunkt `[BELEGT]`

`/api/spectrum/capture` liefert je nach Aufruf drei verschiedene Strukturen:

| Aufruf | Leitfeld | enthält `spectrum_db`? | Fundstelle |
|---|---|---|---|
| `band=pmr446` oder `freenet` | `data.active_channels`, `data.best_candidate` | **nein** | `app.py:748` |
| `mode=fm_sweep` | `windows`, `candidates`, `windows_ok` | **nein** | `spectrum.py:922` |
| `mode=snapshot` | `spectrum_db`, `peaks`, `bin_hz` | **ja** | `spectrum.py:874` |

Ein Renderer muss alle drei unterscheiden. Der Altstand kannte nur zwei davon — der
Bandpfad mit `watch_channels()` ist neuer. **Wer `saRenderTrace` unverändert
zurückkopiert, bekommt beim Bandpfad eine leere Fläche ohne Fehlermeldung.**

### SA5 — der Snapshot-Knopf ruft die falsche Betriebsart: zwei unabhängige Fehler `[BELEGT]`

**Fehler eins — fehlende Betriebsart.** `rf-tools.html:75` sendet
`/api/spectrum/capture?center=${c}&ppm=${p}&gain=${g}`, also **ohne** `mode`.
`app.py:717` setzt `mode = args.get("mode", "fm_sweep")`. Der Knopf mit der Aufschrift
„Snapshot" startet damit einen Durchlauf über das ganze FM-Band.

**Fehler zwei — falscher Feldname.** Selbst mit `mode=snapshot` liest `app.py:769`
`args.get("center_mhz", 98.0)`. Der eingegebene Wert kommt als `center` an und wird nie
gelesen; gemessen würde stets bei 98,0 MHz.

**Dazu, unabhängig:** `rf-tools.html:76` verwirft die Antwort des Aufrufs, wartet blind
8000 ms und lädt dann `/api/spectrum/last`. Ein Sweep über 87,5–108 MHz in 1-MHz-Schritten
braucht deutlich länger, ein Snapshot deutlich kürzer. Die Anzeige zeigt in beiden Fällen
mit hoher Wahrscheinlichkeit das falsche Ergebnis — beim Sweep das vorige, beim Snapshot
eine unnötige Wartezeit.

### SA6 — `rtl_sdr` wird ohne Ausgabeargument gestartet `[BELEGT]`

`spectrum.py:844`:

```python
cmd = ["rtl_sdr", "-f", str(center_hz),
       "-s", str(int(sample_rate_hz)),
       "-n", str(int(sample_count))]
```

`rtl_sdr` verlangt ein Ausgabeziel als letztes Argument — eine Datei oder `-` für
stdout. Ohne das gibt es einen Nutzungshinweis auf stderr und **nichts** auf stdout.
`spectrum.py:860` meldet daraufhin `"keine IQ-Daten"`, auch bei völlig freiem Stick.

**Das ist der harte Blocker.** Solange diese Zeile steht, ist ein Snapshot unmöglich,
unabhängig von Betriebsart, Feldnamen, Renderer und Gerätereservierung. Die Meldung
`"RTL-SDR belegt"` im Feld hat eine andere Ursache (K1 und die Testkette), aber selbst
mit freiem Stick käme hier nur `"keine IQ-Daten"`.

### SA7 — Nutzlast und Rechenzeit: die Reihenfolgefalle `[BELEGT]`

Vorgabe `sample_count=262144` Bytes ergibt 131 072 IQ-Paare. `_fft_power_db_legacy`
(`spectrum.py:765`) rechnet die FFT über **alle** Werte und gibt sie ungekürzt zurück:

```python
fft = np.fft.fftshift(np.fft.fft(arr))
db  = 10.0 * np.log10(power)
return db.tolist(), len(db)
```

`spectrum_db` ist damit eine Liste von **131 072 Fließkommazahlen** — als JSON grob
**zwei Megabyte pro Messung**. Die Zeichenfläche des Altstands ist 680 Pixel breit.

Dazu ein zweiter Punkt: `_u8_iq_to_complex_legacy` (`spectrum.py:753`) ist eine
Python-Schleife über 131 072 Werte, die eine Liste einzelner `complex`-Objekte aufbaut.
Auf dem Pi kostet das Sekunden, nicht Millisekunden, und ist in drei Zeilen mit
`np.frombuffer` ersetzbar.

**Die Falle:** wer SA5 allein behebt, macht die WebUI **schlechter**. Dann liefert der
Endpunkt korrekt einen Snapshot, und zwei Megabyte Rohzahlen landen als Text im `<pre>`.
Deshalb die Reihenfolge in §3.

---

## 2. Arbeitspakete Teil A

### SA-A — Ausgabeargument ergänzen

`spectrum.py:844`: `"-"` als letztes Element der Argumentliste. Prüfen, ob
`sweep_fm_band` über `capture_spectrum` läuft (ja) und damit mitgeheilt ist.

Gegenprobe am Pi, ohne WebUI:

```bash
pidrivectl stop
python3 -c "from modules.radio import spectrum; r=spectrum.capture_spectrum(446.1); \
print(r.get('ok'), r.get('error',''), len(r.get('spectrum_db',[])))"
```

Erwartung: `True`, kein Fehler, Bin-Zahl > 0. Vorher: `False keine IQ-Daten 0`.

### SA-B — serverseitig dezimieren

`capture_spectrum` um eine gezeichnete Spur ergänzen, **zusätzlich** zu den bestehenden
Feldern, damit `/api/spectrum/stations` und die Peak-Auswertung unberührt bleiben:

| neues Feld | Inhalt |
|---|---|
| `trace_max` | je Eimer der Höchstwert in dB, Vorgabe 680 Eimer |
| `trace_min` | je Eimer der Tiefstwert in dB |
| `trace_bins` | Anzahl der Eimer |
| `trace_start_mhz`, `trace_stop_mhz` | Frequenzbezug der Spur |

Zwei Werte je Eimer, weil eine reine Mittelung schmale Spitzen verschluckt — genau die,
die der Betreiber sehen will.

`spectrum_db` nur noch auf ausdrückliches Verlangen ausliefern (`full=1`), sonst
weglassen. Damit fällt die Antwort von rund zwei Megabyte auf wenige Kilobyte.

Im selben Zug `_u8_iq_to_complex_legacy` durch `np.frombuffer(raw, dtype=np.uint8)` mit
Umrechnung in `complex64` ersetzen. Messbarer Nebeneffekt, kein Verhaltensunterschied.

### SA-C — Renderer in `rf-tools.html`

Zeichenfläche wieder einbauen, Vorlage `index_legacy.html:2305`, aber gegen die neuen
Felder aus SA-B statt gegen `spectrum_db`. Drei Fälle unterscheiden:

| Antwort enthält | Darstellung |
|---|---|
| `trace_max` | Kurve mit dB-Achse und Frequenzbeschriftung, Spitzen markiert |
| `windows` | Balken je Fenster, x-Achse = Mittenfrequenz (Sweep) |
| `data.active_channels` | Balken je Kanal mit Name und Bewertung (Bandpfad) |
| keines davon oder `ok:false` | **Fehlertext in die Fläche malen**, nicht stumm bleiben |

Der letzte Fall ist wichtig: der Altstand hat das gemacht, und genau deshalb war dort
sichtbar, wenn eine Messung scheiterte.

### SA-D — Betriebsart und Feldnamen richtigstellen

- Auswahlfeld für Betriebsart wieder einbauen (Snapshot / FM-Sweep / PMR446 / Freenet)
- `mode` mitsenden, beim Snapshot `center_mhz` statt `center`
- **Oder** serverseitig `center` als Zweitnamen akzeptieren — dann sind Altaufrufe robust
- Antwort des Aufrufs **direkt** verwenden, blindes `setTimeout(..., 8000)` entfernen
- Solange die Messung läuft, Knopf sperren und Zustand anzeigen

**Erst nach SA-A, SA-B und SA-C.** Sonst siehe SA7.

### SA-E — welle-cli-Diagnosemodus (getrennt, optional)

Eigener Schalter auf der RF-Seite: `welle-cli -c <Kanal> -w 8000` starten, Verweis auf
`http://<pi>:8000` anzeigen, Prozess bei Verlassen beenden. Bringt Spektrum,
Konstellation, Impulsantwort und TII für DAB ohne eigenen Zeichencode.

Bedingungen, ohne die das Schaden anrichtet:

- belegt den RTL-SDR → vorher `radio_stop`, Quelle auf `idle` festschreiben
- `find_rtl_processes()` erkennt `welle-cli` bereits, also wird die Belegung korrekt gemeldet
- Zeitablauf, damit ein vergessener Diagnosemodus nicht dauerhaft den Stick hält
- in der Oberfläche klar als Diagnose kennzeichnen, nicht als Wiedergabe

**Ersetzt SA-A bis SA-D nicht.** Deckt nur Band III ab.

### SA-F — Altstand erst danach entfernen

`index_legacy.html`, `index_full.html` und `legacy/index_legacy.html` sind rund 365 kB
totes Gewicht. **Sie enthalten aber den einzigen Zeichencode.** Löschen erst, wenn SA-C
abgenommen ist.

---

## 3. Reihenfolge Teil A

1. **K1** aus [AUFTRAG-FUNKPFAD.md](AUFTRAG-FUNKPFAD.md) — ohne Gerätereservierung ist
   jede Messung zufällig
2. **SA-A** — ohne Ausgabeargument gibt es keine Daten
3. **SA-B** — Dezimierung, bevor irgendetwas die Antwort anzeigt
4. **SA-C** — Renderer
5. **SA-D** — Betriebsart
6. **SA-F** — aufräumen
7. **SA-E** — optional, jederzeit danach

Schritt 2 und 3 nie tauschen, Schritt 5 nie vorziehen.

---

# TEIL B — AVRCP-MESSBÜHNE

## 4. Befunde

### AV1 — was der Tab heute kann, und wo er aufhört `[BELEGT]`

`/api/avrcp` (`app.py:786`) liest ausschließlich `/tmp/pidrive_avrcp.json`, geschrieben
von `_write_debug_full` (`avrcp_trigger.py:346`):

| Feld | Inhalt |
|---|---|
| `last_event` | AVRCP-Ereignis, etwa `next`, `volumeup` |
| `trigger` | erzeugter PiDrive-Befehl, etwa `dab_next` |
| `context` | `menu` / `radio` / `scanner` / `list_overlay` |
| `event_count` | Gesamtzahl seit Dienststart |
| `ctx.*` | Quelle, Radiotyp, Sendername, Band, Menüpfad, Listenzustand |

**Damit prüfbar:** kommt ein Tastendruck überhaupt an, welcher, wie wurde er gedeutet,
in welchem Kontext. Für die Frage „erreicht das Rad PiDrive und wird es richtig
interpretiert" reicht das.

**Grenze:** es ist **immer nur das letzte Ereignis**. Jeder weitere Druck überschreibt.
Eine Folge von Raddrehungen ist so nicht auswertbar.

### AV2 — der Ringpuffer wird geschrieben, aber nicht ausgeliefert `[BELEGT]`

`avrcp_trigger.py:44–48` hält die letzten **dreißig** Ereignisse und schreibt sie nach
`/tmp/pidrive_avrcp_events.json`, je Eintrag `id`, `ts`, `event`, `trigger`, `context`,
`source`, `ms`. Der Quelltextkommentar nennt das „P0.8 — Gold im Feldtest".

Leser:

| Ort | Zugriff |
|---|---|
| `cli.py:1758` | `pidrivectl debug avrcp` |
| `cli.py:1777` | `pidrivectl avrcp monitor` |
| `test_suite.py:498`, `:919`, `:924` | Abnahmetests |
| **WebUI** | **keiner** |

**Die bessere Datei existiert, der Browser sieht die schlechtere.** Das ist der billigste
Ausbau des ganzen Dokuments: eine Route, keine neue Messung.

**Für die Probefahrt heute genügt die CLI.** Verfügbar sind (`cli.py:428`):

| Befehl | Wirkung |
|---|---|
| `pidrivectl avrcp monitor` | laufende Anzeige, pollt den Ringpuffer alle 300 ms, neue Ereignisse grün, wenn ein Trigger entstand |
| `pidrivectl avrcp events` | die letzten 20 Einträge auf einmal, mit `--json` der ganze Puffer |
| `pidrivectl avrcp inject next` | Tastendruck ohne Fahrzeug einspeisen — für Werkbanktests von AV-B |
| `pidrivectl debug avrcp` | Ringpuffer als Rohdaten |

`pidrivectl avrcp monitor` ist damit heute schon das brauchbarste Werkzeug am Fahrzeug —
besser als der Tab im Browser.

### AV3 — das `ms`-Feld misst die falsche Strecke `[BELEGT]`

`handle_avrcp` setzt `t0` beim Eintritt (`avrcp_trigger.py:286`) und übergibt in Zeile 341
`int((time.time() - t0) * 1000)`. Gemessen werden also Kontextdateien lesen, Mapping und
Schreiben nach `CMD_FILE` — einstellige Millisekunden.

Die interessante Größe ist **Raddrehung bis Anzeige im BMW**. Die endet erst beim
MPRIS-Push in `main_core.py` und ist derzeit **nirgends gemessen**. Wer `ms` als Latenz
liest, bekommt eine beruhigend kleine Zahl, die nichts über das Display sagt.

### AV4 — nur Eingangsrichtung; für Teil D fehlt die Gegenrichtung `[BELEGT]`

Für die Abnahme des Menüvorrangs (Teil D, v0.11.138) braucht man vier Dinge, von denen
keines im Tab steht: welche Ansicht gesendet wurde (`menu` oder `auto`), mit welchen
Feldern, welcher Wiedergabestatus, und **wie viele Pushes verworfen wurden**.

Zum letzten Punkt, `mpris2.py:82`:

```python
_track_changed = (track_nr != self._last_trackid)
if not _track_changed and (_now - self._last_emit) < 0.3:
    return
```

Verworfen wird **still**, ohne Zähler. Und `mpris2.py:450` hält `track_nr` bewusst
konstant auf 1, damit die Bremse überhaupt greift (Q-M). Folge: **jede Menübewegung
innerhalb von 300 ms fällt weg.**

Beim zügigen Drehen am iDrive ist das genau der Fall, der den Betreiber interessiert.
Ohne Zähler ist nicht unterscheidbar, ob die Anzeige hinterherhängt oder ob der Push nie
stattgefunden hat. **Das ist die wichtigste Erweiterung in Teil B.**

### AV5 — das Rohprotokoll ist aus dem Browser nicht erreichbar `[BELEGT]`

`avrcp_trigger.py:42` schreibt jede rohe D-Bus-Zeile nach
`/var/log/pidrive/avrcp_raw.log`. `/api/logs?target=avrcp` (`app.py:459`) liest dagegen
`journalctl -u pidrive_avrcp` mit Rückfall auf `avrcp.log` — **nicht** `avrcp_raw.log`.

Der Knopf „Log laden" im Tab zeigt also nicht die detaillierteste Quelle. Die ist nur
über SSH erreichbar.

### AV6 — die Browsing-Frage ist hier grundsätzlich nicht beantwortbar `[BELEGT]`

`monitor_dbus` (`avrcp_trigger.py:510`) hört auf `org.mpris.MediaPlayer2.Player`,
`org.bluez.MediaPlayer1`, `org.bluez.MediaControl1` und `PropertiesChanged` unter
`/org/bluez/hci0`.

Der AVRCP-Browsing-Kanal ist ein **eigener L2CAP-Kanal auf PSM `0x001B`**. BlueZ bildet
ihn nicht auf D-Bus ab. Kein Ausbau dieses Tabs kann sichtbar machen, ob der BMW ihn
öffnet.

**Dafür zuständig bleibt** `tools/bmw_avrcp_probe.sh` mit `btmon`, ausgewertet von
`tools/bmw_avrcp_analyze.py`. Dieser Befund steht hier ausdrücklich, damit niemand
versucht, die Stackentscheidung A17 über den AVRCP-Tab zu beantworten.

### AV7 — `pidrivectl avrcp status` zeigt auf eine Datei, die niemand schreibt `[BELEGT]`

`cli.py:1778` definiert `AVRCP_STATUS = "/tmp/pidrive_avrcp_status.json"`. **Niemand
schreibt diese Datei.** `cli.py:1819` liest sie und meldet im Fehlerfall:

```
Kein AVRCP-Status (noch kein Event eingegangen)
```

Diese Meldung ist irreführend: sie erscheint **immer**, auch nach hundert Tastendrücken.
Die Felder, die dort erwartet werden — `ts_human`, `last_event`, `trigger`, `context` —
stehen vollständig in `/tmp/pidrive_avrcp.json`, geschrieben von `_write_debug_full`.
**Die CLI zeigt auf den falschen Dateinamen.**

Ein Ein-Zeilen-Fehler mit einer Meldung, die den Prüfer in die falsche Richtung schickt:
er glaubt, der AVRCP-Dienst empfange nichts, obwohl er längst läuft. Sofort behebbar,
unabhängig von allen anderen Paketen.

### AV8 — doppelte Ereignis-Kennung bei ignorierten Tasten `[ANALYSE]`

`avrcp_trigger.py:341` übergibt `_event_count` als `id`, aber erhöht wird der Zähler nur
in `write_cmd` (`:138`). Ohne Mapping wird `write_cmd` nicht gerufen, die nächste
Kennung wiederholt sich. Kosmetisch, stört aber beim Auswerten einer Tabelle.

---

## 5. Arbeitspakete Teil B

### AV-A — Ringpuffer ausliefern

Neue Route `/api/avrcp/events`, liest `/tmp/pidrive_avrcp_events.json`, gibt `events`,
`total`, `age` und `exists` heraus. Muster: `api_avrcp` in `app.py:786`. Dateipfad als
Konstante nach `web/shared/constants.py`, nicht wörtlich in die Route.

Kein neuer Messcode. **Das Paket mit dem größten Verhältnis von Nutzen zu Aufwand.**

### AV-B — Tabelle statt JSON-Auswurf

`avrcp.html` ersetzt den `<pre>`-Auswurf durch:

| Spalte | Quelle |
|---|---|
| Zeit | `ts_human` beziehungsweise `ts` |
| Ereignis | `event` |
| → Befehl | `trigger`, leer als „ignoriert" kennzeichnen |
| Kontext | `context` |
| Quelle | `source` |

Darüber eine Kopfzeile mit Verbindungszustand, Gerät, `total` und Alter der Datei.
Vorbild für die Machart ist `bluetooth.html` — die einzige Seite, die Zustände heute
schon übersetzt statt sie auszuschütten.

Neueste Zeile oben, Selbstauffrischung im Sekundentakt, damit die Seite im Fahrzeug
mitläuft. Den doppelten `_logText`-Helfer (F11) dabei gleich zusammenführen.

### AV-C — Gegenrichtung erfassen

`mpris2.py` additiv um ein Push-Protokoll ergänzen, **ohne** Q-M anzutasten:

| Feld | Inhalt |
|---|---|
| `last_push_ts` | Zeitpunkt des letzten wirklich gesendeten `PropertiesChanged` |
| `last_view` | `menu` oder `auto` |
| `last_fields` | gesendete Werte für Titel, Interpret, Album |
| `last_playback_status` | wie gesendet |
| `push_count` | Zahl gesendeter Pushes |
| `drop_count` | **Zahl der von der 300-ms-Bremse verworfenen Pushes** |

Ablage in `/tmp/pidrive_avrcp_status.json` — **damit wird AV7 aufgelöst statt gelöscht**:
die Datei, auf die `pidrivectl avrcp status` seit immer zeigt, existiert dann wirklich.
Die dort erwarteten Felder `ts_human`, `last_event`, `trigger`, `context` mitschreiben,
damit der bestehende CLI-Befehl unverändert funktioniert.

Ausliefern über `/api/avrcp/push`, anzeigen als zweiter Block in `avrcp.html`.

Der einzige Eingriff in `mpris2.py` ist ein Zähler im bestehenden `return`-Zweig von
Zeile 82 plus eine Schreibfunktion. Kein geändertes Sendeverhalten.

### AV-D — Ende-zu-Ende-Latenz messbar machen

Ringpuffer-Eintrag um `ts_push` und `ms_total` ergänzen: Zeitstempel des MPRIS-Pushes,
der aus diesem Ereignis folgte, und die Differenz zu `ts`.

Einfachster tragfähiger Weg: `main_core.py` schreibt beim Push den Zeitstempel des
zuletzt verarbeiteten Triggers mit; die Zuordnung erfolgt über den Trigger-Text. Bei
mehreren Ereignissen innerhalb eines Zyklus wird dem jüngsten zugeordnet — das ist
ungenau, aber für die Frage „drei Sekunden oder dreißig Millisekunden" ausreichend.

`ms` **nicht** umdeuten, sondern als `ms_map` umbenennen. Sonst vergleicht man später
Zahlen aus zwei Epochen.

### AV-E — Rohprotokoll als Log-Ziel

`app.py:459` um `target=avrcp_raw` erweitern, liest
`tail -n 200 /var/log/pidrive/avrcp_raw.log`. Im Tab als weitere Auswahl anbieten.

### AV-F — Kleinigkeiten

- **AV7 als Sofortmaßnahme, falls AV-C später kommt:** `cli.py:1778` auf
  `/tmp/pidrive_avrcp.json` zeigen lassen. Zwei Zeichen, und
  `pidrivectl avrcp status` hört auf zu lügen. Wenn AV-C gebaut wird, kann der
  Dateiname wieder auf `..._status.json` wechseln — dann existiert sie.
- AV8: `_event_count` auch bei ignorierten Ereignissen erhöhen, oder eine eigene,
  monoton steigende Kennung einführen
- `avrcp.html`: Hinweis einbauen, dass die Browsing-Frage nur über `btmon` beantwortbar
  ist, mit Verweis auf `tools/bmw_avrcp_probe.sh`. Eine Zeile, die verhindert, dass
  jemand hier sucht, was hier nicht sein kann

---

## 6. Abnahme am Fahrzeug

Voraussetzung: v0.11.138 ist auf dem Pi, AVRCP-Dienst läuft, BMW verbunden.

### HS1 — Spektrum am Schreibtisch (Teil A, ohne Fahrzeug)

```bash
pidrivectl stop
python3 -c "from modules.radio import rtlsdr; print('busy=', rtlsdr.is_busy(), \
rtlsdr.find_rtl_processes())"        # muss leer / False sein
python3 -c "from modules.radio import spectrum; r=spectrum.capture_spectrum(446.1); \
print(r['ok'], len(r.get('trace_max',[])), r.get('trace_bins'))"
```

Ein `pidrivectl`-Unterbefehl für den Gerätezustand existiert nicht — `rtl` steht nicht in
der Befehlsliste. Falls AV/SA häufiger gemessen wird, lohnt `pidrivectl debug rtl` als
Ergänzung; kein Pflichtteil dieses Auftrags.

Bestanden, wenn `ok=True` und `trace_bins` der Vorgabe entspricht. Danach in der WebUI
auf der RF-Seite Betriebsart „Snapshot", Mitte 446.1, und **eine Kurve** sehen.

### HS2 — drei Antwortformen (Teil A)

Je einmal Snapshot, FM-Sweep und PMR446 auslösen. Bestanden, wenn jede Betriebsart eine
passende Darstellung erzeugt und keine eine leere Fläche hinterlässt.

### HS3 — Nutzlast (Teil A)

```bash
curl -s -X POST "http://localhost:8080/api/spectrum/capture?mode=snapshot&center_mhz=446.1" | wc -c
```

Bestanden unter 100 000 Bytes. Vorher rund zwei Millionen.

### HA1 — Ereignisfolge (Teil B)

Im Fahrzeug fünfmal am Drehsteller weiterdrehen, dann Browser auf den AVRCP-Tab.
Bestanden, wenn **fünf** Zeilen mit aufsteigender Zeit stehen, jede mit Kontext und
erzeugtem Befehl. Vorher war nur die letzte sichtbar.

### HA2 — verworfene Pushes (Teil B, wichtigster Test)

Zügig zehnmal in unter drei Sekunden drehen. `drop_count` vorher und nachher notieren.

- `drop_count` steigt → die Bremse greift, die Anzeige kann der Drehung nicht folgen.
  Dann ist die Bremse für den Menüvorrang zu träge und muss für Menüansichten
  angehoben werden.
- `drop_count` bleibt → die Bremse ist nicht die Ursache; falls die Anzeige dennoch
  hinterherhängt, liegt es am BMW oder an der Auffrischung im Kern.

**Dieser Test entscheidet, ob Teil D im Fahrzeug so funktioniert wie beschrieben.**

### HA3 — Ende-zu-Ende-Latenz (Teil B)

Nach AV-D: einmal drehen, `ms_total` ablesen. Erwartung im einstelligen bis niedrigen
zweistelligen Bereich. Dreistellig oder mehr erklärt ein zähes Bediengefühl.

### HA4 — Abgrenzung zum btmon-Pfad (Teil B)

Bestanden, wenn im Tab der Hinweis auf `bmw_avrcp_probe.sh` steht und **keine**
Browsing-Aussage behauptet wird.

---

## 7. Was ausdrücklich nicht gemacht wird

- **Kein Versuch, die Browsing-Frage im AVRCP-Tab zu beantworten.** Siehe AV6.
- **Kein Löschen der Altvorlagen vor SA-C.** Siehe SA-F.
- **Kein Umbau des Sendeverhaltens in `mpris2.py`.** AV-C ist rein additiv; über eine
  Änderung der 300-ms-Bremse wird erst nach HA2 entschieden, nicht davor.
- **Kein welle-cli als Ersatz für `capture_spectrum`.** Siehe SA1.
- **Kein SA-D vor SA-B.** Siehe SA7.
- **Kein Entfernen von `spectrum_db`,** nur das Weglassen aus der Vorgabeantwort.
  `/api/spectrum/stations` und die Peak-Auswertung hängen an der Funktion.

---

## 8. Entscheidungen für den Betreiber

| Nr. | Frage | Vorschlag |
|---|---|---|
| E-SA1 | Soll der welle-cli-Diagnosemodus (SA-E) gebaut werden, obwohl er den Stick belegt und nur DAB abdeckt? | ja, aber zuletzt — der Nutzen für DAB-Fehlersuche ist hoch, der Aufwand klein |
| E-SA2 | Auflösung der Spur: 680 Punkte wie der Altstand, oder feiner für Zoom? | 680 zunächst; Zoom bedeutet Zustandsverwaltung im Browser |
| E-SA3 | Snapshot-Bandbreite bei 2,048 MHz belassen? Für PMR446 (200 kHz belegt) ist das viel Leerraum | belassen — ein schmaleres Fenster kostet Empfindlichkeit an den Rändern |
| E-AV1 | Soll `avrcp.html` sich selbst auffrischen (Sekundentakt) oder nur auf Knopfdruck? | Sekundentakt, im Fahrzeug will man mitlesen |
| E-AV2 | Ringpuffer bei 30 Einträgen belassen? Für eine Fahrt wenig | auf 200 anheben — die Datei bleibt unter 30 kB |
| E-AV3 | Nach HA2: wenn die Bremse greift, für Menüansichten lockern (etwa 100 ms) oder die Ansicht zusammenfassen? | erst messen, dann entscheiden |

---

## 9. Bezug zu bestehenden Dokumenten

| Dokument | Bezug |
|---|---|
| [AUFTRAG-FUNKPFAD.md](AUFTRAG-FUNKPFAD.md) | K1 ist Voraussetzung für jede Spektrummessung |
| [AUFTRAG-WEBUI-SANIERUNG.md](AUFTRAG-WEBUI-SANIERUNG.md) | F1/F2/F3 dort sind hier als SA5/SA3/SA7 präzisiert; F11 wird von AV-B mitgeheilt |
| [AUFTRAG-QUELLENSTART-UND-SUCHLAUFANZEIGE.md](AUFTRAG-QUELLENSTART-UND-SUCHLAUFANZEIGE.md) | Teil D wird durch HA2 erstmals messbar; Q-M bleibt unberührt |
| [AUFTRAG-DISPLAY-RUECKMELDUNG.md](AUFTRAG-DISPLAY-RUECKMELDUNG.md) | D2 (verspätete Anzeige) wird durch AV-D belegbar statt vermutet |
| `tools/bmw_avrcp_probe.sh` | bleibt der einzige Weg zur Browsing-Frage, siehe AV6 |
