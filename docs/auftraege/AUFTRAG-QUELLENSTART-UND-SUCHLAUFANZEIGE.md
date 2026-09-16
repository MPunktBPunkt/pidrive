# Arbeitsauftrag — Quellenstart, Rasterbedienung und Suchlaufanzeige

| | |
|---|---|
| Stand | v0.11.137 / `9db988b` |
| Angelegt | 2026-09-16 |
| Anlass | Eigentümerwunsch am Menü-Mockup |
| Gilt für | `pidrive/menu/*`, `pidrive/trigger/td_nav.py`, `pidrive/trigger/td_radio.py`, `pidrive/mpris2.py`, `pidrive/modules/radio/*` |
| Abhängigkeit | **Teil B blockiert** durch M-B/M-C aus [AUFTRAG-MPRIS2-STABILITAET.md](AUFTRAG-MPRIS2-STABILITAET.md) |
| Behebt | **D3 für FM** aus [AUFTRAG-DISPLAY-RUECKMELDUNG.md](AUFTRAG-DISPLAY-RUECKMELDUNG.md) (Teil C) |

> **Dateieigentum:** dieses Dokument schreibt die Analyse-Instanz. Fortschritt bitte
> ausschließlich in §8 anhängen.

---

## 0. Was gewünscht ist

Zwei Wünsche aus der Betrachtung des iDrive-Mockups, wörtlich:

> „Können wir bei der Wahl der Quelle, wenn wir schon FM, DAB oder Webradio gewählt haben,
> direkt den letzten Sender beginnen abzuspielen? Dann würde der Menüpunkt *Nächster Sender*
> super passen."

> „Können wir beim Suchlauf über die Metadaten dem iDrive aktuelle Infos über den
> Suchbereich, Frequenz bei FM oder Kanal bei DAB anzeigen?"

Dazu am 2026-09-16 eine dritte Frage, nachdem im Mockup der Hinweis zu „Frequenz manuell"
aufgeschlagen war:

> „Müsste hier ein Unterpunkt kommen, bei dem man immer ein bestimmtes Raster springt
> (mehrere Raster zur Auswahl? oder zum nächsten Peak?)"

Daraus werden drei Teile: **A — Quellenstart**, **B — Suchlaufanzeige** und
**C — Rasterbedienung**. Teil A und C sind sofort umsetzbar. Teil B ist fachlich richtig,
aber heute nicht baubar (§1.5).

Teil C ist mehr als Bequemlichkeit: Rasterschritte brauchen keine Eingabeschleife und
**ersetzen** damit die modale Frequenzeingabe, die heute das Menü einfriert. Der
Eigentümerwunsch trifft also zufällig genau die Ursache von Befund D3.

### Festgelegter Umfang

Autoplay gilt **ausschließlich** für die drei Quellenordner:

- `root/sources/fm`
- `root/sources/dab`
- `root/sources/webradio`

**Nicht** betroffen: `root/sources` selbst, die Senderlisten darunter, Scanner, Spotify,
Bibliothek, Favoriten. Das Blättern in Senderlisten bleibt lautlos — Eigentümerentscheidung
vom 2026-09-16. Scanner ist ausdrücklich ausgenommen, weil ein Autoplay dort den RTL-SDR
belegen würde, ohne dass der Nutzer es beabsichtigt.

---

## 1. Ausgangslage

### 1.1 Die gespeicherten Sender existieren bereits  [BELEGT]

```python
# pidrive/settings.py:59-63
    "last_fm_station":    None,
    "last_dab_station":   {"name": "ROCK FM", "channel": "11B",
                           ...
    "last_web_station":   None,
```

`last_dab_station` ist vorbelegt, die beiden anderen stehen auf `None` — Teil A braucht
also einen Rückfall (§2.3).

### 1.2 Das Betreten eines Ordners hat heute keine Wirkung  [BELEGT]

```python
# pidrive/menu/menu_state.py:143-148
        if node.type == "folder" and node.children:
            self._stack.append(node)
            self._cursors.append(self._first_selectable(node.children))
            self.rev += 1
            return node
```

Reine Navigation. `MenuNode` führt zwar `action` und `source` (L19-20), aber `action` wird
bei Ordnern beim Enter nicht ausgewertet. Es braucht ein neues Feld.

### 1.3 Der Cursor sitzt schon richtig  [BELEGT]

`_first_selectable()` überspringt `Zurueck`. Nach dem Betreten von `Quellen › FM Radio`
steht der Cursor bereits auf **Naechster Sender** (Position 2/6, am Mockup bestätigt).
An dieser Stelle ist **keine Arbeit nötig** — der Wunsch „dann würde *Nächster Sender* super
passen" ist bereits erfüllt, sobald Ton läuft.

### 1.4 DAB liefert Suchlauf-Fortschritt, FM nicht  [BELEGT]

```python
# pidrive/modules/radio/dab_scan.py:214-216
    ipc.write_progress("DAB+ Suchlauf", "Regionale Kanäle...", color="blue")
    ...
        ipc.write_progress("DAB+ Suchlauf", f"Kanal {ch}...", color="blue")
```

Der Kanal steht also schon zur Verfügung — er erreicht nur den BMW nicht (Befund D1 in
[AUFTRAG-DISPLAY-RUECKMELDUNG.md](AUFTRAG-DISPLAY-RUECKMELDUNG.md)). Für **FM** gibt es
dagegen keine Fortschrittsmeldung pro Frequenz; `scanner.py` schreibt nur Endzustände
(L680, L716). Die Meldung muss dort erst erzeugt werden.

### 1.5 Teil B ist heute nicht baubar  [BELEGT]

Der Suchlauf läuft im Hintergrund-Thread. Metadaten von dort zu senden ist genau das
Muster, das den Core abstürzen lässt — siehe M1 im MPRIS2-Auftrag. Der Nachweis steht im
eigenen Testcode, und zwar im DAB-Test:

```python
# pidrive/test_suite.py:655-658
def test_dab(sender_nr=22):
    """8. DAB+."""
    _section(f"DAB+ (Sender #{sender_nr})", "📻")
    # _send_to_bmw absichtlich NICHT aufgerufen — würde MPRIS2-Push triggern → SIGABRT
```

Ein Suchlauf mit Fortschrittsanzeige würde nicht eine Anzeige liefern, sondern **bei jedem
Suchlauf einen Prozessabsturz** — häufiger als heute, weil viele Pushes statt einem.

**Konsequenz:** Teil B beginnt erst, wenn M-B und M-C abgenommen sind. Vorher nicht
anfangen. Teil A ist davon nicht betroffen, weil es einen einzelnen Quellenwechsel auslöst
und damit denselben Pfad nutzt wie jeder Sendertastendruck heute.

### 1.6 Die Ratenbegrenzung lässt sich versehentlich aushebeln  [BELEGT]

```python
# pidrive/mpris2.py:79-83
        _track_changed = (track_nr != self._last_trackid)
        # Rate-Limit: max alle 300ms — verhindert Notification-Overflow im BMW
        if not _track_changed and (_now - self._last_emit) < 0.3:
            return
```

Wechselt `track_nr`, wird ohne Begrenzung gesendet. Zählt der Suchlauf-Fortschritt die
Tracknummer mit, ist die Bremse weg: ein FM-Sweep von 87,5 bis 108 MHz in 0,1er-Schritten
sind rund 205 Benachrichtigungen im Schnelldurchlauf ans BMW. Die Tracknummer muss während
eines Suchlaufs **konstant** bleiben.

---

## 2. Entwurf Teil A — Quellenstart

### 2.1 Auslöser — der Zustand meldet, der Dispatcher handelt

Neues optionales Feld am Knoten, etwa `enter_action: Optional[str]`.

> **Korrektur vom 2026-09-16.** Eine frühere Fassung dieses Abschnitts schlug vor, die
> Aktion in `key_enter()` auszuführen. **Das ist falsch.** `MenuState.activate()` ruft
> `key_enter()` für Ordner selbst auf:
>
> ```python
> # pidrive/menu/menu_state.py:256-257
>         if node.type == "folder" and node.children:
>             self.key_enter()
> ```
>
> Ein `activate:<uid>`-Befehl aus WebUI oder AVRCP auf einen Quellenordner würde die
> Wiedergabe damit ungewollt mit auslösen — und `goto:` ebenso, sobald jemand die
> Pfadauflösung auf `key_enter()` umstellt.

Richtig ist die Trennung: `key_enter()` liefert den betretenen Knoten zurück (das tut es
heute schon, L148). Der **Dispatcher** prüft `node.enter_action` und führt sie über `bg()`
aus. Der Menüzustand führt nichts aus und bleibt nebenwirkungsfrei — damit sind `walk`,
`goto` und `activate` von sich aus unbedenklich, ohne Sonderfälle.

Gesetzt wird das Feld ausschließlich an den drei Ordnern aus §0 — in `menu_builder.py`,
nicht über eine Namensheuristik im Menüzustand. Der Menüzustand darf nicht wissen, was FM
ist.

### 2.2 Nur starten, wenn die Quelle nicht schon läuft

**Das ist die wichtigste Regel des ganzen Pakets.** Läuft FM bereits auf 104.4 und der
Nutzer betritt das FM-Menü, um „Nächster Sender" zu drücken, dürfte das Betreten ihn
nicht zuerst auf den gespeicherten Sender zurückwerfen. Das wäre schlechter als der Zustand
heute.

Bedingung also: `source_state.get_current() != <quelle des ordners>`. Bei Gleichheit
passiert nichts — kein Neustart, kein Commit, kein Push.

### 2.3 Rückfall bei leeren Feldern

| Quelle | Erste Wahl | Rückfall |
|--------|-----------|----------|
| FM | `last_fm_station` | Einstellung `fm_freq` (Vorbelegung `"98.5"`, `settings.py:33`) |
| DAB | `last_dab_station` | vorbelegt mit `ROCK FM / 11B` — kein Rückfall nötig |
| Webradio | `last_web_station` | erster Sender der Senderliste |

Ist auch der Rückfall leer (z. B. leere Webradio-Liste), wird **nicht** gestartet und der
Ordner nur betreten. Kein Fehlerdialog.

### 2.4 Über den normalen Quellenwechsel gehen, nicht daneben

Die Enter-Aktion muss denselben Weg nehmen wie ein Sendertastendruck: andere Quellen
stoppen, `begin_transition()`, starten, **Ergebnis prüfen**, dann `commit_source()`.

Ausdrücklich **nicht** das Muster aus `td_scanner.py` übernehmen, das
`commit_source()` unbedingt ausführt — das ist Befund N3 und erzeugt einen Spiegel, der
eine Quelle ohne Gerät meldet. Solange N-C offen ist, darf hier kein zweiter Ort mit
demselben Fehler entstehen.

### 2.5 Ergonomischer Gewinn

Am Mockup gemessen: bis ROCK FM sind es heute achtzehn Tastendrücke. Mit Teil A sind es
**vier bis zum Ton** — runter, Enter (Quellen), runter, Enter (FM Radio) — und der Cursor
steht danach direkt auf „Naechster Sender". Das entlastet genau den Fall, der laut
`docs/menue/MENU-ERGONOMIE.md` am schlechtesten dasteht: der Median von 15 Tastendrücken
betrifft überwiegend Senderwahl.

### 2.6 Nebenwirkung, die leicht übersehen wird

`pidrivectl menu walk` läuft seit `9db988b` in `test all` (`test_suite.py:979`) und geht
jeden Knoten durch. Entscheidend ist dabei, dass er **keine Aktionen ausführt**:

```python
# pidrive/menu/menu_golden.py:441-447
    state = MenuState(root)
    for n in nodes:
        if n["type"] not in ("station", "action", "toggle"):
            continue
        leaves += 1
        got = state.activate(n["uid"])
```

`MenuState.activate()` findet den Knoten und setzt den Cursor — nichts weiter. Ordner
überspringt die Schleife ohnehin. Mit der Trennung aus §2.1 ist der Walk also von sich aus
sicher, und es braucht **keine** Sonderbehandlung. Paket Q-D reduziert sich damit auf eine
Absicherung: ein Test soll festhalten, dass der Walk keinen Tuner startet, damit die
Eigenschaft nicht später unbemerkt verloren geht.

---

## 2b. Entwurf Teil C — Rasterbedienung statt modaler Eingabe

### 2b.1 Was heute passiert  [BELEGT]

```python
# pidrive/modules/radio/fm.py:360-372
def freq_input_screen(screen=None):
    """Headless Frequenz-Eingabe via File-Trigger. Gibt Frequenz-String zurück."""
    freq = 87.5
    deadline = time.time() + 60
    while time.time() < deadline:
        ipc.write_progress(
            "FM Frequenz",
            f"{freq:.1f} MHz  (↑↓ 0.1  ←→ 1.0  Enter=OK  Back=Abbruch)",
            color="blue"
        )
        if not os.path.exists(ipc.CMD_FILE):
            time.sleep(0.15)
            continue
```

Aufgerufen aus `td_nav.py:247`. Die Schleife liest `ipc.CMD_FILE` direkt und löscht sie mit
`os.remove()` — sie umgeht `drain_triggers()` und meldet sich nicht über `LIST_FILE` an.
Bis zu sechzig Sekunden konkurrieren zwei Leser um dieselbe Datei; wer einen Tastendruck
bekommt, ist Zufall. Der eingestellte Wert steht ausschließlich im Overlay und erreicht den
BMW nie. Das ist Befund **D3**.

### 2b.2 Warum Rasterschritte das auflösen

Ein Rasterschritt ist eine gewöhnliche Menüaktion: ein Befehl, einmal vom Dispatcher
abgearbeitet, fertig. Keine Schleife, kein zweiter Leser, kein Einfrieren. Die modale
Eingabe wird dadurch nicht ergänzt, sondern **ersetzt** — `Frequenz manuell` entfällt
samt `fm.freq_input_screen()` und dem Aufruf in `td_nav.py:247`.

Zweite Eigenschaft, die das auf dem iDrive erst benutzbar macht: `MenuState.activate()`
setzt den Cursor auf den ausgeführten Knoten. Bleibt er dort stehen, ist **jeder weitere
Enter ein weiterer Schritt**. Einmal hinnavigieren, dann nur noch drücken.

### 2b.3 Die Einträge

Kein Untermenü zur Rasterwahl — das kostet eine Ebene für wenig Gewinn. Vier feste
Einträge unter `Quellen › FM Radio`, an der Stelle, an der heute `Frequenz manuell` steht:

| Eintrag | Schritt | Zweck |
|---|---|---|
| `+ 0.1 MHz` | europäisches 100-kHz-Raster | der Normalfall |
| `− 0.1 MHz` | dito | |
| `+ 1.0 MHz` | grob | entspricht ←→ der alten Schleife |
| `− 1.0 MHz` | dito | |

Grenzen wie in der alten Schleife: 87.5 bis 108.0, Rundung auf eine Dezimale. Am Rand nicht
umlaufen, sondern stehen bleiben — ein stiller Sprung von 108.0 auf 87.5 wäre im Fahrbetrieb
irritierend.

### 2b.4 Ausdrücklich nicht in diesem Paket

**Die zwei modalen Schleifen im Scanner bleiben.** `scanner.py:724` (`_freq_input`) und
`scanner.py:761` (`freq_input_screen`), aufgerufen aus `td_scanner.py:232`, haben dasselbe
Muster und denselben Defekt. Eigentümerentscheidung vom 2026-09-16: dieses Paket behebt D3
**nur für FM**. D3 bleibt für den Scanner offen und ist dort weiter zu führen.

**Kein Peak-Sprung.** Erwogen und verworfen: `Naechster Sender` springt bereits zum nächsten
*bekannten* Sender aus der Scanliste. Echten Mehrwert hätte ein Peak-Sprung nur für Signale,
die nicht in der Liste stehen — über `candidates` aus `spectrum.py: sweep_fm_band`. Das
setzt einen vorherigen Sweep und einen freien Stick voraus und müsste ohne Ergebnis sauber
degradieren, sonst meldet der Lint einen toten Knoten. Nicht in diesem Umfang.

**Keine DAB-Kanalschritte.** DAB hat kein Raster, sondern benannte Kanäle (5A bis 13F). Ein
`Nächster Kanal` wäre denkbar, kostet aber je Wechsel Sekunden zum Einrasten. Nicht in
diesem Umfang.

### 2b.5 Anzeige nach dem Schritt

Ein Rasterschritt stimmt real ab, also entsteht echter Wiedergabezustand — anders als beim
Overlay erreicht die neue Frequenz den BMW über den normalen Metadatenpfad. **Aber:** der
Push erfolgt heute, bevor die Abstimmung im Hintergrund fertig ist, weshalb die Anzeige
zunächst die alte Frequenz zeigt. Das ist Befund **D2**. Teil C soll nach abgeschlossener
Abstimmung ein zweites Mal senden; ohne das wirkt jeder Schritt verzögert.

---

## 2c. Entwurf Teil D — Menüvorrang mit Zeitablauf

### 2c.1 Der Wunsch

Eigentümerwunsch vom 2026-09-16, aus dem Vergleich mit der Bedienung von Radio und MP3 im
eigenen Fahrzeug:

> „Wenn ich das Rad nicht drehe, kommt nach einigen Sekunden (3–4) die Metadaten, wenn ich
> am Rad drehe, erscheint das Menü, durch das ich navigieren kann."

### 2c.2 Was heute im Weg steht  [BELEGT]

```python
# pidrive/mpris2.py:504-518
    else:
        path     = menu.get("path", [])
        ...
        album   = "PiDrive Menü"
        playing = False
```

Der Menü-Zweig ist das `else` der Verzweigungskette nach Spotify, Radio und Bibliothek. Er
wird also **nur** erreicht, wenn keine Quelle läuft. Sobald etwas spielt, ist die
Menünavigation ohne jede Anzeige — Befund „Blindnavigation".

### 2c.3 Was erreichbar ist, und was nicht

Innerhalb von drei Textfeldern entsteht **keine Liste**. „Das Menü erscheint" heißt hier:
der markierte Eintrag als Titel, der Pfad darunter. Das ist eine Zeile statt Blindflug —
deutlich besser als heute, aber nicht das, was Radio und MP3 zeigen, weil das Steuergerät
dort seine **eigenen** Daten rendert.

Die echte Liste käme nur über einen AVRCP-Browsing-Kanal. Ob der BMW ihn öffnet, klärt
`tools/bmw_avrcp_probe.sh`. Teil D ist unabhängig davon und lohnt sich auch dann, weil er
die Blindnavigation beendet, ohne auf eine Messung zu warten.

### 2c.4 Die Belegung während der Wiedergabe

Solange Musik läuft, ist die dritte Zeile frei — heute steht dort konstant „PiDrive Menü".
Besser ist der laufende Sender, damit beim Navigieren der Bezug nicht verloren geht:

| Zeile | Navigieren, nichts spielt (heute) | Navigieren **während** Wiedergabe (neu) |
|---|---|---|
| `xesam:title` | markierter Eintrag | markierter Eintrag |
| `xesam:artist` | Pfad | Pfad |
| `xesam:album` | `PiDrive Menü` | **laufender Sender**, z. B. `ROCK FM` |

### 2c.5 Die Entscheidung gehört in die Core-Schleife

`mpris2.py` soll Darsteller bleiben und nicht über Zeitfenster urteilen — dieselbe Trennung
wie in §2.1. Also: `update(status, menu, view="auto")` mit zwei Werten.

| `view` | Verhalten |
|--------|-----------|
| `"auto"` | heutige Verzweigungskette, Menü als `else` — unverändert |
| `"menu"` | Menü-Zweig rendern, **Wiedergabezustand aus der echten Lage** übernehmen |

Die Zeitsteuerung liegt in der 2-Hz-Schleife von `main_core.py`, die den Status ohnehin
schreibt (L706-710):

```text
bei Änderung von menu_state.rev:
    menue_bis = jetzt + zeitfenster
    push(view="menu")

sonst wenn menue_bis gesetzt und jetzt >= menue_bis:
    menue_bis = None
    push(view="auto")
```

### 2c.6 Fünf Fallen

**Der Wiedergabezustand muss `True` bleiben.** Der heutige Menü-Zweig setzt
`playing = False` (L518). Wer ihn unbesehen wiederverwendet, während Audio läuft, meldet
dem BMW „gestoppt" — und ein Autoradio darf daraufhin den Stream pausieren oder die
Wiedergabetasten sperren. `playing = False` gilt nur, wenn wirklich nichts spielt.

**Aktivieren ist keine Navigation.** Wird ein Sender ausgewählt, steigt `menu_state.rev`
ebenfalls — das Menü bliebe dann drei bis vier Sekunden stehen und würde genau den Sender
verdecken, den man gerade gewählt hat. Bei Aktivierung eines Blattes muss das Zeitfenster
also **sofort beendet** werden, nicht neu gestartet.

**Die Tracknummer muss konstant bleiben.** Sonst greift die Ratenbegrenzung aus §1.6 nicht,
und schnelles Drehen am Rad erzeugt eine Benachrichtigungsflut im BMW.

**Im Leerlauf darf sich nichts ändern.** Spielt nichts, rendern `"auto"` und `"menu"`
dasselbe. Teil D ist damit eine reine Ergänzung für den Wiedergabefall — im Leerlauf
besteht kein Regressionsrisiko.

**P-F1 bleibt offen.** Der Zeitablauf bringt zwar einen zweiten Anstoß in die Schleife, aber
Titelwechsel einer laufenden Quelle lösen weiterhin keinen Push aus. Teil D behebt das nicht.

### 2c.7 Verhältnis zum MPRIS2-Absturz

`mpris2.update()` wird schon heute aus der Core-Schleife gerufen, also aus einem anderen
Thread als die GLib-Schleife — das ist der Pfad aus M1. Teil D fügt **keinen neuen**
Zugriffspfad hinzu und erhöht die Häufigkeit nur gering: pro Navigationsfolge kommt *ein*
Push für den Rückfall hinzu, nicht einer pro Tastendruck.

Trotzdem gilt: **M-A zuerst messen.** Stürzt der Core während der Navigation ab, sieht das
Ergebnis von Teil D wie ein Fehler in Teil D aus, obwohl die Ursache älter ist.

---

## 3. Entwurf Teil B — Suchlaufanzeige

Erst nach M-B/M-C beginnen.

### 3.1 Belegung der drei Zeilen

| Feld | FM-Suchlauf | DAB-Suchlauf |
|---|---|---|
| `xesam:title` | `Suchlauf 98.5 MHz` | `Suchlauf Kanal 11B` |
| `xesam:artist` | `87.5 – 108.0 MHz · 54 %` | `Regionale Kanäle · 7/12` |
| `xesam:album` | `3 Sender gefunden` | `2 Ensembles gefunden` |

Der Suchbereich gehört in die Artist-Zeile, weil er sich selten ändert und dort im
BMW-Layout ruhig steht; die wechselnde Frequenz in die Titelzeile.

### 3.2 Sendetakt

Höchstens **ein Push pro Sekunde**, und `track_nr` bleibt konstant (§1.6). Zusätzlich nur
bei sinnvollen Ereignissen senden: bei jedem gefundenen Sender, bei DAB je Kanal, bei FM
höchstens je 1 MHz — nicht je 0,1 MHz.

### 3.3 Abschluss

Nach dem Suchlauf muss **noch einmal** gesendet werden, sonst bleibt die letzte
Fortschrittszeile stehen. Das ist Befund D2: die Radiomodule heben `menu_state.rev` nach
Abschluss der Hintergrundarbeit nicht erneut an, weshalb das Display bis zum nächsten
fremden Ereignis veraltet bleibt.

### 3.4 Kein Ersatz für D1

Teil B löst die Anzeige **für den Suchlauf**, nicht allgemein. Der Überlagerungskanal
`ipc.write_progress()` erreicht den BMW weiterhin nicht — Aktionen wie „System-Info" und
„Version" bleiben stumm. D1 bleibt offen und ist separat zu entscheiden.

---

## 4. Arbeitspakete

| ID | Paket | DoD |
|----|-------|-----|
### Teil A — Quellenstart

| ID | Paket | DoD |
|----|-------|-----|
| **Q-A** | Feld `enter_action` in `MenuNode`, Export in `to_dict()`. Auswertung **im Dispatcher** nach §2.1, nicht in `key_enter()`. Ausführung über `bg()`. | Ein Ordner mit `enter_action` löst beim Betreten genau einmal aus. `activate:<uid>` auf denselben Ordner löst **nicht** aus. |
| **Q-B** | `enter_action` an den drei Quellenordnern in `menu_builder.py` setzen. Nirgends sonst. | `pidrivectl menu tree` zeigt das Feld an genau drei Knoten. |
| **Q-C** | Startlogik mit Vorbedingung aus §2.2, Rückfällen aus §2.3 und dem Quellenwechsel aus §2.4. Ergebnisprüfung vor `commit_source()`. | FM läuft auf 104.4 → FM-Menü betreten ändert **nichts**. Idle → FM-Menü betreten spielt den letzten Sender. Spiegel und Gerät stimmen danach überein. |
| **Q-D** | Absicherung statt Sonderfall (§2.6): Test, der festhält, dass `menu walk` keinen Tuner startet. | `pidrivectl menu walk` läuft durch, `pgrep -a rtl_fm` bleibt leer. |
| **Q-E** | Golden Master und Verträge nachziehen: neues Feld im Export heißt geänderter Vergleichsstand. `test_menu_contracts.py` um eine Prüfung ergänzen, dass genau die drei Ordner eine Enter-Aktion tragen. | Offline-CI grün, `menu verify` ohne Verluste, `tests/golden/CHANGES.md` mit **einem** Eintrag. |

### Teil C — Rasterbedienung (behebt D3 für FM)

| ID | Paket | DoD |
|----|-------|-----|
| **Q-G** | **Zuerst der Test, dann der Fix.** iDrive-Skript `tests/idrive/fm-manual-freeze.txt` nach §5b anlegen. Es muss am heutigen Stand **fehlschlagen**. | Skript läuft gegen v0.11.137 rot — der Einfrier-Befund ist erstmals automatisiert belegt. |
| **Q-H** | Vier Rastereinträge nach §2b.3 als gewöhnliche Actions in `menu_builder.py`, Abstimmung im bestehenden FM-Pfad. Grenzen 87.5–108.0, kein Umlauf. | Jeder Enter stimmt einen Schritt weiter; wiederholter Enter ohne Neunavigation funktioniert. |
| **Q-I** | `Frequenz manuell` entfernen: Menüknoten, `fm.freq_input_screen()` (`fm.py:360-389`) und der Aufruf in `td_nav.py:247`. | `grep -rn freq_input_screen pidrive/modules/radio/fm.py pidrive/trigger/td_nav.py` ist leer. Skript aus Q-G wird **grün**. |
| **Q-J** | Zweiten Push nach abgeschlossener Abstimmung (§2b.5, Befund D2), damit die Anzeige nicht eine Frequenz nachläuft. | Am Fahrzeug zeigt der BMW nach jedem Schritt die **neue** Frequenz, nicht die vorherige. |

### Teil D — Menüvorrang (beendet die Blindnavigation)

| ID | Paket | DoD |
|----|-------|-----|
| **Q-K** | `mpris2.update(status, menu, view="auto")` nach §2c.5. Im Zweig `"menu"` den Wiedergabezustand aus der echten Lage übernehmen statt `playing = False`, und `xesam:album` mit dem laufenden Sender belegen (§2c.4). | Aufruf mit `view="menu"` bei laufender Wiedergabe liefert Menütext **und** `PlaybackStatus = Playing`. Aufruf mit `"auto"` verhält sich wie heute. |
| **Q-L** | Zeitsteuerung in der 2-Hz-Schleife von `main_core.py`: Zeitfenster bei Navigation setzen, bei Ablauf einmal auf `"auto"` zurückfallen, bei **Aktivierung eines Blattes sofort beenden** (§2c.6). Fenster als Einstellung, Vorbelegung 3.5 s. | Als reine Funktion prüfbar: Eingabe (rev-Änderung, Art der Änderung, Zeit) → Ausgabe (`view`). Unit-Test in `tests/unit/`, offline lauffähig. |
| **Q-M** | Tracknummer während Menüansicht konstant halten, damit die 300-ms-Begrenzung greift (§1.6). | Zwanzig Tastendrücke in zwei Sekunden erzeugen höchstens sieben `PropertiesChanged`. |
| **Q-N** | Zeitfenster am Fahrzeug gegen das Eigenmaß des BMW kalibrieren (Messung HQ12), Vorbelegung danach festlegen. | Wert in `docs/ABNAHMEN.md` begründet; Umschalten fühlt sich nicht fremd an. |

### Teil B — Suchlaufanzeige

| ID | Paket | DoD |
|----|-------|-----|
| **Q-F** | *(gesperrt bis M-B/M-C)* Suchlaufanzeige nach §3: Fortschritt aus `dab_scan.py` verdrahten, für FM neu erzeugen, Takt nach §3.2, Abschlusspush nach §3.3. | Suchlauf am Fahrzeug sichtbar, kein Core-Neustart während des Laufs, keine Benachrichtigungsflut im BMW. |

### Was nicht zu tun ist

Autoplay über eine Namensheuristik im Menüzustand erkennen. Der Zustand darf keine
Quellenkenntnis haben, sonst wandert Fachlogik an eine Stelle, an der sie später niemand
sucht.

Teil B vor M-B/M-C beginnen. Das erzeugt reproduzierbare Abstürze und verbrennt die
Messgrundlage für M-A.

Den Scanner in den Autoplay-Umfang aufnehmen. Er würde den RTL-SDR unaufgefordert belegen.

---

## 5. Tests am Fahrzeug

| ID | Ablauf | Erwartung |
|----|--------|-----------|
| **HQ1** | Aus `idle`: Quellen → FM Radio betreten | Letzter FM-Sender spielt, Cursor auf „Naechster Sender", vier Tastendrücke bis Ton |
| **HQ2** | Während FM auf 104.4 läuft: FM-Menü betreten | **Kein** Senderwechsel, kein Aussetzer |
| **HQ3** | Aus `idle`: Quellen → DAB+ betreten | `ROCK FM / 11B` spielt (Vorbelegung), Einrasten dauert erkennbar — bis Q-F ohne Anzeige |
| **HQ4** | Quellen → Webradio betreten bei leerer `last_web_station` | Erster Sender der Liste spielt |
| **HQ5** | `pidrivectl menu walk` | Kein Tuner gestartet, `pgrep -a rtl_fm` leer |
| **HQ6** | Senderliste betreten und blättern | Lautlos, kein Quellenwechsel |
| **HQ7** | *(nach Q-F)* DAB-Suchlauf am BMW beobachten | Kanal und Zähler wechseln sichtbar, höchstens ein Wechsel je Sekunde, am Ende steht das Ergebnis |
| **HQ8** | *(Teil C)* FM läuft, `+ 0.1 MHz` anwählen, dann fünfmal Enter ohne Neunavigation | Fünf Schritte, Anzeige folgt jeweils der **neuen** Frequenz |
| **HQ9** | *(Teil C)* Bei 108.0 nochmals `+ 1.0 MHz` | Bleibt auf 108.0 stehen, kein Umlauf, keine Fehlermeldung |
| **HQ10** | *(Teil D)* Bei laufender Wiedergabe navigieren, dabei MPRIS2 auslesen: `dbus-send --system --print-reply --dest=org.mpris.MediaPlayer2.pidrive /org/mpris/MediaPlayer2 org.freedesktop.DBus.Properties.GetAll string:org.mpris.MediaPlayer2.Player` | `xesam:title` zeigt den markierten Eintrag, `xesam:album` den laufenden Sender, `PlaybackStatus` bleibt `Playing` |
| **HQ11** | *(Teil D)* Nach HQ10 fünf Sekunden nichts drücken, erneut auslesen | Anzeige ist von selbst auf den laufenden Sender zurückgefallen |
| **HQ12** | *(Teil D, Kalibrierung)* Am BMW mit **eigener** Quelle (Radio oder USB) das Rad drehen und mit der Stoppuhr messen, nach wie vielen Sekunden die Metadaten zurückkommen | Zeitmaß des Fahrzeugs bekannt; Vorbelegung für Q-N daran ausrichten |
| **HQ13** | *(Teil D)* Während Wiedergabe einen Sender **aktivieren** | Der gewählte Sender erscheint **sofort**, das Menü verdeckt ihn nicht für Sekunden (§2c.6) |

---

## 5b. Der Test, der das Einfrieren findet

Bisher fängt **kein** Test den Befund D3 — und das hat einen nachvollziehbaren Grund:

| Prüfung | Warum sie es nicht sieht |
|---------|--------------------------|
| `menu lint` | Der Knoten hat eine nicht-leere Action → zufrieden |
| `menu walk` | `MenuState.activate()` **führt keine Action aus** (§2.6), prüft nur Adressierbarkeit |
| `tests/idrive/rockfm.txt` | Navigiert zu ROCK FM, berührt `Frequenz manuell` nie |
| FM-Abschnitt in `test all` | Prüft Wiedergabe, nicht Menüaktionen |

Der tiefere Grund: das Einfrieren ist **keine Eigenschaft eines Knotens**, sondern eine
Wechselwirkung zwischen zwei Lesern derselben Datei. Sie tritt nur auf, wenn ein *zweiter*
Befehl eintrifft, während die Schleife läuft. Kein statischer Test stellt diese Situation
her — es braucht einen Verhaltenstest.

Das Werkzeug dafür existiert: die iDrive-Skripte kennen `expect`. Neues Skript
`tests/idrive/fm-manual-freeze.txt` im Format von `rockfm.txt`:

```text
# D3: modale Frequenzeingabe darf keine Tastendrücke schlucken
reset
# zu Quellen › FM Radio navigieren
next
play
sleep 1.3s
expect path_contains=Quellen
next
play
sleep 1.3s
expect path_contains=FM
# auf 'Frequenz manuell' (letzter Eintrag) und auslösen
next
next
next
next
play
sleep 0.5s
# jetzt läuft die modale Schleife — dieser Tastendruck muss ankommen
next
expect selected=Zurueck
```

Die letzte Zeile ist der Kern. Kommt der Tastendruck bei der Hauptschleife an, bewegt sich
der Cursor und das `expect` greift. Klaut die modale Schleife ihn, bleibt die Auswahl
stehen und der Test schlägt fehl.

**Wichtig für Q-G:** dieses Skript muss am heutigen Stand **rot** sein. Ein Test, der den
bekannten Fehler nicht findet, prüft nichts. Erst nach Q-I darf es grün werden — der
Zielwert der Auswahl ist dann an die neue Menüstruktur anzupassen.

---

## 6. Reihenfolge

```text
M-A                                            (MPRIS2: messen, ob der Core abstürzt — Voraussetzung, nicht Sperre)
  ↓
HQ12                                           (Zeitmaß des BMW ablesen — braucht nur eine Stoppuhr)
  ↓
Q-K → Q-L → Q-M → Q-N  +  HQ10…HQ13            (Teil D: Blindnavigation beenden)
  ↓
Q-G                                            (Test zuerst — muss rot sein)
  ↓
Q-H → Q-I → Q-J  +  HQ8, HQ9                   (Teil C: Raster ersetzt modale Eingabe, D3/FM erledigt)
  ↓
Q-A → Q-B → Q-C → Q-D → Q-E  +  HQ1…HQ6        (Teil A: Quellenstart)
  ↓
[Sperre: M-B, M-C aus dem MPRIS2-Auftrag]
  ↓
Q-F  +  HQ7                                    (Teil B: Suchlaufanzeige)
```

**Teil D steht vorn**, weil er die Voraussetzung für den Nutzen der übrigen Teile ist. Teil A
bringt die Blindheit nach vorn — mit Autoplay spielt nach vier Tastendrücken Musik, und
alles danach wäre unsichtbar. Teil C wäre ohne D nur halb bedienbar, weil man die
Rasterschritte blind drückte. Wer D zuletzt baut, baut A und C zweimal ab.

Teil C steht vor Teil A, weil es einen **bestehenden** Fehler behebt, während Teil A eine
neue Eigenschaft hinzufügt. Außerdem ändern beide dieselbe Menüebene
(`Quellen › FM Radio`) — zwei Golden-Master-Umstellungen hintereinander sind billiger als
eine verschränkte.

M-A ist als Voraussetzung geführt, nicht als Sperre: Teil D fügt keinen neuen
Zugriffspfad auf D-Bus hinzu (§2c.7), aber ein Absturz während der Navigation würde als
Fehler in Teil D erscheinen. Die Messung kostet zwei Kommandos.

Teil A kann parallel zu den WLAN- und Scanner-Paketen laufen; es berührt andere Dateien.
Eine Ausnahme: Q-C fasst den Quellenwechsel an, und N-C aus
[AUFTRAG-SPOTIFY-UND-TESTKETTE.md](AUFTRAG-SPOTIFY-UND-TESTKETTE.md) §12.9 räumt genau dort
das fehlerhafte Commit-Muster auf. Wer beides anfasst, sollte **N-C zuerst** machen und
Q-C darauf aufsetzen — sonst entstehen zwei Stellen mit derselben Schwäche.

---

## 7. Offene Eigentümerfragen

| ID | Frage | Empfehlung |
|----|-------|------------|
| **EQ1** | Soll Autoplay abschaltbar sein? | Zunächst nicht. Erst im Betrieb beurteilen, ob es störend wirkt; eine Einstellung nachzurüsten ist billig, ein unnötiger Schalter bleibt für immer. |
| **EQ2** | Soll das Verlassen des Quellenordners („Zurueck") die Wiedergabe beenden? | Nein. Navigation soll Audio nicht abwürgen — sonst wäre Blättern im Menü während der Fahrt riskant. |
| **EQ3** | Soll `last_*_station` auch bei kurzem Anspielen gespeichert werden, oder erst nach einigen Sekunden? | Erst nach etwa zehn Sekunden Wiedergabe. Sonst überschreibt ein Durchblättern mit Autoplay den gemerkten Sender mit einem, den man nie hören wollte. |
| **EQ4** | Länge des Menü-Zeitfensters in Teil D? | Eigentümerwunsch sind 3–4 s. Vorbelegung 3.5 s, danach an HQ12 ausrichten — fühlt sich das Umschalten wie beim eingebauten Radio an, ist es richtig. Als Einstellung führen, damit es ohne neue Auslieferung anpassbar bleibt. |
| **EQ5** | Soll das Zeitfenster auch dann laufen, wenn über WebUI navigiert wird (`goto:`/`activate:`)? | Ja, ohne Sonderfall — beides hebt `menu_state.rev`, und ein Fahrer, der am Telefon navigiert, sieht die Wirkung dann auch am BMW. |

---

## 8. Fortschritt

| Datum | Stand |
|-------|--------|
| 2026-09-16 | Angelegt nach Eigentümerwunsch am Mockup. Umfang auf die drei Quellenordner festgelegt, Senderlisten bleiben lautlos. Teil B als gesperrt geführt, weil §1.5 einen Absturz belegt. §1.3 hält fest, dass der Cursor bereits richtig sitzt — dort ist keine Arbeit nötig. |
| 2026-09-16 | **Teil C ergänzt** (Rasterbedienung statt modaler Eingabe, Pakete Q-G…Q-J). Behebt D3 für FM; Scanner bleibt per Eigentümerentscheidung offen. Peak-Sprung und DAB-Kanalschritte erwogen und mit Begründung verworfen (§2b.4). Neu: §5b erklärt, **warum** bisher kein Test D3 fand, und liefert das Skript, das ihn findet. |
| 2026-09-16 | **Q-A korrigiert:** Enter-Aktion gehört in den Dispatcher, nicht in `key_enter()` — `MenuState.activate()` ruft `key_enter()` für Ordner selbst auf (`menu_state.py:256-257`), ein `activate:`-Befehl hätte sonst die Wiedergabe mit ausgelöst. Q-D dadurch von „Sonderfall im Walk" auf „Absicherung durch Test" reduziert. |
| 2026-09-16 | **Teil D ergänzt** (Menüvorrang mit Zeitablauf, Pakete Q-K…Q-N) nach Eigentümerwunsch: Rad drehen zeigt das Menü, 3–4 s Ruhe zeigt die Metadaten. Beendet die Blindnavigation und steht deshalb **vor** A, C und B — ohne D wären Autoplay und Rasterschritte blind zu bedienen. Fünf Fallen in §2c.6 dokumentiert, darunter `playing = False` (Autoradio darf sonst den Stream pausieren) und „Aktivieren ist keine Navigation" (der gewählte Sender darf nicht 3.5 s verdeckt werden). Erwartung ausdrücklich begrenzt: es entsteht **keine Liste**, nur der markierte Eintrag als Text (§2c.3). |
| 2026-09-16 | Frühere Ablehnung des Menüvorrangs zurückgenommen. Begründung der Ablehnung war, er arbeite gegen die Umschaltlogik des Steuergeräts — das gilt nur, wenn der BMW für Bluetooth eine eigene Listenansicht hat. Bei Radio und USB rendert er **eigene** Daten; für Bluetooth zeigt er ausschließlich, was AVRCP liefert. Damit liegt die Umschaltung vollständig bei PiDrive. |
