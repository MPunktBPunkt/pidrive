> **Arbeitsauftrag — Bluetooth-Fundament: Kopplung, Sichtbarkeit, Spieler-Anmeldung**
> Stand: 2026-09-16 · Basis: v0.11.138 (`251742d`) · Befund-Präfix: **BT** · Pakete: **BF-A…BF-F**
>
> **Vorrang vor allen Menü- und Gateway-Paketen.** Begründung in §7.

---

## 0. Zweck

Der Betreiber hat klargestellt: **am BMW war noch nie ein PiDrive-Menü zu sehen.** Die
Kopplung scheiterte an einer Rückfrage des Fahrzeugs, die der Pi nicht beantworten konnte.
Zu Hause — WLAN, Ton über Klinke — funktioniert alles.

Diese Aussage ist durch den Quellstand vollständig erklärbar. Es sind **zwei voneinander
unabhängige Blocker**, und keiner liegt im Menü, in MPRIS-Inhalten oder in AVRCP-Logik:

1. **Die Kopplung kann nicht zustande kommen**, weil keine Instanz eine vom Fahrzeug
   ausgelöste Bestätigungsanfrage beantwortet.
2. **Selbst nach erfolgreicher Kopplung erschiene keine Anzeige**, weil der Spieler bei
   BlueZ nie angemeldet wird.

Beide sind nie aufgefallen, weil der Bluetooth-Stack gegen einen **Kopfhörer** entwickelt
wurde. Details in BT7.

**Dateibesitz.** Neu angelegt, keiner anderen Instanz zugeordnet. Berührt werden:

| Datei | Zustand | Konflikt |
|---|---|---|
| `pidrive/modules/bluetooth/bt_agent_dbus.py` | **neu, liegt bei** | nein |
| `systemd/pidrive_btagent.service` | **neu, liegt bei** | nein |
| `pidrive/modules/bluetooth/bt_agent.py` | wird stillgelegt (BF-E) | nein |
| `pidrive/main_core.py` | eine Zeile (BF-E) | Q-K/Q-M eingebaut — nur additiv |
| `pidrive/cli/cli.py` | `bt pair` umbauen (BF-C) | nein |
| `pidrive/mpris2.py` | Spieler-Anmeldung (BF-D) | Q-M eingebaut — nur additiv |
| `docs/fahrzeug/iDriveBt.md` | §7.1 und §8 richtigstellen (BF-F) | nein |
| `docs/betrieb/BluetoothError.md` | Geltungsbereich kennzeichnen (BF-F) | nein |
| `install.sh` | Dienst + Policy (BF-A/BF-B) | prüfen |

---

## 1. Gemessen gegen angenommen

Bevor die Befunde kommen, der Rahmen — denn er erklärt, warum sorgfältige Arbeit am
falschen Gegenstück vorbeilaufen konnte.

| Bereich | tatsächlich geprüft gegen | im Fahrzeug geprüft |
|---|---|---|
| A2DP-Audiopfad | Sennheiser HD 4.40BT (`BluetoothError.md`) | nein |
| Kopplung | Kopfhörer, „Just Works" | nein |
| AVRCP-Metadaten | — | nein |
| AVRCP-Tastenzuordnung | `pidrivectl avrcp inject` | nein |
| Menüergonomie | Tastendruckzählung im Modell (M5) | nein |
| Menüvorrang (Teil D) | Modultests | nein |

Die rechte Spalte ist durchgehend leer. Das ist der eigentliche Befund dieses Dokuments.

---

## 2. Befunde

### BT1 — keine Instanz beantwortet eine vom BMW ausgelöste Rückfrage `[BELEGT]`

Die einzige Stelle im Projekt, die auf `request confirmation` antwortet, ist
`bt_agent.py:257`. Sie steht **innerhalb** von `pair_with_agent()`. Diese Funktion wird
nur über die Kette `pidrivectl bt pair` → `bt_repair:` (`cli.py:843`) →
`td_hardware.py:215` → `bt_connect.py:150` erreicht, also **nur wenn der Pi das Pairing
beginnt**.

Die dauerhafte Agent-Sitzung setzt beim Start `agent DisplayYesNo` und `default-agent`
(`bt_agent.py:81–82`) und meldet sich damit bei BlueZ als zuständig. Aber:

- **Kein Leser-Thread.** `_AGENT_PROC.stdout` wird ausschließlich in
  `_drain_agent_stdout()` und `pair_with_agent()` gelesen. Sonst nirgends.
- **Kein D-Bus-Agent.** Suche nach `AgentManager1`, `RegisterAgent` und
  `org.bluez.Agent1` über das ganze Repository: **null Treffer**.

Beginnt also der BMW die Kopplung — was das dokumentierte Verfahren ist, siehe BT6 —
fragt BlueZ den registrierten Agenten, `bluetoothctl` schreibt die Frage in eine Pipe,
und **niemand liest sie**. BlueZ läuft in den Zeitablauf, die Kopplung scheitert.

**Das ist genau das beschriebene Symptom.** Der Kommentar in `bt_agent.py:80` weiß die
Ursache sogar: „Nötig für BMW Numeric Comparison (Request confirmation)".

### BT2 — der Pi-initiierte Weg blockiert an einer Eingabeaufforderung `[ANALYSE]`

`bt_agent.py:247` liest die Antwort mit:

```python
line = _AGENT_PROC.stdout.readline()
```

Die Bestätigungsabfrage von `bluetoothctl` ist eine **Eingabeaufforderung ohne
Zeilenumbruch**:

```
[agent] Confirm passkey 123456 (yes/no):
```

Auf so etwas blockiert `readline()`. Der Zweig mit dem `yes` (Zeile 257) wird nie
erreicht, nach `PAIR_TIMEOUT_SECONDS = 45` (`bt_helpers.py:48`) endet es im Zeitablauf.

**Der Autor kannte dieses Problem.** `_drain_agent_stdout()` wurde genau deswegen auf
`select.select()` umgestellt, mit dem Kommentar in `bt_agent.py:193–194`: „statt blindem
`readline()`, das bei stale stdout dauerhaft blockieren kann". Die Korrektur wurde nur
nicht auf die Schleife angewendet, auf die es ankommt.

Als `[ANALYSE]` eingeordnet und nicht als `[BELEGT]`, weil das genaue Ausgabeverhalten
von `bluetoothctl` bei **nicht-interaktiver Eingabe** (stdin ist hier eine Pipe) von der
BlueZ-Version abhängt. In einer Minute messbar, siehe HB0.

Für den Umbau ist es ohnehin gegenstandslos: BF-A ersetzt den Textkanal vollständig.

### BT3 — Sichtbarkeit läuft nach 180 Sekunden ab `[BELEGT]`

`bt_agent.py:86–87` setzt `discoverable on` und `pairable on` **einmal**, beim Start der
Agent-Sitzung. Eine Einstellung `DiscoverableTimeout` oder `PairableTimeout` findet sich
im ganzen Repository nicht — auch nicht in `install.sh`. Damit greift die BlueZ-Vorgabe
von 180 Sekunden.

Praktische Folge: der Pi ist drei Minuten nach Kernstart findbar, danach unsichtbar. Wer
im Fahrzeug erst das iDrive-Menü durchklickt, sucht nach einem Gerät, das längst nicht
mehr antwortet.

### BT4 — `pidrivectl` verwirft die eingesammelte Bluetooth-Antwort `[BELEGT]`

`pair_with_agent()` sammelt die letzten dreißig `bluetoothctl`-Zeilen und gibt sie als
zweiten Rückgabewert heraus; zusätzlich landen sie in
`/tmp/pidrive_bt_pairing_debug.json` (`PAIRING_BACKUP_FILE`).

`cli.py:838–861` nutzt davon nichts. Es schickt `bt_repair:` los und pollt danach nur den
Zustand über `svc.watch_bt_pair()`. Ausgegeben werden drei Möglichkeiten: `paired`,
`failed`, Zeitablauf. **Warum** es scheiterte, steht in einer Datei, von der man wissen
muss.

Damit deckt sich die Aussage des Betreibers, `pidrivectl` habe die Bluetooth-Antwort
nicht zurückgegeben, mit dem Code.

### BT5 — der Spieler wird bei BlueZ nie angemeldet `[BELEGT]`

`mpris2.py:266` nimmt den **Systembus** und veröffentlicht
`org.mpris.MediaPlayer2.pidrive`. `install.sh:360` installiert dazu nur eine
D-Bus-Richtlinie, die das Besitzen dieses Namens erlaubt.

Nirgends im Repository steht `org.bluez.Media1`, `RegisterPlayer` oder `mpris-proxy`.
`bluetoothd` sucht aber **nicht** selbständig nach MPRIS-Spielern auf dem Bus; ein
Spieler muss angemeldet werden. Ohne Anmeldung gibt es keine Antwort auf
`GetElementAttributes` — und damit **in keinem Fahrzeug** drei Textzeilen.

`iDriveBt.md` §7.1 behauptet „BlueZ liest diese Properties". Das ist falsch und die
Wurzel der Fehlannahme, auf der die gesamte Menüplanung ruht.

Zusätzlich meldet `mpris2.py:162` `HasTrackList: False` — PiDrive sagt jedem Leser
ausdrücklich, dass es keine Titelliste gibt.

### BT6 — die dokumentierte Anleitung beschreibt das Verfahren, das nicht funktionieren kann `[BELEGT]`

`iDriveBt.md` §8.1 „Ablauf BMW ↔ PiDrive":

```
1. BMW: Bluetooth Settings → Neues Gerät
2. BMW: sendet Inquiry / Page Scan
...
5. PIN/Passkey: normalerweise automatisch (Just Works)
```

§8.2 dazu: „BMW soll nun PiDrive finden und pairen".

Das ist der **BMW-initiierte** Weg, also genau der, für den nach BT1 keine Antwortinstanz
existiert. Und Schritt 5 behauptet „Just Works", während `bt_agent.py:80` bereits weiß,
dass der BMW Numeric Comparison verwendet.

Wer die Dokumentation befolgt, kann nicht koppeln.

### BT7 — der Stack wurde gegen einen Kopfhörer entwickelt `[BELEGT]`

`BluetoothError.md` ist das umfangreichste Bluetooth-Dokument des Projekts: rund 340
Zeilen, sechs benannte Fallstricke, Versionsverlauf v0.11.71 bis v0.11.122. Im Kopf steht:

> **Betroffene Hardware:** Cambridge Silicon Radio Bluetooth-Dongle,
> Sennheiser HD 4.40BT (`00:16:94:2E:85:DB`)

Jeder Prüfbefehl darin verwendet diese Adresse — auch der Soll-Zustand am Ende
(`bluetoothctl connect 00:16:94:2E:85:DB`).

Kopfhörer koppeln mit „Just Works", brauchen kein AVRCP-Target und keine Metadaten. BT1,
BT2 und BT5 **konnten dort nicht auffallen**. Die Arbeit war nicht falsch — der
Audiopfad ist dadurch belastbar —, aber sie deckt die Fahrzeugkopplung nicht ab.

Das erklärt vollständig, warum zu Hause alles läuft und im Auto nichts.

### BT8 — zwei Agenten würden sich um die Standardrolle streiten `[ANALYSE]`

BlueZ erlaubt mehrere registrierte Agenten; gefragt wird der über
`RequestDefaultAgent` bestimmte. Der Health-Thread aus `bt_agent.py:168` startet die
`bluetoothctl`-Sitzung bei Bedarf neu, und `start_agent_session()` schreibt dabei wieder
`default-agent`.

Läuft der neue D-Bus-Agent parallel, entscheidet der Zufall, wer die Rückfrage bekommt —
und die alte Sitzung beantwortet sie nicht. **BF-E ist damit keine Aufräumarbeit, sondern
Voraussetzung.**

---

## 3. Die zwei Blocker übereinander

```
BMW: "Neues Gerät"  ──►  findet den Pi?
                            │
        BT3: nach 180 s unsichtbar ──► nein, Ende
                            │ ja
                            ▼
                    BMW fragt: Passkey bestätigen?
                            │
        BT1: niemand liest die Frage ──► Zeitablauf, Ende
                            │ (mit BF-A: ja)
                            ▼
                    A2DP verbunden, Ton läuft
                            │
                            ▼
                    BMW fragt Metadaten ab
                            │
        BT5: kein Spieler angemeldet ──► keine drei Zeilen, kein Menü
                            │ (mit BF-D: ja)
                            ▼
                    drei Textzeilen im Display
                            │
                            ▼
                 erst hier beginnt alles, was bisher geplant wurde
```

Die letzte Zeile ist der Grund für den Vorrang. Menüvorrang, Autoplay, Ergonomie,
Suchlaufanzeige und die Gateway-Planung setzen **unterhalb** der beiden Blocker an.

---

## 4. Arbeitspakete

### BF-A — D-Bus-Agent (liegt bei, muss eingebaut werden)

Neu im Repo: `pidrive/modules/bluetooth/bt_agent_dbus.py` und
`systemd/pidrive_btagent.service`.

Der Agent implementiert `org.bluez.Agent1` vollständig, registriert sich über
`AgentManager1.RegisterAgent` mit Fähigkeit `DisplayYesNo` und beansprucht
`RequestDefaultAgent`. Damit arbeitet er **richtungsunabhängig**: ob der BMW oder der Pi
beginnt, ist ihm gleich. Er kennt keinen Textkanal und damit auch kein
Zeilenumbruchproblem.

Umgesetzte Methoden: `RequestConfirmation` (der Aufruf, an dem es bisher hing),
`RequestAuthorization`, `AuthorizeService`, `RequestPasskey`, `RequestPinCode`,
`DisplayPasskey`, `DisplayPinCode`, `Cancel`, `Release`.

Eigenschaften, die im Fahrzeug zählen:

| Eigenschaft | Wirkung |
|---|---|
| **Jede Anfrage wird protokolliert** | `/tmp/pidrive_bt_agent_events.json`, 200 Einträge, mit Methode, Gerät, Passkey, gegebener Antwort und **Begründung** |
| **`Trusted=True` nach dem Koppeln** | sonst fragt BlueZ bei jedem Verbinden erneut |
| **Zustandsdatei bleibt kompatibel** | gleiches Schema wie bisher, `cli.py:889` und `diagnose.py:573` funktionieren unverändert weiter |
| **Eigener Dienst** | überlebt Kern-Neustarts, läuft vor dem Kern, berührt die GLib-Schleife von `mpris2.py` nicht |
| **Bestätigungsregel** | `always` (Vorgabe) / `window` / `never`, umschaltbar über `PIDRIVE_BT_CONFIRM` |
| **`--selftest`** | prüft die Entscheidungslogik ohne BlueZ |

Zur Vorgabe `always`: sie entspricht dem Verhalten, das die alte Lösung anstrebte, und
kann beim ersten Kopplungsversuch **nicht aus Regelgründen** scheitern. Das ist
beabsichtigt — beim ersten Versuch im Fahrzeug soll nichts anderes schiefgehen können als
Bluetooth selbst. Die Härtung auf `window` steht in E-BT2.

Einbau in drei Schritten, jeder einzeln prüfbar:

```bash
cd ~/pidrive/pidrive

# 1. Entscheidungslogik ohne BlueZ
python3 modules/bluetooth/bt_agent_dbus.py --selftest

# 2. Von Hand im Vordergrund — nimmt BlueZ den Agenten an?
sudo systemctl stop pidrive_core          # alte bluetoothctl-Sitzung weg
sudo python3 modules/bluetooth/bt_agent_dbus.py -f
#    Erwartet: "Agent registriert: /org/pidrive/btagent capability=DisplayYesNo"
#    und "Adapter hci0: alias='PiDrive' discoverable=on pairable=on timeout=0"

# 3. Erst danach als Dienst
sudo cp systemd/pidrive_btagent.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now pidrive_btagent
```

Schritt 2 ist der eigentliche Nachweis und kostet nichts — kein Commit, keine
Installation. Schlägt schon `RegisterAgent` fehl, liegt es an der D-Bus-Richtlinie und
nicht am Fahrzeug.

**Start als Skriptpfad, nicht mit `-m`.** `modules/bluetooth/__init__.py:9` zieht über
`from modules.bluetooth.bluetooth import *` das gesamte Subsystem herein und braucht die
Importumgebung des Kerns. `bt_agent_dbus.py` ist bewusst ohne Projektimporte gebaut, damit
der Dienst vor dem Kern starten kann — `-m` würde diesen Vorteil zunichte machen.

`install.sh` entsprechend ergänzen. Den Pfad in `WorkingDirectory` prüfen: die Unit nennt
`/home/pidrive/pidrive/pidrive`, `pidrive-wifi-recover.service:12` dagegen
`/home/pi/pidrive`. **Beide auf denselben Wert begradigen** — einer von beiden ist falsch.

### BF-B — Sichtbarkeit dauerhaft

Der Agent setzt beim Start über `org.bluez.Adapter1` bereits `DiscoverableTimeout=0`,
`PairableTimeout=0`, `Discoverable=True`, `Pairable=True` und `Alias`.

Zusätzlich in `/etc/bluetooth/main.conf` verankern, damit es auch ohne laufenden Agenten
gilt:

```ini
[General]
DiscoverableTimeout = 0
PairableTimeout = 0
Name = PiDrive

[Policy]
AutoEnable = true
```

`install.sh` soll diese Werte setzen, ohne die Datei blind zu überschreiben.

**Entscheidung nötig:** dauerhaft findbar ist bequem und im Fahrzeug richtig, im Wohnhaus
aber eine offene Tür. Siehe E-BT2.

### BF-C — die CLI muss die Bluetooth-Antwort zeigen

`pidrivectl bt pair` gibt heute drei Ergebniswörter aus (BT4). Neu:

```
$ pidrivectl bt pair BMW
Pairing mit BMW (xx:xx:xx:xx:xx:xx)
Agent: D-Bus, Regel=always, sichtbar=dauerhaft
Warte auf Anfragen des Fahrzeugs …

  [ 2s] AuthorizeService      uuid=…110a  → ja         (Audiodienst)
  [ 3s] RequestConfirmation   passkey=418302  → ja     (Regel always)
        ↳ Zahl am iDrive vergleichen und dort bestätigen
  [ 5s] Paired                → —          (von BlueZ gemeldet)
  [ 5s] Trusted=true gesetzt
  [ 7s] Connected             connected=True

✓ Gekoppelt und verbunden
```

Quelle ist der Ringpuffer aus BF-A, gepollt wie `pidrivectl avrcp monitor` es schon tut
(`cli.py:1794`). Die Zeile mit dem Passkey ist die wichtigste: **der Betreiber muss die
Zahl am iDrive vergleichen können.** Bisher war sie unsichtbar.

Dazu zwei neue Unterbefehle:

| Befehl | Wirkung |
|---|---|
| `pidrivectl bt agent` | Zustand und die letzten Anfragen, auch ohne laufendes Pairing |
| `pidrivectl bt pair-window <s>` | Pairing-Fenster öffnen (für Regel `window`) |

Und `pidrivectl bt pair` soll **ohne Adresse** funktionieren: einfach warten, was das
Fahrzeug fragt. Denn der normale Weg im Auto ist BMW-initiiert — eine Adresse hat man da
noch nicht.

### BF-D — den Spieler bei BlueZ anmelden

Der zweite Blocker (BT5). Nach der Kopplung ist das der Unterschied zwischen „Ton läuft"
und „das Display zeigt PiDrive".

**Wichtig: `mpris-proxy` ist hier das falsche Werkzeug.** Es sucht MPRIS-Spieler auf dem
**Sitzungsbus**, PiDrive veröffentlicht auf dem **Systembus** (`mpris2.py:266`). Es würde
nichts finden.

Der direkte Weg ist deswegen sogar einfacher: PiDrive sitzt schon auf demselben Bus wie
`bluetoothd` und kann sich selbst anmelden.

```python
# in mpris2.py, nach erfolgreicher BusName-Registrierung
def register_with_bluez(bus, adapter="hci0", object_path="/org/mpris/MediaPlayer2"):
    """
    BlueZ liest die MPRIS-Properties NICHT von selbst — der Spieler muss
    angemeldet werden. Danach beantwortet bluetoothd GetElementAttributes
    gegenüber dem Fahrzeug aus diesen Properties.
    """
    media = dbus.Interface(
        bus.get_object("org.bluez", f"/org/bluez/{adapter}"),
        "org.bluez.Media1")
    media.RegisterPlayer(object_path, dbus.Dictionary({}, signature="sv"))
```

Abmelden über `UnregisterPlayer` beim Beenden. Die Anmeldung muss **nach** dem
Verbindungsaufbau erneut versucht werden, wenn BlueZ sie verwirft.

Zu prüfen und im Abnahmeprotokoll festzuhalten, weil versionsabhängig:

- ob `RegisterPlayer` mit leerem Eigenschaftswörterbuch genügt oder ob BlueZ
  `PlaybackStatus` und `Identity` im Aufruf erwartet
- ob BlueZ die Eigenschaften anschließend über
  `org.freedesktop.DBus.Properties.GetAll("org.mpris.MediaPlayer2.Player")` vom
  angegebenen Pfad liest — dann ist keine weitere Schnittstelle nötig
- ob die D-Bus-Richtlinie erweitert werden muss (`send_interface="org.bluez.Media1"`)

**Diese Aussagen sind nicht belegt, sondern zu messen.** Der Nachweis ohne Fahrzeug:

```bash
busctl --system tree org.bluez | grep -i player
```

Erscheint nach dem Start ein Spielerobjekt, ist die Anmeldung angekommen.

`HasTrackList` bleibt zunächst `False`. Eine Titelliste gehört zu AVRCP Browsing und
damit hinter die Messung aus Phase −1 — nicht in dieses Paket.

### BF-E — die alte Agent-Sitzung stilllegen

Voraussetzung, nicht Nacharbeit (BT8).

- `main_core.py:577` `_start_bt_agent_early()` entfernen oder auf den neuen Dienst
  umstellen
- `main_core.py:770` `bluetooth.stop_agent_session()` entsprechend
- `bt_agent.py`: `start_agent_session`, `stop_agent_session`,
  `start_agent_health_thread`, `pair_with_agent`, `_drain_agent_stdout` stilllegen.
  **Nicht sofort löschen** — die Funktionen werden aus `bluetooth.py:31–36`,
  `__init__.py:12–15` und `bt_connect.py:19` reexportiert. Erst Aufrufer umstellen, dann
  entfernen, sonst bricht der Import.
- `bt_connect.py:150` `pair_with_agent(...)` durch „auf den Agenten warten" ersetzen:
  nach `Device1.Pair()` rufen und das Ergebnis am Ringpuffer ablesen

### BF-F — Dokumente richtigstellen

| Datei | Änderung |
|---|---|
| `docs/betrieb/BluetoothError.md` | Kasten an den Anfang: **gilt für A2DP gegen Kopfhörer, nicht für die Fahrzeugkopplung.** Der Inhalt bleibt unverändert gültig und wertvoll — nur der Geltungsbereich muss dranstehen |
| `docs/fahrzeug/iDriveBt.md` §7.1 | „BlueZ liest diese Properties" ist falsch. Anmeldung über `Media1.RegisterPlayer` beschreiben (BT5) |
| `docs/fahrzeug/iDriveBt.md` §8.1 Schritt 5 | „Just Works" ersetzen durch Numeric Comparison mit `RequestConfirmation` |
| `docs/fahrzeug/iDriveBt.md` §8.2 | Anleitung auf den neuen Ablauf umschreiben: Fenster öffnen, `pidrivectl bt pair` ohne Adresse, Zahl am iDrive vergleichen |
| `docs/ABNAHMEN.md` | Stufenprotokoll aus §5 aufnehmen |

---

## 5. Stufenabnahme — die Leiter

**Jede Stufe macht erst die nächste prüfbar.** Keine Stufe überspringen; ein Befund auf
Stufe 2 macht jede Messung auf Stufe 5 wertlos.

### HB0 — Werkbank, ohne Fahrzeug, vor dem Umbau

Belegt BT2 und schafft den Vergleichswert:

```bash
cd ~/pidrive/pidrive
python3 modules/bluetooth/bt_agent_dbus.py --selftest
pidrivectl bt status
cat /tmp/pidrive_bt_agent.json
btmgmt info | grep -i -E "discoverable|pairable"     # Sichtbarkeit jetzt?
sleep 200 && btmgmt info | grep -i discoverable      # nach 200 s noch?
```

Bestanden, wenn der Selbsttest besteht. **Erwartet wird, dass die Sichtbarkeit nach 200
Sekunden weg ist** — das belegt BT3.

### HB1 — der Pi steht in der Geräteliste des BMW

Nach BF-A und BF-B. Zündung an, iDrive → Bluetooth → neues Gerät.

Bestanden, wenn „PiDrive" in der Liste erscheint. **Auch nach zehn Minuten Wartezeit
erneut prüfen** — das ist der eigentliche Test von BT3.

Erscheint nichts, ist die nächste Frage die Geräteklasse: manche Headunits filtern nach
Class of Device. Dann `btmgmt info` und die Klasse protokollieren.

### HB2 — die Kopplung kommt zustande

Am Pi mitlesen:

```bash
pidrivectl bt pair          # ohne Adresse, wartet auf das Fahrzeug
```

Bestanden, wenn im Protokoll `RequestConfirmation` mit Passkey erscheint, **die Zahl mit
der Anzeige im iDrive übereinstimmt**, und danach `Paired` und `Trusted=true` kommen.

Das ist die Stufe, an der es bisher scheiterte. Sie ist die wichtigste des Dokuments.

### HB3 — die Verbindung hält und kommt nach der Zündung wieder

Zündung aus, fünf Minuten warten, Zündung an. Bestanden, wenn A2DP ohne Eingriff
zurückkommt. Prüfen, ob `bt_watcher.py` dabei hilft oder stört.

### HB4 — Ton kommt aus den Fahrzeuglautsprechern

Webradio starten. Bestanden, wenn Ton kommt **und** `pactl list sinks short` einen
`bluez_output.<MAC>.<N>` zeigt. Erwartet nach BT7 stabil, weil dieser Pfad der einzige
ist, der bereits geprüft wurde.

Nebenbei die Warnung aus der Architekturanalyse gegenprüfen: **DAB umgeht PipeWire und
geht direkt auf ALSA** (`dab_play.py:367`). DAB wird auf dieser Stufe also
wahrscheinlich **nicht** über Bluetooth laufen. Getrennt protokollieren, nicht als
Bluetooth-Fehler verbuchen.

### HB5 — drei Textzeilen erscheinen im Display

Nach BF-D. Bestanden, wenn Titel, Interpret und Album am iDrive stehen.

**Das wäre das erste Mal, dass PiDrive überhaupt etwas auf dem BMW-Display anzeigt.** Bis
hierher ist keine einzige Aussage der Menüplanung überprüfbar.

### HB6 — Tasten kommen an, und dann das Menü

Erst jetzt sinnvoll:

```bash
pidrivectl avrcp monitor
```

Am Drehsteller drehen. Bestanden, wenn Ereignisse mit Kontext und erzeugtem Trigger
erscheinen.

Danach — und **nur** danach — sind HA1 und HA2 aus
[AUFTRAG-SPEKTRUM-UND-AVRCP.md](AUFTRAG-SPEKTRUM-UND-AVRCP.md) und die Abnahme des
Menüvorrangs (HQ10–HQ13) durchführbar. Auf derselben Fahrt lohnt der
`btmon`-Mitschnitt für die Browsing-Frage: `tools/bmw_avrcp_probe.sh`.

---

## 6. Was ausdrücklich nicht gemacht wird

- **Kein `mpris-proxy`.** Falscher Bus, siehe BF-D.
- **Kein `org.mpris.MediaPlayer2.Playlists` oder `TrackList` auf Verdacht.** Eine
  Titelliste nützt nur, wenn der Browsing-Kanal überhaupt geöffnet wird; das ist der
  Gegenstand von Phase −1. Die Behauptung, BlueZ übersetze Playlists automatisch in
  AVRCP-Browsing, ist unbelegt — und solange BT5 gilt, liest die Eigenschaften niemand.
- **Kein Löschen von `bt_agent.py` im ersten Schritt.** Reexporte, siehe BF-E.
- **Kein Umbau des A2DP-Audiopfads.** Der ist nach BT7 der einzige geprüfte Teil.
  `bluez5.roles = [ a2dp_source ]` (`install.sh:690`) ist für Pi-als-Quelle richtig, für
  Kopfhörer **und** Fahrzeug.
- **Keine Änderung an `mpris2.py` außer der Anmeldung.** Q-K bis Q-N sind eingebaut; die
  Inhalte der drei Zeilen sind erst nach HB5 beurteilbar.
- **Keine neuen Menüfunktionen, bis HB5 bestanden ist.** Begründung in §7.

---

## 7. Folgen für die laufende Planung

Unangenehm, aber nötig: eine Reihe fertiger Pakete steht auf einem Fundament, das nie
beobachtet wurde.

| Paket | Stand | betroffen |
|---|---|---|
| Menüvorrang (Q-K…Q-N, v0.11.138) | eingebaut | **ja** — regelt, wann welche der drei Zeilen erscheint. Die Zeilen selbst gab es nie |
| Quellen-Autoplay (Q-A…Q-E) | eingebaut | ja — sinnvoll, aber die Ergonomie ist nur am Display beurteilbar |
| FM-Rasterschritte (Q-G…Q-J) | eingebaut | nein — behebt ein echtes Einfrieren, wirkt auch über CLI und WebUI |
| Suchlaufanzeige (Q-F) | gesperrt | ja — gesperrt war richtig, nur aus dem falschen Grund |
| Menüergonomie (M5) | gemessen | Messung bleibt gültig, ihre **Bedeutung** hängt an HB6 |
| Gateway-Planung A17/A18 | offen | ja — S3 setzt Browsing voraus, Browsing setzt eine Verbindung voraus |

**Nicht betroffen** und weiter voll sinnvoll: Funkpfad (K1–K5), Spektrum (SA-A…SA-F),
WebUI-Sanierung, Testkette, Zustandsmaschine, WLAN-Wiederherstellung. Das ist der
größere Teil der offenen Arbeit — im Haus nutzbar und vom Fahrzeug unabhängig.

Empfohlene Reihenfolge: **BF-A, BF-B, BF-E, BF-C** (Werkbank, ein Tag) → **HB1, HB2**
(eine Fahrt) → **BF-D** → **HB4, HB5, HB6 plus `btmon`** (eine Fahrt) → danach
Menüarbeit mit Anschauung statt Modell.

---

## 8. Entscheidungen für den Betreiber

| Nr. | Frage | Vorschlag |
|---|---|---|
| E-BT1 | Regel beim ersten Versuch: `always` oder `window`? | `always` — beim ersten Mal soll nichts außer Bluetooth scheitern können |
| E-BT2 | Danach dauerhaft `always` und dauerhaft sichtbar? | Nach bestandenem HB2 auf `window` härten. Dann kann sich fremd nichts mehr anmelden, und `pidrivectl bt pair-window 300` öffnet bei Bedarf |
| E-BT3 | Adapter-Alias: „PiDrive" oder etwas, das der BMW als Audiogerät einsortiert? | „PiDrive" beginnen. Falls HB1 scheitert, ist die Geräteklasse der nächste Verdacht, nicht der Name |
| E-BT4 | `bt_agent.py` nach BF-E löschen oder als Rückfallebene behalten? | zwei Fahrten behalten, dann löschen |
| E-BT5 | Soll DAB auf HB4 mitgeprüft werden, obwohl der ALSA-Umweg bekannt ist? | ja, aber als eigener Punkt — es ist die erste echte Messung dieses bekannten Problems |
| E-BT6 | Soll die andere Instanz BF-A einbauen, oder willst du den Dienst zuerst von Hand starten? | von Hand starten. Schritt 2 aus BF-A zeigt in zehn Sekunden, ob BlueZ den Agenten annimmt — ohne Installation, ohne Commit |

---

## 9. Bezug zu bestehenden Dokumenten

| Dokument | Bezug |
|---|---|
| `docs/betrieb/BluetoothError.md` | Kopfhörerfall; Geltungsbereich fehlt (BT7, BF-F) |
| `docs/fahrzeug/iDriveBt.md` | §7.1 und §8 sind irreführend (BT5, BT6, BF-F) |
| [AUFTRAG-SPEKTRUM-UND-AVRCP.md](AUFTRAG-SPEKTRUM-UND-AVRCP.md) | AV1–AV8 bleiben gültig; HA1/HA2 setzen HB6 voraus |
| [AUFTRAG-QUELLENSTART-UND-SUCHLAUFANZEIGE.md](AUFTRAG-QUELLENSTART-UND-SUCHLAUFANZEIGE.md) | Teil D ist eingebaut, aber erst ab HB5 beurteilbar |
| [AUFTRAG-DISPLAY-RUECKMELDUNG.md](AUFTRAG-DISPLAY-RUECKMELDUNG.md) | D1/D2 setzen ein funktionierendes Display voraus — also HB5 |
| [AUFTRAG-FUNKPFAD.md](AUFTRAG-FUNKPFAD.md) | unabhängig, weiter uneingeschränkt sinnvoll |
| `tools/bmw_avrcp_probe.sh` | auf derselben Fahrt wie HB6 mitlaufen lassen |
| `esp32.bt-gateway` · `OFFENE-PUNKTE.md` | A17, A18, R19 und R28 hängen an HB2 und HB6. **Die dortige Annahme „NBT Evo" ist zu prüfen** — die Bedieneinheit hat fünf Tasten, was gegen NBT Evo Professional spricht |
