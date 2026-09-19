> **Arbeitsauftrag — Rückmeldung ans Fahrzeugdisplay**
> Stand: 2026-09-15 · Basis: v0.11.128 (`f749a42`) · Befund-Präfix: **D**

---

## 0. Zweck und Abgrenzung

Dieses Dokument ist **neu angelegt**, weil parallel an
[AUFTRAG-WEBUI-SANIERUNG.md](AUFTRAG-WEBUI-SANIERUNG.md) gearbeitet wird. Es gilt
**ein Schreiber pro Datei**: an jener Datei arbeitet die andere Instanz, an dieser hier
niemand sonst.

Die Befunde tragen das Präfix **D** (Display), damit keine Nummer mit S, V, C, F, W, Z,
E, H, R, M, G, B oder K kollidiert. Sie waren zwischenzeitlich als S14–S16 in
`AUFTRAG-WEBUI-SANIERUNG.md` eingetragen; dieser Eintrag wurde zurückgenommen, um den
Konflikt zu vermeiden. Abschnitt 7 nennt, was dort später nachzuziehen ist.

**Verhältnis zu den anderen Aufträgen:**

| Auftrag | Thema | Verhältnis |
|---|---|---|
| [AUFTRAG-FUNKPFAD.md](AUFTRAG-FUNKPFAD.md) | Importpfade, Bandbreite, Suchlauf (K1–K5) | **Zuerst.** Dringender und billiger. Achtung: **D3 und K1–K4 fassen beide `scanner.py` an** — verschiedene Stellen, aber dieselbe Datei |
| `AUFTRAG-WEBUI-SANIERUNG.md` | WebUI, Scanner, FastScan, Zustandsmaschine (W0–W11) | D2 ist verwandt mit P-F1, aber ein eigener Fehler. Keine Überschneidung im Code |
| `esp32.bt-gateway` / `AUFTRAG-CURSOR-4.md` | Gateway-Planung | D1 ist dort **P-F6**, D3 ist dort **P-F7**, D2 ist dort **P-F8** |

---

## 1. Ausgangslage

Die drei Befunde sind bei der Mockup-Arbeit am iDrive-Menü am 2026-09-15 aufgefallen. Der
Eigentümer bemerkte zunächst, dass die Menüeinträge „System-Info" und „Version" am BMW
nichts bewirken, und anschließend, dass dieselbe Meldung auch bei „Nächster Sender",
„Suchlauf starten" und „Frequenz manuell" erschien.

Die Prüfung ergab **drei verschiedene Ursachen**, die nicht zusammengeworfen werden
dürfen — die Korrekturen sind vollständig verschieden:

| | Betroffen | Wirkung |
|---|---|---|
| **D1** | `sys_info`, `sys_version` | dauerhaft unsichtbar |
| **D2** | Radio- und Favoritenaktionen | wirkt, aber Anzeige kommt verspätet |
| **D3** | „Frequenz manuell" und zwei Scanner-Eingaben | friert das Menü ein und stiehlt Tastendrücke |

Gemeinsam ist ihnen nur der Ort, an dem sie sichtbar werden: die drei
AVRCP-Metadatenfelder am BMW.

---

## 2. Befunde

### D1 Der Rückmeldekanal für Aktionen endet vor dem Fahrzeug `[BELEGT]` — hoch

„System-Info" und „Version" landen über `trigger/td_system.py:101-104` in
`modules/system.py:27-51` und melden ihr Ergebnis ausschließlich über
`ipc.write_progress()`:

```
ipc.py:15    PROGRESS_FILE = "/tmp/pidrive_progress.json"
ipc.py:131   def write_progress(title, message="", pct=None, lines=None, color="blue"):
ipc.py:132       write_json(PROGRESS_FILE, { … })
```

Diese Datei wird gelesen von `cli/adapters.py`, `cli/cli.py`, `cli/service.py` und
`web/shared/constants.py` — also **nur von CLI und WebUI**. Gegenprobe: weder `mpris2.py`
noch `main_core.py` enthalten das Wort `progress`. Der Fortschritts- und Ergebniskanal
erreicht das BMW-Display damit **nie**.

**Ein Push findet dabei durchaus statt.** Das ist für die Fehlersuche wichtig:
`check_trigger()` (`main_core.py:177-209`) gibt für jedes behandelte Kommando `True`
zurück, daraufhin läuft `rebuild_tree()` (`main_core.py:630-631`) und erhöht über
`menu_state.rebuild()` den Revisionszähler (`menu_state.py:290`). Der Push geht also raus,
er trägt nur nichts Neues, weil die Nutzlast im Overlay steckt. Wer am Display debuggt,
sieht einen Aktualisierungszyklus **ohne Wirkung** — nicht das Ausbleiben eines Zyklus.

**Umfang:** `ipc.write_progress()` hat **104 Aufrufstellen** (ohne `ipc.py` selbst):

| Modul | Stellen | Was dort gemeldet wird |
|---|--:|---|
| `modules/bluetooth/bt_connect.py` | 19 | Kopplung, Verbindungsaufbau, Fehlerursachen |
| `trigger/td_radio.py` | 16 | Quellenwechsel, Suchlauf |
| `trigger/td_hardware.py` | 15 | Spotify, Radio-Stop, Bibliothek |
| `modules/update.py` | 12 | Update-Fortschritt |
| `modules/audio.py` | 9 | Routenwechsel |
| `modules/radio/scanner.py` | 8 | Scan-Fortschritt, Kanalwechsel |
| `modules/wifi.py` | 7 | Netzwerk-Scan, Verbindung |
| übrige | 18 | DAB-Scan, Favoriten, System, FM |

Im Fahrzeug ist damit **kein** Fortschritt und **keine** Fehlermeldung sichtbar — weder
„Gerät verbunden" noch „Suchlauf 7/38" noch „RTL-SDR belegt".

**Nicht zu verwechseln mit S1** (Aktualität wird berechnet, aber nicht angezeigt). Dort ist
der Empfänger das WebUI und der Weg kurz. Hier ist der Empfänger das Fahrzeugdisplay, und
der einzige Kanal dorthin sind drei Textfelder. Ein Fortschrittsbalken lässt sich darüber
nicht abbilden, eine Textzeile schon. Wie das aussehen soll, ist eine Entscheidung und
keine Reparatur — siehe **E-D1**.

**Abgrenzung.** D1 betrifft nur Aktionen, deren Ergebnis *ausschließlich* im Overlay lebt —
nachgewiesen für `sys_info` und `sys_version`. Radioaktionen sind D2, „Frequenz manuell"
ist D3.

### D2 Der Push kommt vor der Wirkung `[BELEGT]` — hoch

**Dies ist die Ursache des „Display friert zwischen zwei Tastendrücken ein".**

Bei „Nächster Sender", „Suchlauf starten" und „Aktuellen Sender merken" wirkt die Aktion,
aber das Display zeigt weiter den alten Zustand. Die Kette läuft in falscher Reihenfolge:

1. `check_trigger()` behandelt das Kommando und gibt `True` zurück (`main_core.py:209`).
2. Die Aktion wird über `bg(...)` in einen **Hintergrundthread** gegeben — etwa
   `td_radio.py:420-425` für `fm_next`. Der Aufruf kehrt sofort zurück.
3. `main_core.py:630-631` ruft daraufhin `rebuild_tree()`, der Revisionszähler steigt, der
   Push geht raus. **In `S` steht zu diesem Zeitpunkt noch der alte Sender.**
4. Der Hintergrundthread stellt danach den neuen Sender ein. Ein zweiter Push müsste über
   `S["menu_rev"]` angestoßen werden (`main_core.py:633-637`).

Genau Schritt 4 fehlt. Gegenprobe über alle Schreibzugriffe auf `S["menu_rev"]`:

| Modul | Bumps | |
|---|--:|---|
| `modules/bluetooth/bt_connect.py` | 12 | macht es richtig |
| `modules/wifi.py` | 3 | macht es richtig |
| `trigger/td_nav.py` | 2 | macht es richtig |
| `trigger/td_hardware.py` | 2 | macht es richtig |
| `modules/bluetooth/bt_devices.py` | 1 | macht es richtig |
| `modules/radio/fm.py` | **0** | |
| `modules/radio/dab_play.py` | **0** | |
| `modules/radio/scanner.py` | **0** | |
| `modules/webradio.py` | **0** | |
| `modules/favorites.py` | **0** | |

Der neue Sender erscheint deshalb erst beim nächsten unabhängigen Ereignis: einem weiteren
Tastendruck, einem Bluetooth-Ereignis, oder dem 10-Sekunden-Takt von
`store.reload_if_changed()` (`main_core.py:647`) — letzteres nur, wenn sich die Senderdatei
geändert hat, was bei `fm_next` nicht zutrifft.

**Korrektur:** eine Zeile `S["menu_rev"] = S.get("menu_rev", 0) + 1` am Ende der jeweiligen
Aktion. Das Muster steht bereits zwölfmal in `bt_connect.py` — **kein neues erfinden.**

Im WebUI fällt derselbe Fehler kaum auf, weil dort im 2-Hz-Takt gepollt wird. Am BMW gibt
es kein Polling, nur den Push. Das erklärt, warum der Eindruck „im Browser geht es, im Auto
nicht" entsteht.

**Nicht identisch mit P-F1** (`mpris2.update()` nur bei Revisionsänderung). P-F1 beschreibt
die Kopplung, D2 die verpasste Gelegenheit, sie auszulösen. Beide müssen behoben werden,
sonst bleibt auch der DLS-Titelwechsel weiterhin aus.

### D3 „Frequenz manuell" friert das Menü ein und stiehlt Tastendrücke `[BELEGT]` — kritisch

Der Menüeintrag `fm_manual` (`menu_builder.py:241`) führt über `td_nav.py:238-241` zu
`fm.freq_input_screen()` (`fm.py:360-389`). Diese Funktion läuft **bis zu 60 Sekunden** in
einer Schleife und liest darin alle 0,15 s die Kommandodatei **direkt**:

```
fm.py:370       if not os.path.exists(ipc.CMD_FILE):
fm.py:374       cmd = open(ipc.CMD_FILE).read().strip()
fm.py:375       os.remove(ipc.CMD_FILE)
```

Drei Folgen, jede für sich ein Fehler:

1. **Die Schleife umgeht `ipc.drain_triggers()`** und nimmt der Hauptschleife die
   Tastendrücke weg. Für genau diesen Zweck existiert der `LIST_FILE`-Mechanismus, den
   `main_core.py:181-193` auswertet und `local_player.py:47` korrekt benutzt —
   `freq_input_screen()` meldet sich dort **nicht** an.
2. **Beide Seiten lesen und löschen dieselbe Datei.** `main_core.py:188-190` und
   `fm.py:370-375` konkurrieren ohne Sperre. Wer einen Tastendruck bekommt, ist
   nichtdeterministisch — die Frequenzeingabe verliert Tasten an das Menü und umgekehrt.
3. **Der Fahrer sieht nichts.** Der eingestellte Wert steht ausschließlich im
   Fortschritts-Overlay (`fm.py:365-369`), erreicht das BMW also nicht (D1). Er drückt
   Tasten, verstimmt unsichtbar den Empfänger, und nach 60 s bricht die Schleife stumm ab.

**Dasselbe Muster dreifach:** `fm.py:370-375`, `scanner.py:718-723` (`_freq_input`) und
`scanner.py:761-767` (`freq_input_screen`).

Die Bewertung „kritisch" begründet sich nicht über Funktionsverlust, sondern über den
Kontext: eine bis zu 60 Sekunden nicht bedienbare Anlage, ohne jede Anzeige warum, ist
während der Fahrt eine Ablenkungsquelle.

**Sofortentschärfung**, falls die saubere Lösung warten muss: den Eintrag `fm_manual` aus
dem Menübaum nehmen und die Frequenzeingabe dem WebUI überlassen, wo sie funktioniert. Das
ist eine Zeile in `menu_builder.py:241` und nimmt dem Fahrer nichts, was er heute nutzen
könnte — er sieht die Eingabe ohnehin nicht.

---

## 3. Arbeitsschritte

| # | Schritt | Datei(en) | Umfang |
|---|---|---|---|
| 1 | **D3 Sofortentschärfung** — `fm_manual` aus dem Menü nehmen | `menu_builder.py:241` | 1 Zeile |
| 2 | **D2** — `menu_rev` am Ende der Aktionen erhöhen | `fm.py`, `dab_play.py`, `scanner.py`, `webradio.py`, `favorites.py` | 1 Zeile je Modul |
| 3 | **D3 saubere Lösung** — Eingabeschleifen über `LIST_FILE` anmelden oder auf `drain_triggers()` umstellen | `fm.py:360-389`, `scanner.py:709-780` | mittel |
| 4 | **D1** — Entscheidung E-D1 einholen, dann Meldungsweg bauen | `mpris2.py`, `main_core.py` | nach Entscheidung |
| 5 | Tests aus Abschnitt 5 ergänzen, in `run_all()` aufnehmen | `test_suite.py` | — |
| 6 | `VERSION` anheben, Abnahme in `docs/ABNAHMEN.md` | — | — |

**Reihenfolge-Hinweis:** Schritt 1 und 2 sind billig und unabhängig. Schritt 3 fasst
`scanner.py` an — deshalb **nach** Abschluss von [AUFTRAG-FUNKPFAD.md](AUFTRAG-FUNKPFAD.md),
das dieselbe Datei an anderen Stellen ändert. Schritt 4 braucht erst eine Entscheidung.

**D2 hat eine Abhängigkeit zu P-F1:** solange `mpris2.update()` nur bei Änderung der
Menü-Revision läuft, wirkt der `menu_rev`-Bump aus Schritt 2 genau richtig — er erhöht die
Revision. Wird P-F1 später entkoppelt, bleibt Schritt 2 trotzdem korrekt, weil er den
tatsächlichen Zustandswechsel anzeigt. Die beiden Korrekturen widersprechen sich nicht.

---

## 4. Hardware-Verifikation am Pi

Host `192.168.178.105`. Jede Messung nennt den Commit-Hash (H0).

### D1 — am Schreibtisch

```bash
echo sys_version > /tmp/pidrive_cmd
sleep 1
cat /tmp/pidrive_progress.json          # Overlay mit "Version 0.11.128"
python3 -c "import json;d=json.load(open('/tmp/pidrive_status.json'));print(d.get('progress'))"
```

Erwartung vor der Korrektur: das Overlay ist in `pidrive_progress.json` vorhanden, aber
nichts davon erreicht die MPRIS-Metadaten.

### D2 — braucht das Fahrzeug oder einen MPRIS-Mitschnitt

Ohne Fahrzeug, über die MPRIS-Schnittstelle:

```bash
# Metadaten vor und nach der Aktion vergleichen
pidrivectl now
echo fm_next > /tmp/pidrive_cmd
sleep 3
pidrivectl now                                   # zeigt noch den alten Sender?
echo down > /tmp/pidrive_cmd ; sleep 1
pidrivectl now                                   # jetzt der neue?
```

| | Erwartung |
|---|---|
| **vor** D2 | nach `fm_next` unverändert; erst nach dem `down` erscheint der neue Sender |
| **nach** D2 | direkt nach `fm_next` der neue Sender, ohne zusätzlichen Tastendruck |

Der zweite Tastendruck ist der eigentliche Beweis: er ändert inhaltlich nichts, löst aber
den Push aus. Genau das ist der Fehler.

### D3 — am Schreibtisch, deutlich sichtbar

```bash
echo fm_manual > /tmp/pidrive_cmd
sleep 1
# Menü-Navigation versuchen, während die Schleife läuft
echo down > /tmp/pidrive_cmd ; sleep 1
python3 -c "import json;print(json.load(open('/tmp/pidrive_menu.json')).get('rev'))"
```

| | Erwartung |
|---|---|
| **vor** D3 | `rev` bleibt stehen — der Tastendruck ist in der Eingabeschleife verschwunden. Bis zu 60 s lang |
| **nach** D3 | entweder Navigation funktioniert, oder der modale Zustand ist in `pidrive_menu.json` / der Statusdatei **ausgewiesen** |

Der Nachweis für Punkt 2 des Befunds (Wettlauf) braucht Wiederholung: denselben Test
zehnmal laufen lassen. Wenn der Tastendruck manchmal doch ankommt, ist die
Nichtdeterminiertheit belegt.

---

## 5. Tests, die mit diesem Paket entstehen

| Test | prüft | zu D |
|---|---|---|
| `test_action_feedback` | Nach `sys_version` ist die Information entweder in den MPRIS-Metadaten oder es ist dokumentiert, dass sie es nicht ist | D1 |
| `test_menu_rev_after_action` | `fm_next` erhöht `S["menu_rev"]`, ohne dass ein weiterer Tastendruck nötig ist | D2 |
| `test_no_command_theft` | Während einer Eingabeschleife bleibt die Menü-Navigation bedienbar, oder der modale Zustand ist ausgewiesen | D3 |
| `test_cmd_file_single_reader` | Statischer Test: kein Modul außer `ipc.py` und `main_core.py` liest `ipc.CMD_FILE` direkt | D3 |

`test_cmd_file_single_reader` ist der wertvollste — er schließt die Fehlerklasse statt des
Einzelfalls. Ein `grep`-artiger Test über den Quellbaum, wenige Zeilen, und er hätte alle
drei Eingabeschleifen sofort gefunden.

---

## 6. Was ausdrücklich nicht zu tun ist

- **`AUFTRAG-WEBUI-SANIERUNG.md` und `ZUSTANDSMASCHINE.md` nicht anfassen.** Nachträge
  stehen in Abschnitt 7.
- **Kein neues Rückmeldeformat erfinden, bevor E-D1 entschieden ist.** Drei Textfelder sind
  die harte Grenze; alles darüber hinaus braucht den Gateway-Menükanal.
- **Den `LIST_FILE`-Mechanismus nicht ersetzen.** Er ist vorhanden, funktioniert und wird in
  `main_core.py:181-193` ausgewertet. Die Eingabeschleifen müssen ihn benutzen, nicht
  umgekehrt.
- **`scanner.py` nicht parallel zu [AUFTRAG-FUNKPFAD.md](AUFTRAG-FUNKPFAD.md) bearbeiten.**
  Dieselbe Datei, verschiedene Stellen — aber gleichzeitige Arbeit erzeugt vermeidbare
  Konflikte.
- **Das Fortschritts-Overlay nicht abschaffen.** Es funktioniert für WebUI und CLI und ist
  dort richtig. Es fehlt nur ein zweiter Empfänger.
- **Keine Änderung an `mpris2.py` über das hinaus, was E-D1 festlegt.** P-F1 ist ein
  eigener Befund und gehört zur Gateway-Arbeit.

---

## 7. Nachzuziehen in anderen Dokumenten

Zur Einarbeitung durch die jeweiligen Eigentümer — **nach** Abschluss der laufenden Pakete.

### In `AUFTRAG-WEBUI-SANIERUNG.md`

| Was | Wie |
|---|---|
| D1–D3 als Befunde aufnehmen | entweder als S14–S16 am Ende von Kapitel 3, oder als Verweis auf dieses Dokument. **Verweis genügt** — doppelte Pflege ist die größere Gefahr |
| E-D1 in Abschnitt 11 aufnehmen | als E11, Text siehe Abschnitt 8 |
| Bezug bei S1 ergänzen | „nicht zu verwechseln mit D1 — dort ist der Empfänger das Fahrzeugdisplay" |

### In `docs/architektur/ZUSTANDSMASCHINE.md`

Die Sperrschicht 4 (RTL-SDR-`flock`, Tabelle bei L111-114) ist dort als **„0 — toter
Code"** geführt. Richtig ist **„unerreichbar"**: `acquire_lock()` (Z. 343),
`acquire_runtime_lock()` (Z. 300) und die Prozessverwaltung sind vollständig
implementiert, werden aber wegen eines Importfehlers nie erreicht. Ursache und Behebung
stehen als **K1** in [AUFTRAG-FUNKPFAD.md](AUFTRAG-FUNKPFAD.md); dieselbe Korrektur ist
bei L347 nachzuziehen.

Wichtig: eine frühere Fassung dieses Nachtrags sprach von „fehlenden Kompatibilitäts-Shims
`modules/rtlsdr.py` und `modules/spectrum.py`". Das beschreibt einen möglichen Weg, aber
nicht die Ursache — der Importpfad in `modules/radio/` ist falsch. K1 empfiehlt, den Pfad
zu korrigieren statt Shims anzulegen.

### In `esp32.bt-gateway/docs/planung/AUFTRAG-CURSOR-4.md`

**Bereits erledigt.** P-F6 verweist jetzt auf D1, P-F7 auf D3 und P-F8 auf D2, jeweils mit
dem Pfad dieses Dokuments. Nichts weiter zu tun — hier nur vermerkt, damit die Verknüpfung
bei einer späteren Umnummerierung nicht übersehen wird.

---

## 8. Entscheidungen beim Eigentümer

| # | Frage | Empfehlung |
|---|---|---|
| **E-D1** | Soll der Rückmeldekanal zum Fahrzeugdisplay jetzt gebaut werden, oder mit dem Gateway? | **Jetzt nur die Fehlermeldungen** durchschleifen — also `write_progress()`-Aufrufe mit `color="red"` oder `"orange"`. Das deckt „Gerät nicht verbunden" und „RTL-SDR belegt" ab, also die Fälle, in denen der Fahrer sonst ratlos bleibt. Fortschritt weglassen: über drei Textfelder ist er nur als Zahl darstellbar und eher Ablenkung. Die vollständige Lösung braucht den Menükanal des Gateways (P-F6). |
| **E-D2** | Wird „Frequenz manuell" dauerhaft aus dem Menü genommen, oder nur bis zur sauberen Lösung? | Vorschlag: **dauerhaft.** Eine Frequenzeingabe über drei Tasten und ohne Anzeige ist auch repariert keine gute Bedienung. Im WebUI gehört sie hin, am Lenkrad nicht. |
| **E-D3** | Sollen die beiden Scanner-Eingabeschleifen (`scanner.py:709-780`) gleich mitbehandelt werden? | Ja — es ist dasselbe Muster, und getrennte Behandlung bedeutet, `scanner.py` zweimal anzufassen. |

---

## 9. Definition of Done

- `fm_manual` erscheint nicht mehr im Menübaum, oder der modale Zustand ist in der
  Statusdatei ausgewiesen und die Navigation bleibt bedienbar.
- `fm_next` bewirkt am Pi eine sichtbare Änderung in `pidrivectl now` **ohne** zusätzlichen
  Tastendruck.
- Kein Modul außer `ipc.py` und `main_core.py` liest `ipc.CMD_FILE` direkt; durch
  `test_cmd_file_single_reader` abgesichert.
- E-D1 ist entschieden. Falls „Fehlermeldungen durchschleifen": eine provozierte
  Fehlermeldung (RTL-SDR belegt) ist am Fahrzeugdisplay lesbar.
- Alle vier Tests aus Abschnitt 5 laufen in `run_all()` mit.
- `pidrivectl test all` zeigt gegen die Baseline keine neuen Fehler.
- `VERSION` angehoben, Abnahme mit Commit-Hash in `docs/ABNAHMEN.md`.
- Abschnitt 7 an die Eigentümer der drei genannten Dokumente übergeben.

---

## 10. Historie

| Datum | Änderung |
|---|---|
| 2026-09-15 | Angelegt. Befunde D1–D3 gegen v0.11.128 (`f749a42`) belegt. Anlass: Rückmeldung des Eigentümers zum iDrive-Menü-Mockup — „bei System-Info und Version passiert nichts", anschließend dieselbe Meldung bei Radioaktionen. Die Befunde standen zwischenzeitlich als S14–S16 in `AUFTRAG-WEBUI-SANIERUNG.md` und wurden hierher ausgelagert, weil jene Datei parallel bearbeitet wird. |
