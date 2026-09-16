# Auftrag — DAB-Audioweg: warum DAB im Fahrzeug stumm bleibt

**Stand:** 2026-09-16 · gegen `1a502fb` / v0.11.139
**Betrifft:** `pidrive/modules/radio/dab_play.py`, `install.sh`, `/etc/asound.conf`, `docs/KontextPiDrive.md`
**Zuständig:** diese Instanz hat den Befund erhoben; Umsetzung durch die PiDrive-Instanz
**Vorrang:** **vor** der ersten Fahrzeugmessung dokumentiert, Umsetzung danach

---

## 1. Warum das jetzt dringend ist

Mit dem Bluetooth-Fundament (v0.11.139) rückt die erste erfolgreiche Kopplung mit dem
Fahrzeug in Reichweite. Genau in diesem Moment wird ein Fehler sichtbar, der zu Hause
strukturell unsichtbar ist:

**DAB+ schreibt sein Audio fest verdrahtet auf die Klinkenbuchse und kann eine
A2DP-Senke grundsätzlich nicht erreichen.**

Der zu erwartende Ablauf im Auto: Kopplung gelingt (HB2), Webradio ist hörbar (HB4), du
wählst DAB — und der BMW bleibt still, während der Pi in die Klinke spielt. Ohne diesen
Befund liest sich das als Bluetooth-Fehler, ist aber ein Audiowegefehler.

Es ist dasselbe Muster wie beim Bluetooth-Stack selbst: entwickelt und geprüft gegen
Kopfhörer an der Klinke, wo alles einwandfrei läuft. Deshalb ist es in über hundert
Versionen nicht aufgefallen. **DAB ist die Hauptquelle für die Autofahrt** — das macht
diesen Punkt teurer als jeden anderen offenen Posten.

---

## 2. Befunde

### DA1 — `welle-cli` umgeht PipeWire vollständig `[BELEGT]`

`dab_play.py:363–369`:

```python
# v0.11.102: Direktes ALSA wie manuelles `sudo welle-cli` (ohne PA-Plugin).
# pidrive_core.service setzt PULSE_SERVER global — fuer welle-cli entfernen,
# sonst blockiert das PipeWire-ALSA-Plugin den Decode/PCM-Pfad.
_welle_env = dict(os.environ)
_welle_env.pop("PULSE_SERVER", None)
_welle_env.pop("PIPEWIRE_RUNTIME_DIR", None)
_welle_env.pop("PULSE_SINK", None)
```

`welle-cli` erhält damit keinen Zugang zum Audio-Server. Es öffnet die ALSA-Standardkarte
direkt. Eine Bluetooth-Senke existiert in ALSA nicht — sie ist ein PipeWire-Knoten. Der
Ton kann dort also nicht ankommen, unabhängig von jeder Einstellung in PiDrive.

### DA2 — DAB schreibt bei jedem Start eine systemweite Datei um `[BELEGT]`

`dab_play.py:371–390` prüft `/etc/asound.conf` und schreibt sie bei Abweichung neu:

```python
_asound_content = (
    "# PiDrive: ALSA Default auf Klinke\n"
    f"defaults.pcm.card {_hpcard}\n"
    f"defaults.ctl.card {_hpcard}\n"
    "defaults.pcm.device 0\n"
)
```

Zwei Probleme übereinander. Erstens zementiert das den Klinkenweg bei jedem Tastendruck.
Zweitens ist `/etc/asound.conf` **systemweit**: die Wiedergabe einer Quelle verändert die
ALSA-Vorgabe für jeden anderen Nutzer dieser Vorgabe. Eine Quelle darf die Systemkonfiguration
nicht als Nebenwirkung umschreiben.

`install.sh:667–678` legt dieselbe Datei beim Einrichten an. Die Logik ist also doppelt
vorhanden, an zwei Orten, mit derselben Festlegung auf die Klinke.

### DA3 — die Dokumentation behauptet das Gegenteil `[BELEGT]`

`docs/KontextPiDrive.md`:

```
Zeile 176: **welle-cli:** ALSA via PipeWire-ALSA-Plugin (PULSE_SERVER wird gesetzt).
Zeile 188: | DAB+ | `welle-cli` mit PULSE_SERVER | ALSA → PipeWire-Plugin → BT/Klinke |
```

Die Tabelle nennt ausdrücklich „BT/Klinke" als Ziel. Seit `adfc240` (v0.11.102,
18.06.2026) trifft das nicht mehr zu — die Dokumentation beschreibt den Zustand **vor**
diesem Commit. Wer die Unterlagen liest, hält den Bluetooth-Weg für vorhanden.

Das erklärt auch, warum diese Lücke in der Gateway-Planung
(`esp32.bt-gateway` · `PIDRIVE-INTEGRATION.md`, Befund P-F2) nur als Gateway-Thema geführt
wurde und nicht als akuter Fahrzeugfehler: die Tabelle sagte, im Fahrzeug funktioniere es.

### DA4 — DAB steht außerhalb der Audiopolitik `[BELEGT]`

`modules/audio.py` hat mit `decide_audio_route()` → `apply_audio_route()` →
`build_player_args()` eine zentrale Wegeentscheidung, die `get_mpv_args(settings, source)`
allen Quellen anbietet. Webradio nutzt sie, DAB nicht. Die Einstellung `audio_output` ist
für DAB damit wirkungslos — auch die künftige Einstellung `audio_output=gateway`.

### DA5 — der Suchlauf beweist, dass der bessere Weg vorhanden ist `[BELEGT]`

`dab_scan.py:142` startet `welle-cli` bereits **mit Webserver**:

```python
["welle-cli", "-c", ch, "-g", str(gain_idx), "-C", "1", "-w", str(SCAN_PORT)]
```

`SCAN_PORT` ist eine reguläre Einstellung (`dab_scan.py:73`, Vorgabe 7981). Der
Webserver-Modus läuft also seit Längerem im Produktivbetrieb auf genau dieser Hardware —
er ist nicht spekulativ, sondern erprobt. Die Wiedergabe nutzt dagegen den Tonausgabe-Modus
(`dab_play.py:353`):

```python
"welle-cli", "-F", "rtl_sdr", "-T", "-c", ch, "-g", _gain, "-p", name
```

---

## 3. Die Pendelgeschichte — bitte vor jeder Änderung lesen

Dieser Schalter wurde **zweimal umgelegt**. Aus den entfernten Kommentaren in `adfc240`:

| Version | Entscheidung | Begründung im Code |
|---------|--------------|--------------------|
| v0.10.55 (früh) | `PULSE_SERVER` **entfernen** | „PipeWire ALSA-Plugin fängt ALSA-Calls ab → falscher Sink → kein Ton" |
| v0.10.55 (spät) | `PULSE_SERVER` **behalten** | „PA System-Mode hält ALSA Card 1 exklusiv. Ohne PULSE_SERVER kann welle-cli die Hardware nicht öffnen → kein Ton" |
| v0.11.102 (heute) | `PULSE_SERVER` **entfernen** | „sonst blockiert das PipeWire-ALSA-Plugin den Decode/PCM-Pfad" |

Beide Begründungen behaupten dasselbe Symptom — kein Ton — aus entgegengesetzten
Ursachen. Sie können nicht gleichzeitig zutreffen; zwischen ihnen muss sich die
PipeWire-Konfiguration geändert haben (`install.sh` entfernt heute
`10-no-reserve-pidrive.conf` und setzt `seat_monitoring=false`).

**Die Lehre daraus ist die wichtigste Aussage dieses Dokuments:** ein dritter Umschlag
desselben Schalters ist keine Lösung. Beide Versuche stellen dieselbe falsche Frage —
*wie bringe ich `welle-cli` dazu, mit ALSA zu sprechen?* Die tragfähige Frage ist:
*wie wird DAB-Audio ein PipeWire-Strom, den die vorhandene Wegeentscheidung behandeln
kann wie jede andere Quelle?*

Wer diesen Auftrag umsetzt und dabei nur `PULSE_SERVER` wieder hineinschreibt, hat das
Pendel zum dritten Mal bewegt und nichts gewonnen.

---

## 4. Zielbild

DAB soll die Form von Webradio bekommen: ein Strom, den `mpv` abspielt, mit
`get_mpv_args(settings, source="dab")`. Dann gilt für DAB automatisch alles, was für
Webradio heute schon gilt — Klinke, Bluetooth, später Gateway, Lautstärke, Metadaten über
die `mpv`-Schnittstelle, und ein Wechsel der Einstellung `audio_output` ohne Sonderfall.

```
heute:   rtl_sdr → welle-cli → ALSA(hw) → Klinke          [Bluetooth unerreichbar]

Ziel:    rtl_sdr → welle-cli -w PORT → HTTP → mpv → PipeWire → Klinke | BT | Gateway
```

`welle-cli` bleibt der Dekoder und behält den Direktzugriff auf den Stick. Nur die
**Tonausgabe** wandert aus `welle-cli` heraus zu `mpv` — dorthin, wo die Wegeentscheidung
schon greift.

### Konkrete Gestalt

```bash
# Dekoder (kein -C, kein -p — siehe DA-P2)
welle-cli -F rtl_sdr -T -O mp3 -c 11D -g <index> -w <dab_play_port>

# Wiedergabe: SID aus der Senderliste, nicht der Name
mpv <get_mpv_args(settings, source="dab")> http://127.0.0.1:<port>/mp3/0x1234
```

### Rückfallweg, falls der Webserver kein brauchbares Audio liefert

Virtuelle Loopback-Karte (`snd-aloop`): `welle-cli` macht weiter rohes ALSA — das
funktioniert erwiesen —, schreibt aber in `hw:Loopback,0`. PipeWire erfasst die
Gegenseite und stellt DAB als regulären Strom bereit. Kein Neukodieren, dafür ein
Kernelmodul und ein WirePlumber-Knoten.

Dieser Weg ist die Absicherung, nicht die erste Wahl: er hält die Pufferkette länger und
bringt eine zusätzliche Fehlerquelle beim Systemstart mit.

---

## 5. Was über das Protokoll bekannt ist

Quelle: Quellcode-Analyse von welle.io-master, erstellt 2026-04-21 für PiDrive v0.9.4
(`src/welle-cli/`, `src/input/rtl_sdr.cpp`, `src/backend/`, `src/various/channels.cpp`).
Das ist **keine Messung am installierten Stand** — die Fassung auf dem Pi kann abweichen.
DA-M1 bestätigt sie deshalb weiterhin, aber als kurze Kontrolle statt als Erkundung.

### DA-P1 — der Audio-Endpunkt existiert und ist ein echter Strom `[ANALYSE]`

| Endpunkt | Inhalt |
|----------|--------|
| `/mp3/<hex_sid>` | MP3-Strom, `audio/mpeg`, Verbindung bleibt offen, solange Audio anliegt |
| `/flac/<hex_sid>` | nur wenn mit `HAVE_FLAC` gebaut |
| `/mux.json` | vollständiger Ensemble- und Demodulatorzustand |

`-O` wählt den Codec, Vorgabe `mp3`, und MP3 ist laut Referenz **immer verfügbar** —
FLAC ist der bedingte Fall, nicht MP3. Damit ist die größte Unbekannte meines ersten
Entwurfs erledigt: der Strom wird voraussichtlich geliefert.

Intern registriert sich ein `ProgrammeSender` beim `WebProgrammeHandler` des Dienstes und
schreibt die dekodierten Rahmen direkt in die HTTP-Verbindung. `mpv` kann das unmittelbar
verbrauchen.

### DA-P2 — die Adressierung erfolgt über die SID, nicht den Namen `[ANALYSE]`

```json
"services": [ { "sid": "0x1234", "label": {"label": "Bayern 1"}, "url_mp3": "/mp3/0x1234" } ]
```

Das räumt eine Sorge aus meinem ersten Entwurf ab: **Dienstnamen mit Leerzeichen oder
Umlauten müssen nicht URL-kodiert werden**, weil der Name gar nicht in die Adresse
eingeht. `mux.json` liefert `services[].url_mp3` fertig.

Günstig für PiDrive: die Senderkennungen tragen die SID bereits (`dab_{sid}_{ch}`), die
Zuordnung ist also vorhanden und muss nicht erst gebaut werden.

### DA-P3 — `-C` ist ein Karussell und für die Wiedergabe falsch `[ANALYSE]`

`-C N` hält N Programme gleichzeitig aktiv und **wechselt standardmäßig alle zehn
Sekunden** (mit `-P`: erst nach DLS und Slide, höchstens 80 s). Das ist ein
Suchlauf-Verfahren, um Metadaten aller Dienste einzusammeln.

Für die Wiedergabe wäre es verheerend: der Ton würde alle zehn Sekunden den Sender
wechseln. **Die Wiedergabe läuft deshalb ohne `-C`** — dann dekodiert der Webserver für
die verbundenen Zuhörer.

Damit korrigiert sich auch meine Sorge um die Rechenlast aus dem ersten Entwurf: ich hatte
`-C 1` mit „dekodiert alle" verwechselt. Offen bleibt nur die Frage in DA-M2.

### DA-P4 — die Schalter der heutigen Wiedergabe sind unkritisch `[ANALYSE]`

| Schalter | Bedeutung | im Webmodus |
|----------|-----------|-------------|
| `-T` | TII-Dekodierung **aus**, spart Rechenzeit | beibehalten |
| `-F rtl_sdr` | Eingangstreiber ausdrücklich RTL-SDR statt `auto` | beibehalten |
| `-O mp3` | Codec für den Strom | ausdrücklich setzen |
| `-u` | Coarse Corrector **aus** | **nicht verwenden** — er gleicht den PPM-Fehler des Sticks aus (typisch 30–100 ppm) |

### DA-P5 — die Gain-Behandlung ist bereits richtig `[BELEGT]`

Die Referenz warnt: `-g` erwartet einen **Index** 0–28, keinen dB-Wert; `-g 40` ergibt
„Unknown gain count40" und damit 0 dB. `dab_helpers.py` `_get_dab_gain()` rechnet die
Einstellung `dab_gain` über `_RTL_GAIN_TABLE` in den nächstliegenden Index um, protokolliert
beides und gibt `-1` für die Software-AGC zurück.

**Hier ist nichts zu tun** — ausdrücklich festgehalten, damit niemand diese Umrechnung
später als Fehler „begradigt".

---

## 6. Was noch zu messen ist `[MESSEN]`

Alle Messungen **mit angeschlossener Antenne** und auf einem Kanal, der sicher einrastet.

### DA-M1 — Endpunkt am installierten Stand bestätigen

```bash
welle-cli --help 2>&1 | tee /tmp/welle_help.txt        # im Repo nirgends festgehalten
welle-cli -F rtl_sdr -T -O mp3 -c 11B -g 22 -w 7982 &
sleep 15
curl -s http://127.0.0.1:7982/mux.json | python3 -m json.tool | grep -E "url_mp3|\"sid\"|snr"
curl -s -o /tmp/dab_probe.mp3 -m 8 http://127.0.0.1:7982/mp3/0x<SID>
ls -l /tmp/dab_probe.mp3 && file /tmp/dab_probe.mp3
```

Bestanden, wenn die Datei wächst und `file` MP3-Audio meldet. Die `--help`-Ausgabe ins
Protokoll legen — sie fehlt im Repo und belegt, welche Fassung installiert ist.

### DA-M2 — Rechenlast ohne `-C`

Offen bleibt, ob der Webserver **ohne** `-C` nur für verbundene Zuhörer dekodiert oder
alle Dienste vorsorglich. Beim Ensemble mit zehn Diensten ist das der Unterschied zwischen
tragbar und untragbar.

```bash
# nur ein Zuhörer verbunden:
top -b -n 3 -d 2 | grep -E "welle-cli|mpv|Cpu"
vcgencmd measure_temp && vcgencmd get_throttled
```

Grenze: `welle-cli` plus `mpv` dauerhaft unter etwa 150 % (Pi 4, vier Kerne),
`get_throttled` bleibt `0x0`. Im Protokoll vom 16.09. lag `welle-cli` allein bei etwa 53 %.

Wird die Grenze gerissen, ist das der Fall für den Rückfallweg aus §4 — dort bleibt der
Dekodieraufwand wie heute.

### DA-M3 — Verzögerung und Senderwechsel

Zeit von „Sender gewählt" bis „Ton" messen, heute und nachher. Der Webweg puffert
zusätzlich. Radio darf verzögern; merklich träger als heute ist ein Nachteil, den der
Betreiber abwägen muss (E-DA1).

### DA-M4 — Anschlussvergabe

Die Referenz empfiehlt getrennte Anschlüsse: 7981 Suchlauf, 7979 Diagnose. PiDrive nutzt
7981 bereits für den Suchlauf (`dab_scan.py:73`). Die Wiedergabe braucht einen **dritten**
über eine neue Einstellung `dab_play_port`.

Wichtig: zwei `welle-cli` gleichzeitig scheitern ohnehin am Stick, nicht am Anschluss —
die Gerätereservierung muss also weiter greifen. Getrennte Anschlüsse verhindern nur, dass
ein übrig gebliebener Prozess den falschen Strom bedient.

---

## 7. Nebengewinne — nicht in diesem Auftrag, aber dadurch erreichbar

Läuft die Wiedergabe über den Webserver, steht `mux.json` im laufenden Betrieb zur
Verfügung, nicht mehr nur während des Suchlaufs. Drei bekannte Baustellen werden damit
leicht lösbar. **Sie gehören nicht in diesen Auftrag** — hier festgehalten, damit sie
beim Umbau nicht übersehen und nicht doppelt gebaut werden.

### Ehrlicher DAB-Zustand statt „unklar"

`demodulator.snr` und `demodulator.fic.numcrcerrors` erlauben die Unterscheidung, an der
die Testkette heute scheitert:

```
services=[]  fic-Fehler hoch  snr < 3     → kein Signal (Umgebung, nicht Fehler)
services=[]  fic-Fehler hoch  snr 3–8     → Signal vorhanden, Einrasten instabil
services=[]  fic-Fehler = 0   snr > 8     → Einrasten kurz vor Erfolg, mehr Zeit geben
services=N   ensemble != ''                → erfolgreich
```

Der Lauf vom 16.09. meldete „DAB Scan 11B: SNR=0, kein Signal" als Übersprung. Mit dieser
Unterscheidung wäre das ein klares „kein Signal, Antenne fehlt" statt eines unklaren
Ergebnisses. Betrifft `AUFTRAG-SPOTIFY-UND-TESTKETTE.md` (Testkette).

### DAB-Metadaten aus `mux.json` statt aus `stdout`

`services[].dls.label` liefert den Titeltext, `services[].mot.lastchange` den Zeitpunkt.
Heute wird `stdout` von `welle-cli` gelesen (`dab_play.py`, `STDOUT_FILE`). Der Weg über
`mux.json` ist strukturiert und übersteht Formatänderungen der Textausgabe.

### Das gewünschte Spektrum

`/spectrum` liefert 2048 komplexe float32-Werte, FFT-verschoben, 16.384 Byte je Anfrage —
also genau das Bild aus der welle.io-Diagnose, das den Wunsch nach einer Spektrumanzeige
ausgelöst hat. Dazu `/nullspectrum` (Senderkennung, mehrere Sender im Gleichwellennetz),
`/constellation` (QPSK-Güte: vier scharfe Häufungen = gut) und `/impulseresponse`
(Mehrwegeausbreitung, Senderentfernung).

Das betrifft `AUFTRAG-SPEKTRUM-UND-AVRCP.md`, Paket SA-E. Dort war der Endpunkt als
„nur für DAB-Kanäle" eingeordnet — das bleibt richtig, aber die Auswertung ist nun
dokumentiert:

```python
data = np.frombuffer(raw, dtype=np.float32).reshape(-1, 2)
iq = data[:, 0] + 1j * data[:, 1]
power_db = 20 * np.log10(np.abs(iq) + 1e-12)
```

Der allgemeine Spektrumweg über `rtl_sdr` (SA-A bis SA-D) bleibt davon unberührt und
weiterhin nötig — `welle-cli` kann nur Band III und Band L.

---

## 8. Arbeitspakete

### DA-A — Befund dokumentieren `[vor der Fahrt]`

`docs/KontextPiDrive.md:176` und `:188` berichtigen: DAB geht heute **direkt auf ALSA,
Klinke**, Bluetooth ist damit unerreichbar. In `TROUBLESHOOTING.md` einen Eintrag
„DAB im Fahrzeug stumm, Webradio hörbar" mit Verweis auf dieses Dokument.

Das ist das Einzige, was **vor** der Fahrt erledigt sein muss. Nicht damit der Fehler
behoben ist, sondern damit ein stummer BMW bei DAB nicht als Bluetooth-Fehler
fehlgedeutet wird.

### DA-B — Messreihe aus §5 durchführen und protokollieren

Ergebnisse nach `docs/ABNAHMEN.md`, Abschnitt „DAB-Audioweg". Ohne DA-M1 und DA-M2 wird
nicht umgebaut.

### DA-C — Wiedergabe über `mpv` umstellen

Nur wenn DA-M1 und DA-M2 bestanden sind.

1. `welle-cli -F rtl_sdr -T -O mp3 -c <ch> -g <index> -w <dab_play_port>` starten —
   **ohne `-C`** (DA-P3) und **ohne `-p`**, die Dienstwahl geschieht jetzt über die Adresse
2. auf Einrasten warten wie heute (die Zustandsüberwachung bleibt unverändert)
3. SID des Senders bestimmen: vorrangig aus `mux.json` `services[].url_mp3`, als
   Rückfall aus der Senderkennung `dab_{sid}_{ch}`. **Nicht über den Dienstnamen** (DA-P2)
4. `mpv` mit `get_mpv_args(settings, source="dab")` auf
   `http://127.0.0.1:<port>/mp3/0x<SID>` richten
5. das Entfernen von `PULSE_SERVER`, `PIPEWIRE_RUNTIME_DIR` und `PULSE_SINK` **entfällt** —
   `welle-cli` gibt keinen Ton mehr aus, die Umgebung ist gleichgültig
6. `commit_source("dab")` erst, wenn `mpv` tatsächlich spielt — nicht schon beim Start
   von `welle-cli` (dieselbe Falle wie TK-B beim Scanner)

Zu Schritt 3: liefert `mux.json` für den gewünschten Sender keinen Eintrag, ist das
Ensemble noch nicht vollständig eingerastet. Das ist ein Wartefall, kein Fehlerfall — die
heutige Logik wartet an dieser Stelle schon richtig.

Als Vorlage dient `modules/webradio.py`, besonders das Warten auf die Bluetooth-Senke
über `_audio.get_bt_sink()` (bis zu fünf Sekunden, während die Kopplung noch aufbaut).
Ohne dieses Warten startet DAB im Auto, bevor die Senke da ist.

### DA-D — `/etc/asound.conf` nicht mehr aus der Wiedergabe schreiben

Den Block `dab_play.py:371–390` entfernen. Die Datei gehört in die Einrichtung
(`install.sh`), nicht in einen Wiedergabepfad. Der Klinkenweg bleibt über die
Wegeentscheidung in `audio.py` erreichbar — dort ist er richtig aufgehoben.

Beim Aktualisieren eines bestehenden Systems steht in `/etc/asound.conf` weiterhin die
Festlegung auf die Klinke. Das ist für `mpv` unschädlich, weil `mpv` über PipeWire geht,
aber es sollte trotzdem geprüft werden — sonst ist die Ursache beim nächsten Rätsel
wieder unsichtbar.

### DA-E — DAB in die Audiopolitik aufnehmen

`decide_audio_route()` muss `source="dab"` kennen und gleich behandeln wie `webradio`.
Wenn dort Sonderfälle nötig sind, gehören sie **in** die Politik, nicht daneben.

### DA-F — Rückfallweg nur bei Bedarf

Scheitert DA-M1 oder DA-M2, dann `snd-aloop` nach §4. Eigenes Paket, eigene Abnahme,
nicht nebenher.

---

## 9. Hardware-Abnahme

| Stufe | Prüfung | Bestanden wenn |
|-------|---------|----------------|
| HD1 | Werkbank: DAB auf Klinke, wie bisher | Ton, Metadaten, Senderwechsel unverändert |
| HD2 | Werkbank: DAB auf Bluetooth-Kopfhörer (Sennheiser) | **Ton im Kopfhörer** — das ist der eigentliche Nachweis, und er braucht kein Fahrzeug |
| HD3 | `audio_output` zur Laufzeit umstellen, DAB läuft | Ton wechselt die Senke, kein Abbruch |
| HD4 | Rechenlast und Temperatur über zehn Minuten DAB | unter der Grenze aus DA-M2, `get_throttled` = `0x0` |
| HD5 | `pidrivectl test all` mit Antenne | nicht schlechter als der Lauf vom 16.09. |
| HD6 | Fahrzeug: DAB über A2DP | Ton im BMW, Metadaten im Display |

**HD2 ist die Schlüsselstufe** und sie ist an der Werkbank machbar. Der
Bluetooth-Kopfhörer aus `BluetoothError.md` ist derselbe A2DP-Fall wie der BMW. Damit
lässt sich dieser gesamte Auftrag abnehmen, **ohne** auf eine Fahrt zu warten — und
umgekehrt wäre es fahrlässig, HD6 zu versuchen, solange HD2 nicht steht.

---

## 10. Entscheidungen für den Betreiber

| Nr. | Frage | Empfehlung |
|-----|-------|------------|
| E-DA1 | Wenn der Webweg den Senderwechsel merklich träger macht (DA-M3): hinnehmen oder Rückfallweg `snd-aloop`? | Hinnehmen, solange unter etwa zwei Sekunden. Radio im Auto verzeiht das; ein Kernelmodul im Startpfad ist der teurere Handel |
| E-DA2 | Wenn `-C 1` zu viel Rechenzeit zieht und `-w` keinen Einzeldienst zulässt | Dann `snd-aloop` — dort bleibt der Dekodieraufwand wie heute |
| E-DA3 | Klinke bleibt der Vorgabeweg zu Hause? | Ja, über `audio_output` in den Einstellungen wie bei allen anderen Quellen — nicht über `asound.conf` |
| E-DA4 | Soll DA-C vor der Fahrt versucht werden? | **Nein.** Nur DA-A vorher. Die Fahrt klärt vier Entscheidungen und sollte nicht auf einem frischen Audioumbau stattfinden |

---

## 11. Was ausdrücklich nicht gemacht wird

- **Kein dritter Umschlag von `PULSE_SERVER`** — siehe §3
- `welle-cli` wird nicht ersetzt oder neu gebaut
- Die DAB-Zustandsüberwachung (Einrasten, PCM, DLS, Wiederherstellung) bleibt unberührt;
  sie liest `stderr` und `stdout` von `welle-cli` und ist vom Audioweg unabhängig
- Der Suchlauf wird nicht angefasst — er ist der Beleg dafür, dass der Webserver-Modus
  trägt, und soll genau so bleiben
- Keine Verbesserungen an der Tonqualität in diesem Auftrag; Ziel ist erst einmal
  **Ton auf der richtigen Senke**

---

## 12. Bezug zu bestehenden Dokumenten

| Dokument | Zusammenhang |
|----------|--------------|
| [AUFTRAG-BLUETOOTH-FUNDAMENT.md](AUFTRAG-BLUETOOTH-FUNDAMENT.md) | HB4 prüft Ton mit Webradio. **HB4 mit DAB würde heute scheitern** — dort als Hinweis vermerken |
| `esp32.bt-gateway` · `PIDRIVE-INTEGRATION.md` | Befund P-F2 ist derselbe Sachverhalt, dort nur als Gateway-Hindernis geführt. Dieser Auftrag erledigt zugleich die Gateway-Voraussetzung |
| [AUFTRAG-FUNKPFAD.md](AUFTRAG-FUNKPFAD.md) | Gerätereservierung am Stick — DA-M4 hängt daran |
| `docs/betrieb/BluetoothError.md` | Der dort beschriebene A2DP-Pfad gegen Kopfhörer ist die Messgrundlage für HD2 |
| `docs/KontextPiDrive.md` | Wird durch DA-A berichtigt |
| [../referenz/WELLE-CLI.md](../referenz/WELLE-CLI.md) | **Quelle für §5** — Kommandoreferenz, HTTP-Endpunkte, `mux.json`-Struktur, Gain-Index-Tabelle. Dort auch die Nebengewinne aus §7 im Detail |
| [AUFTRAG-SPEKTRUM-UND-AVRCP.md](AUFTRAG-SPEKTRUM-UND-AVRCP.md) | SA-E gewinnt durch §7 eine dokumentierte Auswertung des `/spectrum`-Formats |
| [AUFTRAG-SPOTIFY-UND-TESTKETTE.md](AUFTRAG-SPOTIFY-UND-TESTKETTE.md) | Der unklare DAB-Übersprung wird mit `mux.json` entscheidbar (§7) |

---

## 13. Fortschritt

| Datum | Stand |
|-------|-------|
| 2026-09-16 | Angelegt. DA1–DA5 belegt, Pendelgeschichte aus `adfc240` rekonstruiert, Messreihe und Pakete DA-A…DA-F festgelegt. Nichts davon umgesetzt. |
| 2026-09-16 | welle.io-Quellcodereferenz eingearbeitet (`../referenz/WELLE-CLI.md`). §5 neu als DA-P1…DA-P5: Audio-Endpunkt und MP3-Vorgabe geklärt, Adressierung über SID statt Name, **`-C` für die Wiedergabe als falsch erkannt**, `-T`/`-F` unkritisch, Gain-Umrechnung als bereits richtig bestätigt. Messreihe von fünf auf vier Punkte verkürzt. §7 Nebengewinne ergänzt. |
