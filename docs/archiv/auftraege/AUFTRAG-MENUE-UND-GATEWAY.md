# Auftrag: Menü-Reifung & Gateway-Vorbereitung

**Adressat:** zweite Cursor-Instanz, die im Repo `pidrive` arbeitet
**Stand der Analyse:** `pidrive` v0.11.127 · `esp32.bt-gateway` Planung V1.1
**Erstellt:** 2026-09-15
**Bezug:** [`esp32.bt-gateway/docs/planung/AUFTRAG-CURSOR-2.md`](https://github.com/MPunktBPunkt/esp32.bt-gateway) (Gegenstück im Gateway-Repo)

---

## 0. Wie dieses Dokument zu lesen ist

Dies ist ein **Arbeitsauftrag mit Abnahmekriterien**, kein Ideenpapier. Jedes Arbeitspaket
hat: Ziel → betroffene Dateien → Vorgehen → Abnahmekriterium (per CLI prüfbar).

**Drei Regeln, die über allem stehen:**

1. **Kein Funktionsverlust.** In der Vergangenheit sind bei Optimierungen wiederholt
   Funktionen verschwunden. Deshalb gilt ab jetzt: Erst das Sicherheitsnetz (Kapitel 2),
   dann der Umbau. Wer ohne grünes Netz refactored, arbeitet gegen den Auftrag.
2. **Alles muss über die Kommandozeile prüfbar sein.** `pidrivectl` ist das
   Debugging-Werkzeug im Fahrzeug (SSH vom Handy, kein Browser, kein Display). Jede neue
   Funktion braucht einen CLI-Einstieg **und** eine CLI-Prüfung.
3. **Menü = Daten + kopflose API.** Jede Oberfläche (BMW-3-Zeilen, späteres BMW-Listen-Menü,
   WebUI, CLI) ist nur ein *Renderer* über denselben Baum und dieselbe Navigations-API.
   Keine Oberfläche darf eigene Menülogik haben.

---

## 1. Kontext: warum wir das Menü jetzt anfassen

### 1.1 Das Fernziel

Es entsteht ein zweites Projekt, `esp32.bt-gateway`: ein dedizierter ESP32 übernimmt die
Bluetooth-Classic-Rolle gegenüber dem BMW (A2DP Source + AVRCP Target), PiDrive liefert nur
noch PCM, Metadaten und Steuerung über WLAN. Daraus folgen zwei Dinge für PiDrive:

- **Der Pi wird Audio-Senke für Fremdgeräte.** Handy und Tablet sollen sich künftig mit dem
  Pi koppeln (A2DP **Sink**), weil der BT-Dongle frei wird, sobald das BMW am ESP hängt.
  Der ESP kann das nicht übernehmen: A2DP Sink und Source gleichzeitig ist auf dem ESP32
  mit Bluedroid ausdrücklich nicht möglich (Espressif-Doku, beide A2DP-Beispiele).
- **Das Menü könnte ein echtes Menü werden.** AVRCP ab 1.4 hat einen Browsing-Kanal, über
  den ein Player eine **Ordner-/Titelliste** ans Headunit liefert; das iDrive rendert die
  Liste dann selbst und macht sie mit dem Dreh-Drück-Regler bedienbar. Das ist die
  bevorzugte Ziellösung.

### 1.2 Warum das heute nicht geht — und was daran PiDrives Aufgabe ist

BlueZ kann auf der **Target**-Seite Browsing nur zur Hälfte: Es bewirbt den Browsing-Kanal
im SDP-Record und beantwortet `GetFolderItems` **ausschließlich für Scope 0x00
(Media Player List)**. Die Scopes `0x01` (Virtual Filesystem), `0x02` (Search) und `0x03`
(Now Playing) werden mit `AVRCP_STATUS_INVALID_SCOPE` abgelehnt; `SetBrowsedPlayer`,
`ChangePath`, `GetItemAttributes` und `PlayItem` sind auf der Target-Seite gar nicht
implementiert. (Quelle: `bluez/profiles/audio/avrcp.c`, Handler-Tabelle `browsing_handlers`.)

Ein echtes Listen-Menü im BMW braucht also später einen eigenen AVRCP-Target-Stack auf dem
ESP32 — das ist Sache des anderen Repos. **PiDrives Aufgabe ist die Vorarbeit**, und die
ist wertvoll, egal wie die Browsing-Messung ausgeht:

> Der Menübaum muss zu einer **UID-adressierbaren Datenstruktur mit kopfloser
> Navigations- und Aktivierungs-API** werden. Genau das braucht der Browsing-Kanal
> (`GetFolderItems`, `ChangePath`, `PlayItem` arbeiten auf UIDs) — und genau das fehlt
> PiDrive heute auch für WebUI, CLI und Tests.

### 1.3 Die offene Kernfrage: Ist das Menü überhaupt ausgereift?

Der Eigentümer hat das PiDrive-Menü **noch nie am BMW gesehen**. Das ist kein Zufall: Bis
v0.11.122 brach `mpris2.update_metadata()` mit `TypeError` ab und `main_core` verschluckte
das in `try/except: pass` — die Anzeige kam nie zustande. Der Fix ist seit v0.11.123 drin,
aber im Fahrzeug unbestätigt (`KontextPiDrive.md`, Funktionsstatus: 🟡).

Das heißt: Das Menü ist **nie unter realen Bedingungen bedient worden**. Alles, was darüber
im Code steht, ist Theorie. Die Analyse in Kapitel 3 zeigt, dass es in dieser Form im Auto
mit hoher Wahrscheinlichkeit frustrierend ist — und zwar aus Gründen, die man ohne Fahrzeug
finden und beheben kann.

---

## 2. Zuerst das Sicherheitsnetz (Arbeitspaket M0) — blockierend

**Kein Umbau aus Kapitel 4 und 5 wird begonnen, bevor M0 grün ist.** Ausgenommen sind
die reinen Messpakete G1/G2 (sie ändern keinen Produktivcode) und die
Dokumentenordnung D1–D3 (Kapitel 6), die ohnehin vorher laufen sollte.

### M0.1 Funktions-Inventar als Vertrag

Datei neu: `FEATURES.md` im Repo-Wurzelverzeichnis.

Eine Tabelle mit jeder garantierten Fähigkeit, jeweils mit:

| Spalte | Inhalt |
|---|---|
| ID | `F-001` … stabil, wird nie neu vergeben |
| Fähigkeit | „DAB-Sender nach Name starten" |
| CLI-Prüfung | `pidrivectl play dab "ROCK FM"` |
| Erwartung | `pidrivectl now` zeigt Quelle `DAB`, Sendername gesetzt |
| Abhängigkeit | RTL-SDR, welle-cli |
| Stand | ✅ / 🟡 (nur im Fahrzeug prüfbar) / ⛔ (bekannt defekt) |

Quellen für die Inventarisierung: `ARCHITECTURE.md` (CLI-Kurzreferenz), `cli/cli.py`
(vollständige Subcommand-Liste), `KontextPiDrive.md` (Funktionsstatus),
`trigger/trigger_dispatcher.py` (alle behandelten Trigger).

**Abnahme:** `FEATURES.md` enthält mindestens jeden Trigger, den
`trigger_dispatcher.handle_trigger()` behandelt, und jedes `pidrivectl`-Subcommand.
Zeilen ohne CLI-Prüfung sind nicht erlaubt — wenn es keine gibt, ist das ein Auftrag,
eine zu bauen.

### M0.2 Golden-Master-Snapshot des Menübaums

Neu: `pidrivectl menu snapshot` schreibt den **vollständigen** Baum (siehe M1) normalisiert
nach `tests/golden/menu_tree.json`: pro Knoten `path`, `id`, `type`, `action`, `label`
(dynamische Anteile maskiert, siehe unten), Kinderreihenfolge erhalten.

Dynamische Labels müssen maskiert werden, sonst ist der Snapshot instabil. Maskierungsregeln
explizit in `tests/golden/README.md` dokumentieren, z. B.:

```
"IP: 192.168.178.100"       → "IP: <IP>"
"Ausgang: bt"               → "Ausgang: <OUTPUT>"
"Bluetooth: verbunden"      → "Bluetooth: <BT_STATE>"
"> Galaxy S21"              → "<BT_PREFIX>Galaxy S21"
"Status: aktiv"             → "Status: <SPOTIFY_STATE>"
```

Neu: `pidrivectl menu verify` vergleicht den aktuellen Baum gegen den Snapshot und listet
**Verluste** (Knoten weg), **Zugänge** (Knoten neu) und **Änderungen** (Typ/Action geändert)
getrennt auf. Exit-Code 0 nur bei „keine Verluste, keine Action-Änderungen".

**Das ist die zentrale Regressionsbremse.** Wenn ein Refactoring versehentlich das
Scanner-Untermenü oder „Aktuellen Sender merken" verliert, schlägt der Befehl fehl —
statt dass es drei Monate später im Auto auffällt.

Snapshot-Aktualisierung nur explizit über `pidrivectl menu snapshot --accept` **mit**
Eintrag in `tests/golden/CHANGES.md` (Datum, Version, Begründung, wer). Ein Snapshot-Update
ohne Begründungszeile gilt als Fehler.

### M0.3 Trigger-Contract-Test

Neu: `pidrivectl menu lint` prüft den Baum statisch und meldet:

| Prüfung | Warum |
|---|---|
| Jede `action` im Baum wird vom Dispatcher behandelt | sonst: Menüeintrag, der im Auto nichts tut |
| Jede `id` ist baumweit eindeutig | Voraussetzung für UID-Adressierung, siehe B3 |
| Jeder `folder` hat einen erreichbaren Rückweg | sonst: Sackgasse ohne Stop-Taste |
| Kein `folder` ohne Kinder | `key_enter()` läuft sonst ins Leere |
| Keine `info`-Knoten ohne `skip_on_nav` | Enter darauf ist eine Blindstelle, siehe B5 |
| Labeltiefe ≤ 64 Zeichen | AVRCP/MPRIS kürzt auf 64, `mpris2.update_metadata()` |

Für „action wird behandelt" braucht der Dispatcher eine **Registry** statt der heutigen
`if/elif`-Kette, oder mindestens einen `handle_trigger(cmd, dry_run=True)`-Pfad, der nur
„würde ich behandeln: ja/nein" zurückgibt. Der zweite Weg ist der kleinere Eingriff und
für den Anfang ausreichend.

**Abnahme M0:** `pidrivectl menu lint` und `pidrivectl menu verify` laufen, sind in
`pidrivectl test all` eingebunden, und der aktuelle Stand ist als Snapshot eingecheckt.
Gefundene Lint-Fehler werden **dokumentiert, nicht sofort behoben** — die Behebung ist
Kapitel 4.

---

## 3. Analyse: was am Menü heute nicht stimmt

Alle Befunde sind am Code verifiziert. Datei-/Zeilenangaben beziehen sich auf v0.11.127.

### B1 — Rebuild wirft den Cursor zurück (schwerwiegend, Fahrbetrieb)

`main_core.rebuild_tree()` (`main_core.py:360-380`) rettet den Pfad, setzt aber **jeden
Cursor auf 0**:

```python
menu_state._stack   = [new_root]
menu_state._cursors = [0]
for label in old_path[1:]:
    ...
    menu_state._cursors.append(0)
```

Ein Rebuild passiert nicht selten, sondern bei jedem `S["menu_rev"]`-Inkrement — und das
wird an mindestens einem Dutzend Stellen gesetzt: `bt_connect.py` (Connect, Disconnect,
Pairing, Reconnect — mehrfach), `bt_devices.py` (Scan-Ende), `modules/wifi.py` (Toggle,
Scan, Connect), `td_hardware.py`, `td_nav.py`. Zusätzlich alle 10 s bei
`store.reload_if_changed()` (`main_core.py:655-658`).

**Wirkung im Auto:** Man scrollt mit der Skip-Taste durch 50 DAB-Sender, im Hintergrund
meldet der BT-Watcher einen Zustandswechsel — und man steht wieder auf Position 0. Bei
Skip-Only-Bedienung ist das der Unterschied zwischen „benutzbar" und „unbenutzbar". Das ist
mein stärkster Verdacht dafür, dass das Menü sich im Fahrzeug nie „ausgereift" anfühlen
kann, egal wie gut der Baum ist.

**Fix:** Position über **ID-Pfad** retten, nicht nur den Ordnerpfad — und den Cursor auf die
zuvor markierte Knoten-ID zurücksetzen, nicht auf 0. Wenn die ID verschwunden ist (Sender
weg), auf den nächstliegenden Index fallen.

### B2 — Pfad-Restore über Labels bricht bei dynamischen Labels

Derselbe Code vergleicht `child.label == label`. Genau die Ordner, deren Labels sich ändern,
sind die, bei denen man sich beim Rebuild aufhält: `"> Galaxy S21"` vs. `"* Galaxy S21"`
(`menu_builder.py:350-355`), `"Ausgang: bt"`, `"Bluetooth: verbunden"`,
`"Status: aktiv"`, `"IP: …"`. Ändert sich das Label, bricht die Schleife (`break`) und man
landet in der Wurzel.

**Fix:** Restore ausschließlich über `id`. Das setzt B3 voraus.

### B3 — Knoten-IDs sind nicht garantiert eindeutig und nicht stabil

Es gibt keine Eindeutigkeitsprüfung, und mehrere ID-Bildungen können kollidieren:

| Stelle | Bildung | Kollisionsrisiko |
|---|---|---|
| `menu_builder.py:153` | `web_{name[:20]}` | zwei Webradios mit gleichem 20-Zeichen-Präfix |
| `menu_builder.py:125` | `dab_{service_id or name}` | DAB-Sender ohne `service_id`, gleicher Name |
| `menu_builder.py:281` | `lib_{ordnername[:20]}` | zwei Musikordner mit gleichem Präfix |
| `menu_builder.py:100` | `fm_{freq mit _}` | ok |

Für AVRCP-Browsing brauchen wir stabile **64-Bit-UIDs** plus einen `uid_counter`, der sich
bei Baumänderung erhöht (entspricht dem AVRCP-Event „UIDs Changed" 0x0c). Das ist zugleich
die Lösung für B1/B2.

**Fix:** Kanonische Pfad-ID (`root/sources/dab/dab_stations/dab_<service_id>`) als
Wahrheit, daraus ein stabiler 64-Bit-UID (z. B. FNV-1a/xxhash über die Pfad-ID, Kollisionen
beim Bauen erkennen und mit Suffix auflösen). `MenuNode` bekommt `uid: int` und
`path_id: str`.

### B4 — `td_radio.py` umgeht `rebuild_tree()` und erzeugt einen Stale-Tree

An drei Stellen (`td_radio.py:64-67`, `:117-120`, `:166-169`) steht:

```python
new_root = build_tree(store, S, settings)
menu_state.root = new_root
menu_state.clamp_cursors()
menu_state.rev += 1
```

Das ersetzt die Wurzel, lässt `menu_state._stack` aber auf **Knotenobjekten des alten
Baums** stehen. `current_nodes` liefert danach die alten Kinder, während `root` neu ist —
Anzeige und Navigation laufen auf einem verwaisten Teilbaum, bis der nächste echte Rebuild
kommt. Zusätzlich scheitert `clamp_cursors()` hier zwangsläufig: es sucht
`self.root.children.index(self._stack[1])` über Objekt-Identität
(`menu_state.py:153-168`) und fängt den `ValueError` mit Cursor 0 ab.

**Fix:** Ein einziger Weg für Baumtausch — `menu_state.rebuild(new_root)` als Methode in
`MenuState`, die Pfad und Cursor per ID rettet. `main_core.rebuild_tree()` und alle
`td_*`-Stellen rufen nur noch diese Methode. `menu_state.root = …` von außen zu setzen wird
verboten (Attribut privat, Setter entfernen).

### B5 — `info`-Knoten sind Blindstellen bei Skip-Only-Bedienung

`key_enter()` (`menu_state.py:108-120`) behandelt nur `folder`, `station`, `action`,
`toggle`. Bei `info` passiert **nichts** — kein Trigger, keine Rückmeldung, nicht einmal
ein `rev`-Inkrement, also auch keine Display-Aktualisierung. Betroffen sind u. a.
`ao_status`, `bt_state`, `bt_status`, `bt_last`, `sys_ip`, `wifi_status`, `spot_status`,
`{band}_info`, `fav_empty`, `dab_empty`, `web_empty`, `fm_empty`, `bt_hint`, `wifi_hint`.

Im Auto sieht der Fahrer eine Zeile und drückt Play — es passiert nichts. Für ihn ist das
System hängengeblieben. Im Ordner „Verbindungen" stehen **drei** solche Knoten am Stück.

**Fix:** `MenuNode.skip_on_nav: bool`. Info-Knoten werden bei `key_up`/`key_down`
übersprungen und sind nur für Renderer sichtbar, die eine Liste zeigen (WebUI,
Browsing-Liste). Alternativ (schlechter): Enter auf `info` wirkt wie `back`.
Wichtig: Wenn ein Ordner **nur** aus Info-Knoten besteht (z. B. `bt_geraete` ohne
Scan-Ergebnis), muss trotzdem ein Eintrag anwählbar bleiben — der „Zurueck"-Knoten.

### B6 — Favoriten-Umschalter pro Sender ist im Auto unerreichbar

Station-Knoten bekommen ein Kind (`_fav_node`, `menu_builder.py:74-84`, angehängt bei
`:104-108`, `:130-133`, `:161-166`). `key_enter()` auf einen `station`-Knoten gibt aber den
Knoten zum Abspielen zurück und steigt nie in die Kinder ab. Der Kommentar im Code sagt das
auch: „nur über WebUI erreichbar".

Damit trägt jeder Sender-Knoten ein unerreichbares Kind mit sich — Ballast im Baum, der
beim Browsing-Export später als echter Unterordner auftauchen würde.

**Fix (Entscheidung nötig, siehe Kapitel 8):** Entweder die Sender-Favorisierung
ausschließlich über „Favoriten → Aktuellen Sender merken" führen (dann `_fav_node` aus dem
Baum entfernen und die WebUI direkt auf die Favoriten-API gehen lassen), oder Station-Knoten
als „playable folder" modellieren, den das Browsing-Menü öffnen kann. Für die
Skip-Only-Bedienung ist Variante 1 klar besser.

### B7 — `navigate_to()` erreicht nur Wurzelkinder

`menu_state.py:134-151` durchsucht ausschließlich `self.root.children`. Es gibt keine
Möglichkeit, gezielt auf `Quellen → DAB+ → Sender → ROCK FM` zu springen — weder aus der
CLI, noch aus der WebUI, noch für einen Test. Das ist der Grund, warum es bisher keinen
automatisierten Menü-Test geben kann.

**Fix:** `goto(path_id)` und `activate(uid)` als kopflose API (siehe M2).

### B8 — Zwei AVRCP-Eingänge mit unterschiedlichem Mapping

`integration/avrcp_trigger.py` mappt kontextabhängig (`get_context()` + `map_event()`),
`mpris2.py` mappt fest (Next→`down`, Stop→`back`, …). Welcher Pfad das BMW bedient, ist
unbestätigt (`iDriveBt.md` §6.1 führt es als offenen Punkt). Im Menü-Kontext liefern beide
dasselbe, in Radio-/Scanner-Kontexten nicht.

**Wirkung:** Solange das offen ist, sind **alle** Fahrzeugmessungen am Menü nicht
reproduzierbar — man weiß nicht, welche Mapping-Tabelle gerade gilt.

**Fix vor dem Feldtest:** Ein Eingang bleibt Wahrheit. Empfehlung: `avrcp_trigger.py` als
einzige Semantikquelle; `mpris2.py` reicht empfangene Kommandos **unverändert als Event**
weiter (`next`, `previous`, …), statt selbst auf Trigger zu mappen. Dann gibt es genau eine
`map_event()`-Tabelle — und genau die braucht später auch der Gateway-Pfad, weil PDAP
Event-Namen liefert.

### B9 — `export()` zeigt nur die aktuelle Ebene

`menu_state.export()` (`menu_state.py:170-187`) exportiert `current_nodes` plus
Legacy-Kompatibilitätsfelder (`cat`, `item`, `categories`, `items`). Niemand — WebUI, CLI,
Test, späterer Browsing-Export — kann den ganzen Baum sehen. Die Legacy-Felder sollten nach
M1 als deprecated markiert und mit einem Zieldatum entfernt werden.

### B10 — Ergonomie ist nie gemessen worden

Bei Skip-Only-Bedienung ist die einzig relevante Kennzahl: **Wie viele Tastendrücke bis zum
Ziel?** Heute weiß das niemand. Beispiel Wurzel → `Quellen`(1×down, enter) →
`DAB+`(2×down… je nach Reihenfolge) → `Sender`(enter) → Sender *n* (n×down) → enter.
Bei 50 Sendern sind das leicht 55+ Tastendrücke — im fahrenden Auto.

**Das ist die eigentliche Antwort auf „ist das Menü ausgereift?"** — und sie ist messbar,
siehe M5.

---

## 4. Arbeitspakete Menü (M1–M6)

### M1 — Baum als Datenstruktur mit stabilen UIDs

**Dateien:** `menu/menu_state.py`, `menu/menu_builder.py`, `menu/menu_model.py`, `ipc.py`

1. `MenuNode` erweitern: `path_id: str`, `uid: int`, `skip_on_nav: bool = False`.
2. Nach `build_tree()` einen **Post-Processing-Lauf**: Baum rekursiv durchlaufen,
   `path_id` aus Elternpfad + `id` bilden, `uid` daraus stabil hashen, Kollisionen
   erkennen und mit Zählersuffix auflösen, `skip_on_nav` für `type == "info"` setzen.
   Bewusst als eigener Durchlauf, damit `build_tree()` inhaltlich unangetastet bleibt —
   das hält das Diff klein und das Regressionsrisiko niedrig.
3. `export_tree()` in `MenuState`: vollständiger Baum, mit `uid_counter`, der sich bei
   jedem Baumtausch erhöht, in dem sich die UID-Menge geändert hat (nicht bei jedem
   Rebuild — sonst invalidiert der Browsing-Client ständig).
4. `ipc.write_menu_tree()` → `/tmp/pidrive_menu_tree.json`, geschrieben nur bei
   geändertem `uid_counter` (nicht in der 0,2-s-Schleife).

**Abnahme:** `pidrivectl menu tree --json` liefert den ganzen Baum; jede `uid` ist
eindeutig; zwei aufeinanderfolgende Aufrufe ohne Zustandsänderung liefern identische UIDs
(Stabilität!); `uid_counter` bleibt dabei gleich.

### M2 — Kopflose Navigations-API

**Dateien:** `menu/menu_state.py`, `trigger/td_nav.py`

- `MenuState.rebuild(new_root)` — einziger erlaubter Weg für Baumtausch, rettet Pfad **und**
  Cursor über `path_id`/`uid` (behebt B1, B2, B4).
- `MenuState.goto(path_id) -> bool` — beliebige Tiefe (behebt B7).
- `MenuState.activate(uid) -> node | None` — entspricht `enter` auf einem Knoten, ohne
  vorher dorthin navigieren zu müssen. Das ist das PDAP-/Browsing-`PlayItem`-Äquivalent.
- `key_up`/`key_down` respektieren `skip_on_nav` (behebt B5).
- Alle direkten `menu_state.root = …`-Zuweisungen entfernen.

**Abnahme:** `pidrivectl menu goto <path_id>` und `pidrivectl menu activate <uid>`
funktionieren; `pidrivectl menu lint` meldet keine Sackgassen mehr.

### M3 — Rebuild-Robustheit

**Dateien:** `main_core.py`, `trigger/td_radio.py`, `trigger/trigger_dispatcher.py`

`rebuild_tree()` auf `MenuState.rebuild()` umstellen, die drei Stellen in `td_radio.py`
ebenfalls. Danach den Kommentar in `trigger_dispatcher.py:116-120` prüfen: Die dortige
Warnung („ein sofortiger Rebuild danach setzt den Cursor auf 0 zurück!") ist mit
ID-basiertem Restore gegenstandslos und die `rebuild_cmds`-Whitelist kann vermutlich
vereinfacht werden — **aber erst nach** grünem `menu verify`.

**Abnahme:** Neuer Test `pidrivectl test menu-rebuild`: tief navigieren
(`goto sources/dab/dab_stations`, 5× down), Rebuild auslösen (`menu rebuild --force`),
danach müssen Pfad **und** markierter Knoten identisch sein. Zusätzlich mit einem
absichtlich entfernten Sender: Cursor muss auf einen Nachbarn fallen, nicht auf 0.

### M4 — Baum-Ergonomie für Skip-Only

Erst **nach** M5 (Messung) entscheiden und umsetzen, sonst optimieren wir ins Blaue. Kandidaten:

- Häufigstes zuerst: Favoriten stehen schon vorn — messen, ob das reicht.
- Sender-Direktsprung: „Nächster/Vorheriger Sender" nach oben, weil das ohne Liste
  funktioniert und bei Skip-Only unschlagbar ist.
- Alphabet-/Blocksprung in langen Listen (jeder 10. Sender als Ankerknoten).
- `cat:0`-Doppeltipp existiert (Sprung an den Menüanfang) — im Baum sichtbar dokumentieren.
- Selten benutzte Zweige (Scanner-Bänder, WiFi-Netzwerke) tiefer legen.

**Abnahme:** Kennzahlen aus M5 verbessern sich messbar; `menu verify` weist keine Verluste
aus (nur bewusste, in `CHANGES.md` begründete Umstellungen).

### M5 — Ergonomie messen (das Reifegrad-Urteil)

Neu: `pidrivectl menu cost <path_id>` — minimale Tastendrücke bei Skip-Only-Bedienung
(`down`/`up`/`enter`, kein `back`, weil Stop im Fahrzeug unzuverlässig ist), inklusive der
„Zurueck"-Einträge als normale Knoten.

Neu: `pidrivectl menu report` — Tabelle über alle Blätter: Tiefe, Kosten, erreichbar
ja/nein. Plus Kennzahlen: Median- und Maximalkosten, Anzahl Blätter mit Kosten > 20,
unerreichbare Knoten.

**Das ist die Antwort auf die Ausgangsfrage.** Sie macht aus „fühlt sich unreif an" eine
Zahl, die man vor und nach M4 vergleichen kann. Ergebnis als
`docs/menue/MENU-ERGONOMIE.md` einchecken (Vorher-Stand zuerst, damit der Fortschritt belegbar
ist).

### M6 — iDrive-Simulation für die Couch

Neu: `pidrivectl idrive <next|previous|play|pause|stop|vol_up|vol_down>` — speist das
Event **auf Event-Ebene** ein, also genau dort, wo `avrcp_trigger.py` es einspeisen würde,
inklusive `get_context()`/`map_event()` und Double-Tap-Fenster (1,2 s). Nicht zu verwechseln
mit dem vorhandenen `pidrivectl inject <trigger>` (`cli.py:386`), das die
**Trigger**-Ebene bedient und damit das Mapping überspringt.

Neu: `pidrivectl idrive script <datei>` — Sequenz aus Zeilen wie `next`, `next`, `play`,
`sleep 1.5`, abspielen und nach jedem Schritt Pfad + markierten Knoten protokollieren.

Damit ist die komplette 2-Tasten-Bedienung ohne Fahrzeug testbar — und im Fahrzeug kann man
dieselben Skripte über SSH gegen die echte AVRCP-Strecke laufen lassen und vergleichen.

**Abnahme:** Ein eingecheckter Testpfad, z. B. `tests/idrive/rockfm.txt`, startet aus der
Wurzel einen bestimmten DAB-Sender und endet mit `radio_type == DAB` und passendem
Sendernamen.

---

## 5. Arbeitspakete Gateway-Vorbereitung (G1–G4)

### G1 — BMW-Browsing-Probe (Messung, keine Implementierung) — höchste Priorität

Das ist die Messung, die im Gateway-Repo über die Architektur entscheidet, und sie läuft auf
dem Pi mit vorhandener Hardware. Neu: `tools/bmw_avrcp_probe.sh` + `pidrivectl bt probe`.

Ablauf:

1. `btmon -w /var/log/pidrive/bmw_probe_<ts>.btsnoop` im Hintergrund starten.
2. BMW verbinden lassen (Zündung an) bzw. `pidrivectl bt reconnect`.
3. SDP-Record des BMW und den eigenen auslesen und protokollieren:
   `sdptool browse <BMW-MAC>` und `sdptool browse local`. Festhalten: AVRCP-Version
   (Profile Descriptor), `SupportedFeatures`-Bits, insbesondere **Bit 59 (Browsing)**,
   **Bit 60 (Searching)**, **Bit 65 (NowPlaying)**, und ob ein
   **Additional Protocol Descriptor mit AVCTP-Browsing-PSM 0x001B** vorhanden ist.
4. Zehn Minuten mitschneiden, dabei im iDrive nach „Multimedia → Bluetooth" navigieren,
   die Medienliste/Titelliste öffnen, Skip/Play drücken, Quelle wechseln, einmal Zündung
   aus/an.
5. Auswertung: `btmon -r <datei>` und im Log nach folgenden Signaturen suchen —
   `btmon`s AVCTP-Dekoder benennt sie im Klartext (`monitor/avctp.c`):
   `SetBrowsedPlayer`, `GetFolderItems`, `ChangePath`, `GetItemAttributes`, `PlayItem`,
   `GetTotalNumberOfItems`, `SetAddressedPlayer`, `Media Player List`,
   `Media Player Virtual Filesystem`, `Now Playing`.

Interpretationsschlüssel — **vorher festschreiben**, damit das Ergebnis eindeutig ist:

| Beobachtung | Bedeutung |
|---|---|
| BMW öffnet L2CAP PSM 0x001B **nicht** | Browsing ist am NBT Evo nicht nutzbar → echtes Listen-Menü über BT fällt weg, 3-Zeilen-Pfad bleibt BT-Zielbild. Alternative Untersuchung: USB-MSC-Menü — [../planung/IDEE-USB-MSC-MENUE.md](../../planung/IDEE-USB-MSC-MENUE.md) |
| BMW öffnet den Kanal, fragt nur `GetFolderItems(scope=0x00)` | Es prüft nur die Player-Liste; noch kein Beweis für nutzbares Browsing |
| BMW sendet `SetBrowsedPlayer` (BlueZ antwortet ablehnend) | **Grünes Licht** — das Auto *will* browsen, BlueZ kann es nur nicht. Genau diese Lücke füllt ein eigener AVRCP-Target-Stack auf dem ESP32 |
| BMW sendet `GetFolderItems(scope=0x01)` oder `ChangePath` | Starkes grünes Licht, inkl. Hinweis auf erwartete Attributliste und Seitengröße |

Ergebnis als `docs/fahrzeug/BMW-AVRCP-PROBE.md` einchecken: rohe Signaturen, Interpretation,
btsnoop-Datei referenziert. Diese Datei ist der Input für das Gateway-Repo.

> Wichtig: Ein negatives Ergebnis ist **wertvoll**, nicht enttäuschend. Es spart im anderen
> Repo die Entscheidung für einen aufwendigen Stackwechsel.

### G2 — Display-Pfad im Fahrzeug endlich bestätigen

Der `art_url`-Fix ist seit v0.11.123 drin, aber unbestätigt. Vor allen Menü-Umbauten muss
belegt sein, dass die drei Zeilen im Auto ankommen — sonst testet man später gegen eine
unbekannte Größe.

Neu: `pidrivectl idrive display-probe` — setzt über `mpris2` nacheinander definierte
Zeilen (`"PROBE 1/3"`, `"PROBE 2/3"`, `"PROBE 3/3"`), jeweils 5 s, und protokolliert, was
gesendet wurde. Der Fahrer notiert, was das Display zeigt. Ergebnis nach
`docs/fahrzeug/BMW-DISPLAY-PROBE.md`: Welche Zeile ist Titel/Interpret/Album, wie viele Zeichen
werden dargestellt, wie schnell aktualisiert das Display, ab welcher Änderungsrate hängt es
(das 300-ms-Rate-Limit in `mpris2.py` validieren).

Gleichzeitig ist das der Test für B8: Beim Drücken der Lenkradtasten protokollieren, ob
`avrcp_trigger.py` oder der `mpris2.py`-Pfad reagiert hat — dafür in beiden Pfaden eine
unterscheidbare Logzeile einbauen (`AVRCP_INGRESS path=dbus|mpris event=next`).

### G3 — Handy/Tablet als Quelle: Pi wird A2DP-Sink

**Nicht** vor G1/G2 anfangen. Umfang:

1. **WirePlumber-Rolle erweitern.** Heute ist bewusst nur Source aktiv:
   `bluez5.roles = [ a2dp_source ]` (`pipewire-config/wireplumber.conf.d/50-bluetooth-pidrive.conf`,
   dokumentiert in `iDriveBt.md` §5.4 und `scripts/fix-bt-a2dp.sh`). Für Sink-Betrieb muss
   `a2dp_sink` hinzukommen. **Achtung, hohes Regressionsrisiko:** Genau diese Einschränkung
   war Teil der A2DP-Stabilisierung in v0.11.117–122. Änderung isoliert, mit Vorher-/Nachher-
   Messung über `pidrivectl test bt` und `pidrivectl diagnose`, und mit dokumentiertem
   Rückweg.
2. **Neues Modul** `modules/bluetooth/bt_sink.py`: eingehende A2DP-Verbindungen annehmen
   (Agent existiert: `bt_agent.py`), Quellknoten finden (Gegenstück zu
   `find_bt_sink_for_mac()` in `bt_audio.py`), in die reguläre Audiokette einspeisen.
3. **Neue Quelle** in der Source-State-Machine (`modules/source_state.py`) und im Menü:
   `Quellen → Bluetooth-Geräte` mit den gekoppelten Handys/Tablets; Auswahl schaltet die
   aktive Quelle um. Mehrere Geräte dürfen gekoppelt sein, **eines** streamt.
4. **Metadaten**: PiDrive wird hier AVRCP **Controller** gegenüber dem Handy.
   BlueZ liefert das über `org.bluez.MediaPlayer1` des Handy-Geräts — Titel/Interpret
   auslesen und in die bestehende Metadatenkette einspeisen, damit sie weiter ans BMW
   gehen. Steuerkommandos (Skip/Play) müssen dann vom BMW **durchgereicht** werden:
   BMW → PiDrive-Event → wenn Quelle `bt_in`, dann AVRCP-Kommando ans Handy.
   Das ist ein neuer Fall in `map_event()` und gehört ins Mapping-Dokument.
5. **CLI**: `pidrivectl btin status|devices|select <mac>|disconnect`.

**Abnahme:** Handy koppelt sich, spielt, Titel erscheint in `pidrivectl now`, Skip vom
BMW steuert das Handy, und `pidrivectl test all` bleibt grün — insbesondere die
BT-A2DP-**Source**-Tests, die nicht regredieren dürfen.

### G4 — Gateway-Schnittstelle vorbereiten (nur Vorbereitung!)

Die Gateway-Anbindung selbst (`integration/gateway_client.py`, `audio_output=gateway`,
PDAP) wird **erst begonnen, wenn das Gateway-Repo den PDAP-Contract freigegeben hat**.
Vorher nur die Nahtstellen schaffen, die ohnehin Sinn ergeben:

- `map_event()` so herausziehen, dass es ohne D-Bus aufrufbar und einzeln testbar ist —
  der Gateway-Pfad wird dieselbe Funktion mit PDAP-Event-Namen speisen.
- `mpris2.update()` in „Metadaten berechnen" und „Metadaten an BlueZ senden" trennen,
  damit derselbe Datensatz später an PDAP gehen kann.
- Dokumentieren, welche Quellen **nicht** durch PipeWire laufen: DAB startet welle-cli
  direkt auf ALSA (`modules/radio/dab_play.py`, `welle_direct_alsa`, entfernt `PULSE_*`
  aus der Umgebung und schreibt `/etc/asound.conf`). Das ist der bekannte Blocker für
  Gateway-DAB und ein eigenes Arbeitspaket — hier **nur dokumentieren**, nicht umbauen.

---

## 6. Arbeitspakete Dokumentenordnung (D1–D6)

Die Dokumentation liegt heute unstrukturiert im Wurzelverzeichnis. Das ist nicht
kosmetisch: Dieser Auftrag erzeugt allein sieben neue Dokumente (`FEATURES.md`,
`ABNAHMEN.md`, `MENU-ERGONOMIE.md`, `BMW-AVRCP-PROBE.md`, `BMW-DISPLAY-PROBE.md`,
`tests/golden/README.md`, `tests/golden/CHANGES.md`). Ohne Ordnung vorher wird es
hinterher schlimmer.

### 6.0 Befund: was heute im Wurzelverzeichnis liegt

Elf Markdown-Dateien, ~3.100 Zeilen, drei verschiedene Namenskonventionen:

| Datei | Zeilen | Art | Konvention |
|---|---|---|---|
| `README.md` | 168 | Projekt-Einstieg | — |
| `ARCHITECTURE.md` | 270 | Referenz: Struktur, IPC, Services | `SCREAMING_SNAKE` |
| `RUNTIME_FLOWS.md` | 410 | Referenz: Laufzeitpfade, Menü→Display | `SCREAMING_SNAKE` |
| `DEVELOPER_GUIDE.md` | 197 | Referenz: wo liegt welcher Code | `SCREAMING_SNAKE` |
| `TROUBLESHOOTING.md` | 259 | Betrieb: Fehlerbehebung | `SCREAMING_SNAKE` |
| `MIGRATION_BACKLOG.md` | 76 | Prozess, teils erledigt | `SCREAMING_SNAKE` |
| `MIGRATION_STRUCTURE.md` | 55 | Prozess, **veraltet** (Stand v0.11.96) | `SCREAMING_SNAKE` |
| `iDriveBt.md` | 583 | Fahrzeug: BT/AVRCP/MPRIS2-Referenz | `camelCase` |
| `BluetoothError.md` | 249 | Fahrzeug/Betrieb: A2DP-Fehleranalyse | `camelCase` |
| `KontextPiDrive.md` | 366 | Entscheidungsverlauf + Changelog | `camelCase` |
| `AUFTRAG-MENUE-UND-GATEWAY.md` | 482 | dieses Dokument | `KEBAB-CASE` |

**Gute Nachricht zum Risiko:** Kein Python-Code hängt an Dokumentpfaden. Es gibt genau
**einen** Verweis außerhalb der Dokumente — einen Kommentar in
`scripts/fix-bt-a2dp.sh:3`. Der Umzug ist also fast risikofrei, anders als beim
Verschieben von Skripten (siehe D6).

Zu reparieren sind: rund 16 gegenseitige Verweise zwischen den Dokumenten, der Verweis in
`README.md:219`, der Kommentar in `fix-bt-a2dp.sh` — und, wichtig, die **repo-übergreifenden**
Verweise aus `esp32.bt-gateway/docs/planung/PIDRIVE-INTEGRATION.md` (Abschnitte 2 und 11
verlinken `iDriveBt.md`, `BluetoothError.md`, `ARCHITECTURE.md`, `RUNTIME_FLOWS.md`).

**Zusätzlich vorgefundene Doku-Fäulnis**, die bei der Gelegenheit mit erledigt wird:

- `README.md` nennt **vier verschiedene Versionen**: Badge `0.11.126`, Schnellstart
  „sollte 0.11.103 sein" (Zeile 43), Highlight-Kasten „v0.11.104" (Zeile 25),
  Abschnitt „Versionierung" `0.11.104` (Zeile 225). Tatsächlicher Stand: **0.11.127**.
- `MIGRATION_STRUCTURE.md` beschreibt einen Stand von v0.11.96 und ist inzwischen
  sachlich falsch: `mpris2.py` liegt weiter unter `pidrive/mpris2.py` (nicht in
  `integration/`), die `menu_*.py` sind längst echte Module in `menu/`.
- Die Referenzdokumente tragen „Stand v0.11.122", `KontextPiDrive.md` dagegen v0.11.127.
  Es gibt keine Konvention, wann ein Versionsstempel nachgezogen wird.

### D1 — Zielstruktur festlegen

**Regel: Kein Dokument im Wurzelverzeichnis außer `README.md`.**

Im Wurzelverzeichnis bleiben nur: `README.md`, `LICENSE`, `VERSION`,
`config.txt.example` und `install.sh`.

> ⚠️ **`install.sh` darf sich nicht bewegen.** Die Installation läuft über
> `curl -sL https://raw.githubusercontent.com/MPunktBPunkt/pidrive/main/install.sh | bash`.
> Dieser Einzeiler steht in `README.md`, in `KontextPiDrive.md` und in externer
> Kommunikation. Ein Umzug bricht jede bestehende Installationsanleitung.

Zielstruktur:

```
pidrive/
├── README.md                      ← Einstieg, bleibt (GitHub-Konvention)
├── LICENSE · VERSION · install.sh · config.txt.example
└── docs/
    ├── README.md                  ← Index: welches Dokument für wen (D3)
    ├── FEATURES.md                ← Funktions-Inventar (M0.1)
    ├── ABNAHMEN.md                ← Abnahmeprotokolle (7.2)
    ├── KONTEXT.md                 ← Entscheidungsverlauf + Changelog
    ├── architektur/
    │   ├── ARCHITEKTUR.md         ← Struktur, IPC, Services
    │   ├── LAUFZEITPFADE.md       ← Laufzeitpfade, Menü→Display
    │   └── ENTWICKLERHANDBUCH.md  ← wo liegt welcher Code
    ├── betrieb/
    │   ├── FEHLERBEHEBUNG.md
    │   └── BLUETOOTH-FEHLER.md
    ├── fahrzeug/
    │   ├── IDRIVE-BLUETOOTH.md    ← BT/AVRCP/MPRIS2-Referenz
    │   ├── BMW-AVRCP-PROBE.md     ← Ergebnis G1
    │   └── BMW-DISPLAY-PROBE.md   ← Ergebnis G2
    ├── menue/
    │   └── MENU-ERGONOMIE.md      ← Ergebnis M5
    ├── auftraege/
    │   └── AUFTRAG-MENUE-UND-GATEWAY.md
    └── archiv/
        ├── MIGRATION_BACKLOG.md
        └── MIGRATION_STRUCTURE.md
```

Die Ordnernamen sind deutsch, weil der gesamte Inhalt deutsch ist. Die **Dateinamen**
bleiben in diesem Schritt unverändert — Umzug und Umbenennung werden getrennt, weil jede
Umbenennung die Menge der zu reparierenden Verweise (inklusive zweitem Repo) vervielfacht.
Die Umbenennung auf die oben genannten Zielnamen ist ein eigener, optionaler Schritt und
Entscheidung des Eigentümers (E7). Bis dahin gilt: `docs/architektur/ARCHITECTURE.md` usw.

### D2 — Verschieben, in einem Commit, ohne Inhaltsänderung

Ausschließlich `git mv`, damit die Historie den Dateien folgt (`git log --follow`).
Kein Kopieren-und-Löschen, kein Editieren im selben Commit — der Commit muss als reiner
Umzug erkennbar sein:

```
docs/architektur/  ← ARCHITECTURE.md · RUNTIME_FLOWS.md · DEVELOPER_GUIDE.md
docs/betrieb/      ← TROUBLESHOOTING.md · BluetoothError.md
docs/fahrzeug/     ← iDriveBt.md
docs/archiv/       ← MIGRATION_BACKLOG.md · MIGRATION_STRUCTURE.md
docs/auftraege/    ← AUFTRAG-MENUE-UND-GATEWAY.md
docs/              ← KontextPiDrive.md  (Zielname KONTEXT.md erst mit E7)
```

**Abnahme D2:** `git status` zeigt ausschließlich Renames (`R`), keine Modifikationen.
`git log --follow docs/fahrzeug/iDriveBt.md` zeigt die vollständige Historie.

### D3 — Verweise reparieren und Index anlegen

Eigener Commit nach D2.

1. Alle relativen Links in den verschobenen Dokumenten korrigieren (16 Stellen, die
   Trefferliste liefert `rg -n '\.md' docs/`).
2. `README.md:219` („Weitere Docs: …") auf `docs/README.md` umstellen — ein Link statt
   drei, damit der Index die einzige Pflegestelle bleibt.
3. Kommentar in `scripts/fix-bt-a2dp.sh:3` nachziehen.
4. **`docs/README.md` als Index** anlegen: pro Dokument eine Zeile mit Zweck, Zielgruppe
   („Entwickler" / „Betrieb im Fahrzeug" / „Planung") und Stand-Version. Der Index ist
   ab dann die einzige Stelle, an der Dokumente aufgelistet werden.
5. **Zweites Repo informieren:** Die Verweise in
   `esp32.bt-gateway/docs/planung/PIDRIVE-INTEGRATION.md` (Abschnitte 2 und 11) und in
   `AUFTRAG-CURSOR-2.md` zeigen auf die alten Pfade. Nicht selbst dort editieren —
   stattdessen eine Pfad-Mapping-Tabelle (alt → neu) an die Gateway-Instanz übergeben
   und in `docs/README.md` mitführen, damit alte Verweise auffindbar bleiben.
6. **Link-Prüfer** `tools/check_docs.sh`: prüft, dass jeder relative Markdown-Link im
   Repo auf eine existierende Datei zeigt, und meldet Dokumente, die von keinem anderen
   Dokument und nicht vom Index verlinkt werden (Waisen). Wird Teil der
   Regressionsmatrix (R8).

**Abnahme D3:** `tools/check_docs.sh` läuft ohne Fehler, kein Dokument ist Waise,
`docs/README.md` listet alle Dokumente.

### D4 — Doku-Fäulnis beseitigen

Eigener Commit, danach.

1. **Version nur noch an einer Stelle im README.** Die drei Prosa-Versionsangaben
   (Zeilen 25, 43, 225) entfernen bzw. auf „aktuelle Version siehe `VERSION`" umstellen.
   Der Badge darf bleiben, muss aber in die Release-Routine aufgenommen werden —
   sonst entsteht die Divergenz beim nächsten Bump erneut.
2. **Versionsstempel-Konvention** in `docs/README.md` festschreiben: Jedes Dokument
   beginnt mit `**Stand:** vX.Y.Z · <Datum>`. Wer ein Verhalten ändert, zieht den Stempel
   im betroffenen Dokument nach. Dokumente mit Stempel älter als zehn Patch-Versionen
   gelten als prüfbedürftig und werden im Index markiert.
3. **`MIGRATION_STRUCTURE.md` und `MIGRATION_BACKLOG.md`** nach `docs/archiv/` mit einem
   Kopfhinweis: „Historisch, Stand v0.11.96, nicht mehr gepflegt". Ob der Shim-Abbauplan
   als eigenes, aktuelles Dokument neu entsteht, entscheidet der Eigentümer (E8) — die
   Shims sind weiter aktiv in systemd-Units referenziert und damit ein echtes offenes
   Thema, nur eben nicht mehr in dieser Form beschrieben.
4. `docs/architektur/ARCHITECTURE.md` und `RUNTIME_FLOWS.md` auf v0.11.127 prüfen: Die
   Menü-Abschnitte werden durch M1–M4 ohnehin angefasst; hier nur offensichtlich
   Falsches korrigieren, **keine** inhaltliche Neufassung (die gehört in die jeweiligen
   Arbeitspakete).

### D5 — Rückfall verhindern

In `docs/README.md` als verbindliche Regel aufnehmen:

- Neue Dokumente kommen **immer** nach `docs/<kategorie>/`, niemals ins
  Wurzelverzeichnis. Passt keine Kategorie, wird eine angelegt und im Index begründet.
- Neue Dateinamen: `KEBAB-CASE.md`, deutsch, sprechend (`BMW-AVRCP-PROBE.md`).
  Kein `camelCase`, kein `SCREAMING_SNAKE` mehr.
- Jedes neue Dokument wird im selben Commit in `docs/README.md` eingetragen —
  sonst schlägt der Waisen-Check in `tools/check_docs.sh` fehl.
- Ergebnis-Dokumente (Messungen, Abnahmen) tragen Datum und Version im Kopf und werden
  **nicht** überschrieben, sondern ergänzt; für Wiederholungsmessungen einen neuen
  Abschnitt anlegen, damit die Entwicklung nachvollziehbar bleibt.

### D6 — Skripte im Wurzelverzeichnis (optional, erhöhtes Risiko)

Im Wurzelverzeichnis liegen außerdem vier Shell-Skripte
(`pidrive_boot_debug.sh`, `pidrive_car_only_cleanup.sh`, `pidrive_debug.sh`,
`setup_bt_audio.sh`), während `scripts/` und `tools/` schon existieren. Das ist dieselbe
Unordnung — aber **nicht** dasselbe Risiko. Betroffen wären:

| Verweis | Datei |
|---|---|
| `ExecStart=/bin/bash /home/pi/pidrive/pidrive_boot_debug.sh` | `systemd/pidrive_boot_debug.service:9` |
| `bash "$INSTALL_DIR/pidrive_car_only_cleanup.sh"` (3×) + Hinweistext | `install.sh:1265,1270,1290,1294` |
| Fix-Hinweise an den Benutzer | `diagnose.py:265,805` |
| Eigene Aufrufhinweise in den Skript-Köpfen | alle vier Skripte |

Dazu kommen Installationen im Feld, in denen die alten Pfade in `~/pidrive/` liegen und
per `git pull` aktualisiert werden — ein Umzug verändert dort dokumentierte
Handgriffe.

**Empfehlung: zurückstellen.** D6 ist kein Dokumentationsthema, sondern ein
Installer-Thema und gehört in ein eigenes Paket mit eigenem Feldtest. Wenn es doch
gemacht wird: `scripts/` als Ziel, alle vier Verweisstellen im selben Commit, und
`pidrivectl diagnose` plus eine Neuinstallation als Abnahme.

**Abnahme Kapitel 6 gesamt:** Im Wurzelverzeichnis liegt nur noch `README.md` als
Dokument, `tools/check_docs.sh` ist grün, der Index ist vollständig, und die
Pfad-Mapping-Tabelle ist an das Gateway-Repo übergeben.

---

## 7. Testdefinition (verbindlich)

### 7.1 Neue CLI-Oberfläche

Alles unter zwei neuen Gruppen, damit nichts Bestehendes verändert wird:

```
pidrivectl menu tree [--json] [--depth N]     Baum anzeigen
pidrivectl menu path                          aktueller Pfad + markierter Knoten
pidrivectl menu goto <path_id>                gezielt navigieren
pidrivectl menu activate <uid>                Knoten auslösen (PlayItem-Äquivalent)
pidrivectl menu rebuild [--force]             Rebuild auslösen (Test)
pidrivectl menu lint                          statische Prüfungen (M0.3)
pidrivectl menu snapshot [--accept]           Golden Master schreiben
pidrivectl menu verify                        gegen Golden Master prüfen
pidrivectl menu cost <path_id>                Tastendrücke bis Ziel
pidrivectl menu report                        Ergonomie-Kennzahlen
pidrivectl menu walk                           Baum vollständig ablaufen

pidrivectl idrive <event>                     AVRCP-Event simulieren (Event-Ebene!)
pidrivectl idrive script <datei>              Sequenz abspielen
pidrivectl idrive display-probe               Display-Zeilen testen
pidrivectl btin status|devices|select|disconnect
pidrivectl bt probe                            BMW-AVRCP-Probe (G1)
```

Das vorhandene `pidrivectl inject` und `pidrivectl debug menu` bleiben unverändert
(Rückwärtskompatibilität, sie sind in Skripten und Doku referenziert).

### 7.2 Regressionsmatrix — bei jedem Arbeitspaket auszuführen

| Stufe | Befehl | Muss |
|---|---|---|
| R1 | `pidrivectl menu lint` | 0 Fehler |
| R2 | `pidrivectl menu verify` | 0 Verluste, 0 Action-Änderungen |
| R3 | `pidrivectl menu walk` | jeder Ordner erreichbar, jeder mit Rückweg |
| R4 | `pidrivectl test menu-rebuild` | Position übersteht Rebuild |
| R5 | `pidrivectl idrive script tests/idrive/*.txt` | alle Sollzustände erreicht |
| R6 | `pidrivectl test all` | keine neue Regression gegenüber Vorlauf |
| R7 | `pidrivectl diagnose` | keine neuen Warnungen |
| R8 | `tools/check_docs.sh` | alle Doku-Links gültig, keine Waisen (D3) |

R1–R5 und R8 laufen ohne Hardware (auch auf dem Futro S920) und gehören in `pidrivectl test all`.
R6/R7 brauchen RTL-SDR bzw. BT.

**Nach jedem Arbeitspaket** die Matrix in die Commit-Message oder nach
`docs/ABNAHMEN.md` schreiben — mit Datum, Version, Ergebnis. Genau diese Spur fehlte in der
Vergangenheit.

### 7.3 Was ein Arbeitspaket nicht sein darf

- Kein Paket, das gleichzeitig Menü **und** Audio/BT anfasst.
- Kein „Aufräumen im Vorbeigehen" — Legacy-Felder (`export()`-Kompatibilität, Shims in
  `modules/dab.py`, `webui.py`, `avrcp_trigger.py`) werden nur nach ausdrücklichem
  Auftrag entfernt. Die Shims sind aktiv in systemd-Units referenziert
  (`pidrive_web.service`, `pidrive_avrcp.service`).
- Keine Version-Bumps ohne Eintrag in `KontextPiDrive.md` (Changelog-Konvention des
  Projekts).
- Keine Änderung an der WirePlumber-/PipeWire-Konfiguration außerhalb von G3.

---

## 8. Entscheidungen, die der Eigentümer treffen muss

Nicht selbst entscheiden, sondern sammeln und vorlegen:

| # | Frage | Empfehlung |
|---|---|---|
| E1 | B6: Sender-Favorisierung nur über „Aktuellen Sender merken"? | Ja — entlastet den Baum, Skip-Only-freundlich |
| E2 | B8: `avrcp_trigger` als einzige Semantikquelle, `mpris2` nur Event-Weitergabe? | Ja, vor dem Feldtest |
| E3 | Info-Knoten überspringen oder als `back` behandeln? | Überspringen (`skip_on_nav`) |
| E4 | Soll `menu verify` in CI laufen (GitHub Actions) oder nur lokal? | CI, sobald M0 steht |
| E5 | G3: Pi gleichzeitig Sink (Handy) und Source (BMW) auf einem Dongle — oder Sink erst, wenn der ESP das BMW übernimmt? | Erst messen, Zielbild ist „Pi nur Sink" |
| E6 | Reihenfolge G1 vs. M1: Messung zuerst oder Umbau zuerst? | G1 zuerst, wenn ein Fahrzeugtermin greifbar ist — die Messung blockiert das andere Repo |
| E7 | D1: Dateinamen auf deutsche `KEBAB-CASE`-Zielnamen umbenennen, oder Namen behalten? | Erst umziehen, später umbenennen — und nur, wenn beide Repos gleichzeitig nachgezogen werden |
| E8 | D4: Shim-Abbauplan als neues, aktuelles Dokument, oder Thema ganz vertagen? | Neu schreiben, sobald die Menü-Pakete durch sind — die Shims sind ein echtes offenes Thema |

---

## 9. Reihenfolge und Definition of Done

```
D1–D3  Dokumente nach docs/ + Index + Link-Prüfer           ← zuerst, billig, entlastet alles Weitere
M0     Sicherheitsnetz (Inventar, Golden Master, Lint)      ← blockierend für M1–M6
D4     Doku-Fäulnis (README-Versionen, Stempel, Archiv)
G2     Display-Pfad im Fahrzeug bestätigen + B8 klären      ← braucht Fahrzeug
G1     BMW-Browsing-Probe                                   ← braucht Fahrzeug, blockiert das andere Repo
M5     Ergonomie messen (Vorher-Stand einchecken)
M1     UIDs + export_tree
M2     Kopflose API (goto/activate/rebuild, skip_on_nav)
M3     Rebuild-Robustheit (B1/B2/B4)
M6     iDrive-Simulation + Testskripte
M4     Baum-Ergonomie verbessern (nach M5-Zahlen)
G4     Nahtstellen für PDAP vorbereiten
G3     Handy/Tablet als A2DP-Sink
D5     Rückfall-Regeln in docs/README.md verankern          ← mit D3 beginnen, hier abschließen
D6     Skripte aufräumen                                    ← optional, eigenes Paket, eigener Feldtest
```

D1–D3 stehen bewusst vor M0: `FEATURES.md` und die Golden-Master-Dateien brauchen ohnehin
einen Platz, und ein reiner `git mv`-Commit lässt sich später nicht mehr sauber von
inhaltlichen Änderungen trennen.

G1 und G2 lassen sich in **einer** Fahrzeugsitzung erledigen — beide brauchen nur eine
verbundene BMW-Strecke und ein Mitschnitt-Fenster. Wenn kein Termin absehbar ist, mit M0/M5
beginnen; beides braucht keine Hardware.

**Definition of Done für den Gesamtauftrag:**

1. Im Wurzelverzeichnis liegt kein Dokument mehr außer `README.md`; `docs/README.md` ist
   vollständiger Index; `tools/check_docs.sh` ist grün und in der Matrix verankert.
2. `docs/FEATURES.md` existiert, ist vollständig und jede Zeile hat eine CLI-Prüfung.
3. Regressionsmatrix R1–R5 und R8 läuft hardwarefrei und ist in `pidrivectl test all`
   eingebunden.
4. Der Menübaum ist UID-adressierbar, vollständig exportierbar und per CLI navigier- und
   auslösbar.
5. Die Menüposition übersteht einen Rebuild — nachgewiesen per Test.
6. `docs/menue/MENU-ERGONOMIE.md` zeigt Vorher-/Nachher-Zahlen.
7. `docs/fahrzeug/BMW-AVRCP-PROBE.md` und `docs/fahrzeug/BMW-DISPLAY-PROBE.md` liegen vor
   und sind im Gateway-Repo verlinkt.
8. `docs/KontextPiDrive.md` und `docs/architektur/ARCHITECTURE.md` sind nachgezogen;
   `RUNTIME_FLOWS.md` Abschnitt I beschreibt den neuen Menü-Datenfluss.
9. Die Pfad-Mapping-Tabelle (alt → neu) ist an das Gateway-Repo übergeben und dort
   eingearbeitet.
