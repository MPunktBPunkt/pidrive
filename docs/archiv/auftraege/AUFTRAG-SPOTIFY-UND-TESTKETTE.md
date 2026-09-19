# AUFTRAG — Spotify-Integration und Testkette

**Dokumentstatus:** Auftrag V1.0 · 2026-09-15  
**Geprüfter Stand:** Repo `pidrive`, Commit `b555300`, v0.11.132  
**Messgrundlage:** `pidrivectl test all` am Pi `Pidrive`, 2026-09-15 18:57, Zweitstandort  
**Zuständigkeit:** zweite Cursor-Instanz

> **Dateihoheit.** Dieses Dokument ist neu angelegt, damit es nicht mit
> [AUFTRAG-WEBUI-SANIERUNG.md](AUFTRAG-WEBUI-SANIERUNG.md),
> [AUFTRAG-FUNKPFAD.md](AUFTRAG-FUNKPFAD.md) oder
> [AUFTRAG-DISPLAY-RUECKMELDUNG.md](AUFTRAG-DISPLAY-RUECKMELDUNG.md) kollidiert.
> Befunde hier bitte **hier** fortschreiben. `docs/ABNAHMEN.md` bleibt unberührt,
> bis die Abnahme tatsächlich stattgefunden hat.

---

## 0. Was die Messung hergibt — und was nicht

Der Lauf endete mit **26 bestanden, 1 Fehler, 30 Warnungen** in 115 s.

Zum Standort: der Pi stand an einem Ort, an dem die DAB-Antenne anders platziert ist.
**DAB-Empfang war physikalisch nicht möglich.** Alles, was aus dem DAB-Abschnitt kommt,
ist deshalb als Umgebungsbefund zu lesen und **nicht** als Softwarefehler:

- `DAB: unklar nach 51.1s  state=unknown`
- `ofdm-processor: SyncOnPhase failed`
- `DAB SCAN 11B: SNR 4.0 dB  FIC-Fehler 2328  Ensemble:` (der einzige `✗` des Laufs)

Die Software ist hier trotzdem auffällig — nicht weil sie kein Signal findet, sondern
**weil sie das nicht sagen kann**. Ein Suchlauf mit 4 dB SNR und 2328 FIC-Fehlern ist
kein „unklar", sondern ein eindeutiges „kein Signal". Dass der einzige Fehler des
Gesamttests eine Umgebungsbedingung ist, macht den Exit-Status des Tests unbrauchbar:
wer ihn automatisiert auswertet, bekommt an diesem Standort immer „rot".

Der wichtigste Befund des Laufs steht dagegen klein am Ende, in der Log-Auswertung:

```text
⚠ 18:57:53 [WARNING] Scanner: RTL-SDR belegt
⚠ 18:58:04 [WARNING] DAB: RTL-SDR belegt vor play DIE NEUE 107.7 [11B]
⚠ 18:58:04 [WARNING] CLI play_dab: Exception — kein commit 'Sender #22'
```

Diese drei Zeilen sind **eine** Ursachenkette, sie liegt in der Testkette selbst, und sie
erklärt zugleich, warum der Scanner-Test grün gemeldet hat, obwohl der Stick belegt war.
Das ist der Grund, warum die Testkette in dieser Anweisung **vor** allem anderen kommt:
Solange das Messinstrument lügt, ist jede weitere Messung wertlos.

---

## 1. Testkette — Befunde

### TK1 — Der Scanner-Test stoppt die falsche Quelle `[BELEGT]`

Der FM-Test stoppt korrekt mit `radio_stop` — `pidrive/test_suite.py` **L459–463**:

```python
    _write_trigger("stop")
    time.sleep(0.5)
    _write_trigger("radio_stop")  # laufende Quelle stoppen
    import time as _tfm; _tfm.sleep(1.5)
    _write_trigger(f"play_fm:{freq}")
```

Der Scanner-Test unmittelbar danach schickt aber `scanner_stop` — **L498–502**:

```python
    _write_trigger("stop")
    time.sleep(0.5)
    _write_trigger("scanner_stop")  # laufende Quelle stoppen
    import time as _tsc; _tsc.sleep(1.5)
    _write_trigger(f"scan_setfreq:fm:{freq}")
```

Zu diesem Zeitpunkt läuft nicht der Scanner, sondern **FM** aus dem vorigen Test.
`scanner_stop` beendet FM nicht, also bleibt `rtl_fm` am Stick. Und `rtl_fm` steht
genau im Suchmuster der Belegtprüfung — `pidrive/modules/radio/rtlsdr.py` **L119–121**:

```python
    r = _sh(r"ps ax -o pid=,cmd= | grep -E 'rtl_test|rtl_fm|welle-cli' "
            r"| grep -v grep || true", timeout=3)
```

Damit ist die Warnung um 18:57:53 vollständig erklärt.

### TK2 — Der DAB-Test räumt nur `welle-cli` weg `[BELEGT]`

`pidrive/test_suite.py` **L538–543**:

```python
    import subprocess as _sp3
    _sp3.run("pkill -f welle-cli 2>/dev/null", shell=True)
    time.sleep(0.5)
    _write_trigger("stop")
    time.sleep(0.5)
    _write_trigger(f"play_dab:{name}")
```

Vor dem DAB-Test lief der Scanner, also wieder `rtl_fm`. Das `pkill` trifft nur
`welle-cli`, und ein `scanner_stop` fehlt ganz. Daher „RTL-SDR belegt vor play"
um 18:58:04 — elf Sekunden nach der ersten Warnung, also dieselbe Kette.

### TK3 — Die Tests glauben `source_state`, nicht dem Gerät `[BELEGT]`

Der Scanner-Test hat `✓ Scanner FM 103.0: aktiv  7.5s` gemeldet, **während** das Log
„Scanner: RTL-SDR belegt" schrieb. Beides stimmt gleichzeitig, weil der Test nur den
Zustandsspiegel abfragt — `pidrive/test_suite.py` **L92–99**:

```python
def _wait_for_source(source_key, max_wait=15):
    """Wartet bis source_key aktiv ist (source_state.json, nicht status.json)."""
    ctx_map = {"webradio": "radio_web", "fm": "radio_fm", "dab": "radio_dab"}
    deadline = time.time() + max_wait
    while time.time() < deadline:
        cur = _current_source()
        if cur == source_key:
            return True
```

`source_state` ist ein Spiegel und keine Kontrollinstanz — dokumentiert in
[../architektur/ZUSTANDSMASCHINE.md](../../architektur/ZUSTANDSMASCHINE.md). Der Zustand
wird gesetzt, auch wenn die Geräteübernahme scheiterte. Ein Test, der ausschließlich
darauf schaut, kann einen belegten Stick nicht von erfolgreicher Wiedergabe unterscheiden.

Das ist die schwerwiegendste Eigenschaft des Laufs: **ein grünes Häkchen bedeutet hier
nicht, dass Ton floss.**

### TK4 — Der Spotify-Test kann nicht fehlschlagen `[BELEGT]`

`pidrive/test_suite.py` **L103–104**:

```python
        if source_key == "spotify" and s.get("spotify"):
            return True
```

`status.json["spotify"]` ist nichts anderes als „der Dienst läuft" (siehe SP1). Der Test
prüft damit genau das, was er vier Zeilen vorher schon per `systemctl is-active`
festgestellt hat. Das erklärt die gemeldeten **0,3 s**: `_wait_for_source` war beim
allerersten Durchlauf schon fertig, bevor der eigentliche Umschaltvorgang im
Hintergrund überhaupt gelaufen war.

`✓ Spotify Connect: aktiviert  0.3s` ist also eine Tautologie. Sie sagt nichts darüber
aus, ob PiDrive als Connect-Ziel erreichbar ist, ob eine Sitzung besteht oder ob Ton
fließt — und sie bleibt grün, selbst wenn der Hintergrund-Task den Dienst gerade
**abschaltet** (siehe SP2).

### TK5 — Eine Ausnahme wird zur Warnung verdünnt `[BELEGT]`

`CLI play_dab: Exception — kein commit 'Sender #22'` ist die einzige Spur eines
Programmfehlers, und sie enthält weder Ausnahmetyp noch Traceback. Der Gesamttest zählt
sie als eine von 30 Warnungen und läuft weiter.

### TK6 — Der DAB-Test wartet 50 s auf ein Urteil, das er nicht fällt `[BELEGT]`

`pidrive/test_suite.py` **L548–550**:

```python
    deadline = time.time() + 50
    dab_state = "unknown"
    while time.time() < deadline:
```

Bleibt es bei `unknown`, meldet der Test „unklar" — er unterscheidet nicht zwischen
„kein Empfang am Standort" und „Wiedergabe defekt". Der SNR-Wert, der diese
Unterscheidung trivial macht, liegt im DAB-Scan-Test daneben und wird nicht
herangezogen.

Nebenbefund im selben Test — **L528–534**:

```python
    stations_path = os.path.join(BASE_DIR, "..", "dab_stations.json")
    try:
        stations = _j.load(open(stations_path))
        sender = stations[sender_nr - 1] if len(stations) >= sender_nr else None
        name = sender.get("name","?") if sender else f"Sender #{sender_nr}"
    except Exception:
        name = f"Sender #{sender_nr}"
```

Die Senderliste wird über einen Relativpfad gesucht, und der Fehlerfall ist stumm. Dass
im Log der Name **`'Sender #22'`** auftaucht, zeigt, dass genau dieser Rückfall
gegriffen hat — der Test hat also `play_dab:Sender #22` mit einem Namen ausgelöst, den
es in der Senderliste nicht gibt. Dass in der Warnung eine Zeile vorher
`DIE NEUE 107.7 [11B]` steht, ist zu klären: beide Namen im selben Vorgang deuten auf
zwei verschiedene Auflösungswege hin.

---

## 2. Spotify — Befunde

Die Frage war, ob Spotify richtig eingebunden ist. Kurz: der Dienst läuft und die
Anmeldedaten liegen vor, aber **PiDrive weiß über Spotify praktisch nichts** — es
verwechselt durchgehend „der Daemon läuft" mit „Spotify spielt". Daraus folgen mehrere
Fehler, einer davon schaltet Spotify ab, wenn man es einschalten will.

### SP1 — „Spotify: aktiv" heißt nur „Dienst läuft" `[BELEGT]`

`pidrive/status.py` **L139–145**:

```python
        # Spotify (raspotify auf ARM, librespot auf x86)
        sp_active = False
        for _svc in ("raspotify", "librespot"):
            if _run(f"systemctl is-active {_svc} 2>/dev/null", timeout=2) == "active":
                sp_active = True
                break
        new["spotify"] = sp_active
```

`raspotify` startet beim Systemstart und läuft dauerhaft. Das Feld ist damit praktisch
immer `True` und trägt keine Information. Genau das zeigte die Konsole:

```text
Wiedergabe
  Quelle:       idle          ← nichts läuft
Verbindungen
  Spotify:      aktiv         ← Dienst läuft
```

Für den Fahrer liest sich „Spotify: aktiv" wie „Spotify spielt". Das Feld sollte
entweder „Dienst" heißen oder eine echte Sitzungsinformation tragen.

### SP2 — `spotify_on` kann Spotify **abschalten** `[BELEGT]` — schwerwiegend

Alle vier Kommandos landen in derselben Funktion, die ihren eigenen Namen nicht kennt —
`pidrive/trigger/td_hardware.py` **L23–25**:

```python
    if cmd in ("spotify_on", "spotify_off", "spotify_toggle", "play_spotify"):
        def _spotify_toggle():
            was_active = bool(S.get("spotify"))
```

`was_active` stammt aus dem Feld aus SP1, ist also im Normalbetrieb **immer** `True`.
Weitergegeben wird das an `pidrive/modules/update.py` **L323–336**:

```python
def spotify_toggle(S: dict) -> None:
    """Spotify Connect ein-/ausschalten via systemctl."""
    active = bool(S.get("spotify"))
    # ... wenn active:
        for svc in ("raspotify", "librespot"):
        S["spotify"] = False
        log.info("[UPDATE] Spotify: gestoppt")
```

Damit gilt: wer im Menü oder per CLI **„Spotify ein"** auslöst, stoppt bei laufendem
Dienst den Dienst — und `_spotify_toggle` setzt anschließend konsequent
`commit_source("idle")`. `spotify_on` ist also nicht idempotent, sondern kehrt die
Absicht um. Umgekehrt startet `spotify_off` Spotify, wenn der Dienst gerade steht.

Dass das im Test nicht auffiel, liegt an TK4: der Test meldete Erfolg, bevor der
Hintergrund-Task den Dienst beendet hatte.

### SP3 — `commit_source("spotify")` ohne jeden Nachweis eines Streams `[BELEGT]`

`pidrive/trigger/td_hardware.py` **L60–74**:

```python
                    if S.get("spotify"):
                        _sp_active2 = True
                    else:
                        try:
                            import subprocess as _ssp
                            for _ssvc in ("librespot", "raspotify"):
                                _sr = _ssp.run(["systemctl", "is-active", _ssvc],
                                               capture_output=True, text=True, timeout=2)
                                if _sr.stdout.strip() == "active":
                                    S["spotify"] = True; _sp_active2 = True; break
                            else: _sp_active2 = False
                        except Exception: _sp_active2 = False
                    if _sp_active2:
                        source_state.commit_source("spotify")
                        S["radio_playing"] = True
```

Die Schleife ist als „bis zu 8 s auf Spotify warten" gebaut, prüft aber nur den
Dienststatus — und der ist beim ersten Durchlauf schon erfüllt. PiDrive erklärt Spotify
damit zur aktiven Quelle, obwohl weder ein Endgerät verbunden noch ein Titel gestartet
ist. Am BMW erscheint dann „Spotify Connect" ohne Titel, und jede echte Quelle wird
verdrängt.

Der Code widerspricht dabei seinem eigenen Kommentar. Weiter oben in derselben Funktion
steht die richtige Absicht (**L52**):

```python
            S["radio_playing"] = False  # pending bis Spotify tatsächlich spielt
```

In L74 wird genau das wieder aufgehoben, ohne dass „tatsächlich spielt" je geprüft wurde.

### SP4 — Der Titel bleibt nach dem Stoppen für immer stehen `[BELEGT]`

Der Metadaten-Hook schreibt nur bei zwei Ereignissen — `install.sh` **L539–544**:

```bash
cat > /usr/local/bin/spotify_event.sh << 'EOF'
#!/bin/bash
if [ "$PLAYER_EVENT" = "track_changed" ] || [ "$PLAYER_EVENT" = "playing" ]; then
    echo "${PLAYER_EVENT}|${NAME}|${ARTISTS}|${ALBUM}" > /tmp/spotify_status
fi
EOF
```

`paused`, `stopped` und `session_disconnected` schreiben **nichts**. Die Datei behält
also den letzten Titel, bis `/tmp` beim Neustart geleert wird. Gelesen wird sie
unabhängig davon, ob gerade etwas läuft — `pidrive/status.py` **L149–155**:

```python
        if new["spotify"]:
            try:
                with open("/tmp/spotify_status") as f:
                    line = f.readline().strip()
                if "|" in line:
                    p = line.split("|")
                    new["spotify_track"]  = p[1][:40] if len(p) > 1 else ""
```

Zusammen mit SP1 („`spotify` ist immer True") heißt das: **hat einmal etwas gespielt,
meldet PiDrive diesen Titel dauerhaft als laufend** — auch Tage später, auch wenn das
Handy längst weg ist.

### SP5 — Das Ereignisfeld wird gelesen und weggeworfen `[BELEGT]`

`p[0]` ist `PLAYER_EVENT`, wird beim Zerlegen also mitgeholt, aber nie ausgewertet.
Genau dieses Feld würde SP4 lösen. Verstärkt wird das eine Ebene höher —
`pidrive/modules/playback_meta.py` **L63–69**:

```python
    if src == "spotify":
        return {
            "title": st.get("track") or st.get("spotify_track") or "",
            "artist": st.get("artist") or st.get("spotify_artist") or "",
            "dls": "",
            "playing": bool(st.get("spotify")),
        }
```

`playing` ist damit wieder der Dienststatus. Der zentrale Metadaten-Normalisierer, der
die BMW-Anzeige speist, kann „Spotify spielt" prinzipiell nicht von „raspotify läuft"
unterscheiden.

### SP6 — Spotify liegt außerhalb der Audio-Policy `[BELEGT]`

`pidrive/modules/audio.py` beschreibt Spotify in **L61** so:

```text
    Spotify     PipeWire-Pulse librespot --device pulse
```

Der Installer konfiguriert aber ALSA — `install.sh` **L858–867**:

```bash
    if grep -q "^LIBRESPOT_BACKEND" /etc/raspotify/conf; then
        sed -i 's|^LIBRESPOT_BACKEND=.*|LIBRESPOT_BACKEND=alsa|' /etc/raspotify/conf
    else
        echo 'LIBRESPOT_BACKEND=alsa' >> /etc/raspotify/conf
    fi
    if grep -q "^LIBRESPOT_DEVICE" /etc/raspotify/conf; then
        sed -i 's|^LIBRESPOT_DEVICE=.*|LIBRESPOT_DEVICE=default|' /etc/raspotify/conf
    else
        echo 'LIBRESPOT_DEVICE=default' >> /etc/raspotify/conf
    fi
```

Der Kommentar direkt darüber behauptet das Gegenteil („Spotify über zentralen
PulseAudio-Pfad"). Mit `BACKEND=alsa` und `DEVICE=default` öffnet librespot das
**ALSA**-Default-Gerät, nicht den PipeWire-Sink. Ob damit trotzdem PipeWire erreicht
wird, hängt allein daran, ob `/etc/asound.conf` `default` auf den Pulse-Plugin
umbiegt — das ist am Pi zu messen (H2).

Unabhängig davon kennt die Routing-Politik Spotify überhaupt nicht: in
`decide_audio_route()` (`audio.py` L510) gibt es keinen Spotify-Zweig, und
`_spotify_toggle` ruft `apply_audio_route()` nie auf. Ein Wechsel von
`audio_output=klinke` auf `bt` wirkt also auf Spotify nicht.

**Für das Gateway relevant:** damit ist Spotify der zweite Bypass neben DAB (P-F2 im
Gateway-Repo). Wer später `audio_output=gateway` einführt, bekommt bei Spotify
denselben stummen Pfad wie bei DAB.

### SP7 — Frischinstallation möglicherweise ohne Metadaten-Hook `[ANALYSE]`

`install.sh` behandelt `/etc/raspotify/conf` an **zwei** Stellen mit
unterschiedlichem Schlüsselsatz. Der Block ab **L846–854** setzt `LIBRESPOT_ONEVENT`,
greift aber nur, wenn die Datei **schon existiert**:

```bash
if [ -f /etc/raspotify/conf ]; then
    sed -i 's/^LIBRESPOT_DISABLE_CREDENTIAL_CACHE=/#LIBRESPOT_DISABLE_CREDENTIAL_CACHE=/' /etc/raspotify/conf
    if grep -q "LIBRESPOT_NAME" /etc/raspotify/conf; then
        sed -i 's/^LIBRESPOT_NAME=.*/LIBRESPOT_NAME="PiDrive"/' /etc/raspotify/conf
    else
        echo 'LIBRESPOT_NAME="PiDrive"' >> /etc/raspotify/conf
    fi
    grep -q "^LIBRESPOT_ONEVENT" /etc/raspotify/conf || \
        echo "LIBRESPOT_ONEVENT=/usr/local/bin/spotify_event.sh" >> /etc/raspotify/conf
```

Der Block ab **L884–890** legt die Datei an, wenn sie fehlt — **ohne** `ONEVENT`,
`BACKEND` und `DEVICE`:

```bash
    if [ ! -f /etc/raspotify/conf ]; then
        cat > /etc/raspotify/conf << 'RASPEOF'
LIBRESPOT_NAME="PiDrive"
LIBRESPOT_DEVICE_TYPE="automobile"
LIBRESPOT_SYSTEM_CACHE="/var/cache/librespot"
LIBRESPOT_DISABLE_DISCOVERY=true
RASPEOF
```

Daraus folgt die Vermutung: bei einer echten Erstinstallation entsteht eine Konfiguration
**ohne Metadaten-Hook**, und erst ein zweiter Installerlauf ergänzt ihn. Auf dem
Messpi ist der Hook womöglich nur deshalb vorhanden, weil der Installer mehrfach lief.
Diese Vermutung ist mit einem `grep` belegbar oder widerlegbar (H1) — bitte **messen,
nicht annehmen**, da die Verschachtelung der beiden Blöcke hier nur aus Fragmenten
gelesen wurde.

### SP8 — Discovery abgeschaltet, nur Cloud-Anmeldung `[ANALYSE]`

`LIBRESPOT_DISABLE_DISCOVERY=true` (L889) schaltet die lokale mDNS-Erkennung ab. PiDrive
erscheint dann nur über die bei Spotify hinterlegten Anmeldedaten in der App. Laufen
die ab oder wird ein anderes Konto benutzt, verschwindet PiDrive lautlos aus der
Geräteliste — ohne lokalen Rückfallweg und ohne Meldung. Das ist als Betriebsrisiko zu
vermerken; die Begründung im Kommentar (Avahi-Kollision mit dem Namen „PiDrive") ist
nachvollziehbar, aber ein abweichender `LIBRESPOT_NAME` wäre der mildere Weg.

---

## 3. Menü-Duplikate

Der Lint meldete sechs Doppel-IDs bei eindeutigen UIDs. Das sind **drei** Ursachen,
jede mit einem mitgezogenen Favoriten-Kind.

### MD1 — Webradio-Kennung wird auf 20 Zeichen gekürzt `[BELEGT]`

`pidrive/menu/menu_builder.py` **L179**:

```python
            _wid = f"web_{name.lower().replace(' ', '_')[:20]}"
```

`web_rock_antenne_heavy_m` ist genau diese Kürzung auf 20 Zeichen. Zwei Sender, deren
Namen sich erst ab dem 21. Zeichen unterscheiden, erhalten dieselbe ID. Dasselbe Muster
steckt zweimal weiter unten und ist dort genauso latent — **L320** und **L417**:

```python
            _sid = "lib_" + _sf["name"].replace(" ", "_")[:20]
...
                        id="wfn_" + _s.replace(" ", "_")[:16],
```

Bei WLAN-Netzen mit 16 Zeichen ist eine Kollision sogar wahrscheinlich.

### MD2 — DAB-Doppelungen sind ein Datenfehler `[BELEGT]`

`dab_0x1014` und `dab_0x1b2e` leiten sich aus der SID ab, werden also nicht gekürzt.
Zwei gleiche IDs bedeuten hier **zwei Einträge mit derselben SID** in
`dab_stations.json`. Das ist in den Daten zu bereinigen, nicht im Code — der Scanner
sollte beim Schreiben der Liste zusätzlich auf SID-Eindeutigkeit prüfen.

### MD3 — Golden Master ist um sechs Knoten veraltet `[BELEGT]`

`menu verify` meldet sechs Zugänge und keine Verluste:

```text
+ root/sources/scanner/{pmr446,freenet,lpd433,cb,vhf,uhf}/*_stop
```

Das sind die Stop-Knoten aus den Scanner-Paketen. Der Vergleichsstand wurde danach nicht
erneuert. Solange das so bleibt, tragen künftige Läufe diese sechs Zugänge als Rauschen
mit und echte Zugänge fallen weniger auf.

---

## 4. Kleinbefunde

| ID | Befund | Ort |
|----|--------|-----|
| KB1 | `read_json(/tmp/pidrive_list.json): Expecting value: line 1 column 1` — leere Datei wird wie defektes JSON behandelt und warnt bei jedem Selbsttest | `web/shared/files.py` bzw. `view_model.py` |
| KB2 | Einziger Sink ist `…mailbox.stereo-fallback` im Zustand `SUSPENDED`. Das Profil `stereo-fallback` deutet darauf hin, dass kein passendes Kartenprofil gewählt wurde | Audio-Abschnitt des Tests |
| KB3 | `AVRCP-Inject: 0 Events verarbeitet (erwartet ≥0)` — eine Erwartung, die immer erfüllt ist, prüft nichts | `test_suite.py` `test_avrcp_inject` |

---

## 5. Arbeitspakete

Die Reihenfolge ist bewusst gewählt: zuerst das Messinstrument, dann die Funktion.
Wer SP2 vor TK3/TK4 behebt, hat hinterher keinen Test, der die Behebung belegen kann.

### TK-A — Quellenwechsel in der Testkette zentralisieren

Ersetze die handgeschriebenen Stopp-Sequenzen in `test_fm`, `test_scanner_fm`,
`test_dab`, `test_webradio` und `test_spotify` durch **einen** Helfer, etwa
`_stop_all_sources()`, der `radio_stop`, `scanner_stop` und `webradio_stop` schickt,
anschließend `rtlsdr.wait_until_free(timeout=5.0)` abwartet und das Ergebnis
zurückgibt. Schlägt das Freiwerden fehl, muss der folgende Test mit **SKIP** und
klarer Begründung abbrechen, nicht mit PASS starten.

**DoD:** Ein `pidrivectl test all` am Pi zeigt in der Log-Auswertung **keine** Zeile
„RTL-SDR belegt" mehr. Läuft absichtlich vorher `rtl_fm` von Hand, meldet der nächste
Abschnitt SKIP mit Begründung.

### TK-B — Tests am Gerät prüfen, nicht am Zustandsspiegel

`_wait_for_source()` darf nicht allein aus `source_state.json` urteilen. Ergänze eine
zweite, unabhängige Bedingung je Quelle — für die RTL-Quellen ein passender Prozess aus
`find_rtl_processes()`, für Webradio/lokal ein laufender `mpv`, für Spotify siehe TK-C.
Fällt Spiegel und Gerätebefund auseinander, ist das ein **FAIL** mit beiden Werten im
Text, kein PASS.

**DoD:** Ein künstlich belegter Stick (`rtl_fm` von Hand gestartet) führt im
Scanner-Abschnitt zu FAIL, nicht zu `✓ aktiv`.

### TK-C — Spotify-Test aussagekräftig machen

Streiche die Abkürzung `if source_key == "spotify" and s.get("spotify")` aus
`_wait_for_source`. Der Spotify-Test soll drei unterscheidbare Ergebnisse liefern:
Dienst läuft, Anmeldung gültig, Sitzung aktiv mit Titel. Ohne verbundenes Endgerät ist
das korrekte Ergebnis **SKIP** („kein Connect-Client verbunden"), nicht PASS.

**DoD:** Bei gestopptem `raspotify` schlägt der Test fehl. Bei laufendem Dienst ohne
Client meldet er SKIP. Mit spielendem Handy meldet er PASS **mit** Titel.

### TK-D — Ausnahmen als Ausnahmen behandeln

`CLI play_dab: Exception` muss Ausnahmetyp und Traceback ins Log schreiben und im
Gesamttest als **FAIL** zählen. Zusätzlich: den Rückfall auf `f"Sender #{sender_nr}"`
in `test_dab` laut machen — fehlt `dab_stations.json`, ist das ein Aufbaufehler des
Tests und kein Sendername. Bitte dabei klären, woher im selben Vorgang der Name
`DIE NEUE 107.7 [11B]` stammt, obwohl der Test `Sender #22` geschickt hat.

**DoD:** Der Pfad zu `dab_stations.json` wird beim Testbeginn geprüft und bei Fehlen mit
klarer Meldung abgebrochen. Eine Ausnahme in `play_dab` erscheint mit Traceback.

### TK-E — Kein Empfang ist ein eigenes Ergebnis

Der DAB-Abschnitt soll bei niedrigem SNR früh und eindeutig abbrechen. Vorschlag:
Schwelle bei **SNR < 6 dB oder FIC-Fehler > 500** → Ergebnis `SKIP: kein DAB-Signal am
Standort`, mit SNR und FIC-Zahl im Text, und ohne die 50 Sekunden abzuwarten.

Das ist keine Kosmetik: es macht den Exit-Status des Gesamttests wieder brauchbar. Am
Zweitstandort muss ein vollständiger Lauf **0 Fehler** ergeben können.

**DoD:** Am Zweitstandort endet `pidrivectl test all` mit 0 Fehlern und einem klar als
SKIP markierten DAB-Abschnitt. Am Hauptstandort bleibt der DAB-Test unverändert
wirksam.

### SP-A — Ein Zustand, drei Bedeutungen trennen

Führe getrennte Felder ein und benenne sie so, dass sie nicht verwechselbar sind:

| Feld | Bedeutung | Quelle |
|------|-----------|--------|
| `spotify_service` | `raspotify`/`librespot` läuft | `systemctl is-active` |
| `spotify_session` | ein Connect-Client ist verbunden | letztes `PLAYER_EVENT` ≠ `stopped`/`session_disconnected` |
| `spotify_playing` | es läuft gerade ein Titel | letztes `PLAYER_EVENT` ∈ {`playing`, `track_changed`} |

`status.py` schreibt alle drei. Das alte Feld `spotify` bleibt als Alias auf
`spotify_service`, damit die WebUI nicht sofort bricht, und wird in einem zweiten
Schritt ersetzt. In der CLI heißt die Zeile künftig `Spotify-Dienst:` statt `Spotify:`.

**DoD:** Bei laufendem Dienst ohne Client zeigt `pidrivectl status`
`Spotify-Dienst: aktiv` und **keine** Angabe, die nach Wiedergabe klingt.

### SP-B — `spotify_on` und `spotify_off` trennen

`_spotify_toggle()` muss das auslösende Kommando auswerten, statt blind zu kippen.
`spotify_on` bei laufendem Dienst ist ein **No-Op mit Erfolgsmeldung**, `spotify_off`
bei stehendem Dienst ebenso. Nur `spotify_toggle` kippt. Dasselbe gilt für
`update.spotify_toggle(S)` — dort einen expliziten Zielzustand übergeben, etwa
`spotify_set(S, on=True)`.

**DoD:** `spotify_on` zweimal hintereinander lässt den Dienst laufen. `spotify_off`
zweimal hintereinander lässt ihn gestoppt. Im Log erscheint der Zielzustand.

### SP-C — Quelle erst nach Nachweis übernehmen

`commit_source("spotify")` erst, wenn `spotify_session` wahr ist — also ein
Connect-Client verbunden ist. Ohne Client bleibt die Quelle unverändert, und der
Benutzer bekommt über `ipc.write_progress()` die Meldung „Spotify bereit — in der App
PiDrive auswählen". Der Kommentar in L52 („pending bis Spotify tatsächlich spielt")
beschreibt dann wieder, was der Code tut.

**DoD:** `spotify_on` ohne verbundenes Handy führt **nicht** zu
`source_current=spotify`. Mit verbundenem Handy schon.

### SP-D — Metadaten mit Verfallsdatum

Erweitere `/usr/local/bin/spotify_event.sh` so, dass **jedes** Ereignis geschrieben wird,
inklusive `paused`, `stopped` und `session_disconnected`. `status.py` wertet dann `p[0]`
aus: bei Stop-Ereignissen werden `spotify_track`/`artist`/`album` geleert.

Zwei Dinge dabei beachten. Erstens ist die Hookdatei **Installationsartefakt**, nicht
Repo-Inhalt — die Änderung muss in `install.sh` und braucht einen Migrationspfad für
bestehende Installationen (der Installer ist idempotent, ein erneuter Lauf genügt, das
gehört aber nach `docs/betrieb/`). Zweitens sollte die Datei zusätzlich einen Zeitstempel
tragen, damit `status.py` sie nach einer Karenzzeit ohnehin als veraltet verwerfen kann.

**DoD:** Handy verbinden, Titel spielen, Wiedergabe stoppen, Handy trennen → in
`pidrivectl now` steht danach **kein** Titel mehr. Ein Neustart des Cores ändert daran
nichts.

### SP-E — Spotify in die Audio-Policy holen

`decide_audio_route()` erhält einen Spotify-Zweig, und `_spotify_toggle` ruft
`apply_audio_route()` auf. Danach ist zu entscheiden, ob librespot dauerhaft auf den
PipeWire-Pulse-Pfad gelegt wird (`LIBRESPOT_BACKEND=pulse`) — das wäre die Variante, die
Kommentar und Dokumentation ohnehin behaupten, und die Voraussetzung dafür, dass
`audio_output` auch für Spotify gilt.

Vorher ist H2 zu messen: liegt `default` per `/etc/asound.conf` schon auf Pulse, ist der
heutige Zustand nur schlecht dokumentiert. Liegt er direkt auf der Hardware, ist Spotify
ein echter Bypass wie DAB.

**DoD:** Ein Wechsel von `audio_output=klinke` auf `bt` bei laufender Spotify-Wiedergabe
verlagert den Ton, ohne librespot neu zu starten — oder es ist dokumentiert, warum das
nicht geht. Dokumentation in `audio.py` und `install.sh` stimmt anschließend mit dem
Code überein.

### SP-F — Installationsfehler klären

H1 messen. Zeigt sich, dass die Frischinstallation ohne `LIBRESPOT_ONEVENT` auskommt,
sind die beiden `conf`-Blöcke in `install.sh` zu **einem** zusammenzuführen, der
unabhängig von der Vorgeschichte denselben Schlüsselsatz garantiert.

**DoD:** `bash -n install.sh` läuft, und eine Neuinstallation in einem Container liefert
eine `conf` mit allen fünf Schlüsseln (`NAME`, `DEVICE_TYPE`, `SYSTEM_CACHE`,
`ONEVENT`, `BACKEND`/`DEVICE`).

### MD-A — Stabile IDs statt Kürzung

Ersetze die Kürzung in `menu_builder.py` L179, L320 und L417 durch einen Slug mit
angehängtem Kurz-Hash über den **vollen** Namen, etwa
`web_<slug20>_<sha1(name)[:6]>`. Damit bleiben IDs lesbar und trotzdem eindeutig.
Achtung: IDs wandern dadurch — der Golden Master muss im selben Schritt neu erzeugt
werden, und `menu verify` ist danach einmal mit Bedacht zu lesen.

**DoD:** `pidrivectl menu lint` meldet **0 Warnungen**. Zwei Testsender, deren Namen sich
erst ab Zeichen 21 unterscheiden, erhalten verschiedene IDs.

### MD-B — SID-Eindeutigkeit beim Schreiben der Senderliste

Beim Speichern von `dab_stations.json` auf doppelte SIDs prüfen und Duplikate verwerfen
(erster Eintrag gewinnt, Verwurf ins Log). Die bestehende Liste einmalig bereinigen.

**DoD:** `dab_0x1014` und `dab_0x1b2e` erscheinen im Lint nicht mehr.

### MD-C — Vergleichsstand erneuern

Nachdem MD-A und MD-B durch sind und die sechs Scanner-Stop-Knoten als gewollt bestätigt
sind: `pidrivectl menu snapshot` neu erzeugen und einchecken, mit Versionsangabe im
Commit.

**DoD:** `pidrivectl menu verify` meldet weder Verluste noch Zugänge.

### KB-A — Kleinbefunde

`read_json` unterscheidet „Datei fehlt", „Datei leer" und „Datei defekt"; nur der letzte
Fall warnt. `test_avrcp_inject` bekommt eine Erwartung, die scheitern kann, oder wird
ehrlich als INFO gekennzeichnet. KB2 nur untersuchen, wenn am Hauptstandort
tatsächlich Tonprobleme über Klinke auftreten — `SUSPENDED` allein ist bei
unbenutztem Sink normal.

---

## 6. Hardware-Verifikation

Zugang: `ssh pidrive@192.168.178.107` (Passwort `pidrive`; laut `docs/ABNAHMEN.md` ist
das der LAN-Host).

### H1 — Spotify-Konfiguration am Pi (zu SP7)

```bash
sudo cat /etc/raspotify/conf
grep -c LIBRESPOT_ONEVENT /etc/raspotify/conf
ls -l /usr/local/bin/spotify_event.sh
systemctl show raspotify -p Environment -p EnvironmentFiles
```

Erwartet: `LIBRESPOT_ONEVENT` genau einmal vorhanden, Hookdatei ausführbar. Fehlt der
Schlüssel, ist SP7 belegt.

### H2 — Läuft Spotify über PipeWire oder direkt auf ALSA? (zu SP6)

```bash
cat /etc/asound.conf 2>/dev/null
# Während Spotify spielt:
pactl list sink-inputs | grep -iE 'librespot|application.name'
sudo lsof -p "$(pgrep -f librespot | head -1)" 2>/dev/null | grep -E 'snd|pcm|pulse'
```

Erscheint librespot als `sink-input`, geht der Ton über PipeWire und SP6 ist nur ein
Dokumentationsfehler. Erscheint es stattdessen mit offenem `/dev/snd/pcm*`, ist es ein
echter Bypass.

### H3 — Metadaten-Verfall (zu SP4)

```bash
cat /tmp/spotify_status; stat -c '%y' /tmp/spotify_status
# Handy verbinden, Titel starten, dann Wiedergabe stoppen und Handy trennen:
sleep 20; cat /tmp/spotify_status
pidrivectl now
```

Steht nach dem Trennen noch der alte Titel in beiden Ausgaben, ist SP4 belegt.

### H4 — `spotify_on` ist nicht idempotent (zu SP2)

```bash
systemctl is-active raspotify          # erwartet: active
pidrivectl trigger spotify_on; sleep 6
systemctl is-active raspotify          # SP2 belegt, wenn hier "inactive" steht
pidrivectl source state
```

Bitte das Ergebnis wörtlich protokollieren — das ist der Befund, der die Umkehrung der
Absicht beweist.

### H5 — Gerätekonflikt reproduzieren (zu TK1/TK2/TK3)

```bash
pidrivectl trigger play_fm:104.4; sleep 5
pgrep -a rtl_fm
pidrivectl trigger scan_setfreq:fm:103.0; sleep 5
pgrep -a rtl_fm                        # läuft noch der FM-Prozess?
pidrivectl source state                # sagt der Spiegel trotzdem "scanner"?
grep 'RTL-SDR belegt' /var/log/pidrive/*.log | tail -5
```

Zeigt `source state` den Scanner, während `pgrep` noch den FM-Prozess listet, ist TK3
belegt.

### H6 — Gesamttest nach den Änderungen

```bash
pidrivectl test all 2>&1 | tee /tmp/test_after.txt
grep -cE 'RTL-SDR belegt' /var/log/pidrive/*.log
tail -5 /tmp/test_after.txt
```

Ziel am Zweitstandort: **0 Fehler**, DAB als SKIP, keine Belegt-Warnung.

Ergebnisse nach `docs/ABNAHMEN.md` — erst **nach** erfolgter Messung, und bitte diesen
Auftrag dabei referenzieren.

---

## 7. Eigentümerfragen

| # | Frage | Empfehlung |
|---|-------|------------|
| **QS1** | Soll `spotify_on` bei laufendem Dienst ein No-Op sein, oder soll es die Quelle auf Spotify umschalten, auch ohne verbundenes Handy? | **No-Op mit Hinweis.** Ohne Client gibt es nichts zu hören, und ein Umschalten würde eine laufende Quelle grundlos verdrängen. |
| **QS2** | Darf `LIBRESPOT_BACKEND` auf `pulse` gestellt werden? Das ist ein Eingriff in eine funktionierende Installation. | **Ja, aber erst nach H2.** Liegt `default` schon auf Pulse, genügt es, die Dokumentation zu korrigieren — der risikoärmere Weg. |
| **QS3** | Soll die lokale Spotify-Erkennung (`DISABLE_DISCOVERY`) wieder eingeschaltet werden, mit abweichendem `LIBRESPOT_NAME` zur Vermeidung der Avahi-Kollision? | **Zurückstellen.** Erst messen, wie oft PiDrive tatsächlich aus der App verschwindet. Ohne Beleg ist das eine Lösung für ein unbestätigtes Problem. |
| **QS4** | Ist die SNR-Schwelle für „kein DAB-Signal" bei 6 dB richtig angesetzt? | Vorschlag beibehalten und am Hauptstandort gegenmessen: dort muss ein normaler Empfang deutlich darüber liegen. Notfalls nachziehen. |

---

## 8. Was nicht zu tun ist

- **Keine Änderungen an `docs/ABNAHMEN.md`**, solange keine Messung stattgefunden hat.
  Befunde gehören in dieses Dokument, Abnahmen erst nach H1–H6.
- **`tools/bmw_avrcp_probe.sh` und `tools/bmw_avrcp_analyze.py` nicht anfassen.** Sie
  gehören zu Paket G1 und werden anderswo geführt. Hinweis: der Web-Upload hat das
  Ausführbar-Bit verloren, die Datei liegt als `100644` im Repo — ein
  `git update-index --chmod=+x tools/bmw_avrcp_probe.sh` ist die einzige gewünschte
  Änderung daran.
- **Die DAB-Empfangsfehler nicht „behoben" melden.** Sie sind am Zweitstandort
  physikalisch bedingt. Ziel ist, dass die Software das *erkennt* und benennt, nicht
  dass sie Empfang erfindet.
- **Kein Umbau der Zustandsmaschine im Rahmen dieses Auftrags.** TK-B prüft am Gerät
  *zusätzlich* zum Spiegel; die eigentliche Sanierung liegt in W7 und bleibt dort.
- **`spotify_toggle` nicht einfach löschen.** Das Kommando wird aus dem Menü und der
  WebUI heraus benutzt; es bleibt, bekommt aber mit SP-B eine klare Bedeutung.

---

## 9. Reihenfolge

```text
TK-A → TK-B → TK-C → TK-D → TK-E      (Messinstrument erst geradeziehen)
   ↓
H5, H6                                 (Gerätekonflikt belegen, Testkette abnehmen)
   ↓
SP-A → SP-B → SP-C → SP-D              (Spotify-Semantik und Steuerung)
   ↓
H1, H3, H4                             (Spotify am Fahrzeug-Pi belegen)
   ↓
H2 → SP-E → SP-F                       (Audio-Pfad, erst nach Messung)
   ↓
MD-A → MD-B → MD-C                     (Menü-IDs, dann Vergleichsstand neu)
   ↓
KB-A                                    (Kleinbefunde)
```

SP-E hat Fernwirkung: Spotify ist neben DAB der zweite Pfad, der die zentrale
Audio-Politik umgeht. Beide müssen angebunden sein, bevor `audio_output=gateway` im
Gateway-Projekt Sinn ergibt.

---

## 10. Fortschritt (diese Instanz)

| Datum | Stand |
|-------|--------|
| 2026-09-15 | Nutzer-Lauf am Pi `62aa12b` / v0.11.132: **22 bestanden, 2 Fehler, 29 Warnungen** — bestätigt TK1/TK2 (RTL-SDR belegt nach Scanner→DAB), TK-E (DAB Scan FAIL bei SNR~3), MPRIS2 ServiceUnknown, Spotify ohne Dienst. |
| 2026-09-15 | **TK-A…E umgesetzt** in `test_suite.py` (+ Traceback in `td_radio` play_dab): `_stop_all_sources`, Geräteprüfung in `_wait_for_source`, Spotify SKIP ohne Client/Dienst, DAB-Scan SKIP bei SNR&lt;6 oder FIC&gt;500, `dab_stations.json` Pflicht. Version **0.11.133**. SP-* noch offen. |
| 2026-09-15 | Pi @ **0.11.135**: nach Update kein „RTL-SDR belegt“ mehr im Suite-Log. Restprobleme: Core läuft als **root** → `welle-cli` orphan nach Boot-Resume nicht per User-`pkill` killbar; `radio_stop` kann in Transition hängen. Webradio/FM scheitern wenn Triggers nicht greifen. MPRIS2 ServiceUnknown separat. Nächster Hebel: zuverlässiges `dab.stop`/Resume-Sperre für Tests, nicht Core-Restart. |
| 2026-09-15 | **TK-B Nachweis am Pi:** `play web "Rock Antenne"` startet **mpv**, aber `source_current` bleibt `idle` (vorher `scanner`). Suite meldet korrekt FAIL — alter Test hätte am Spiegel ggf. auch gehangen. Ursache: fehlendes `commit_source("webradio")` nach Stop-Kette / Boot-Resume. Separat: Zombie-`rtl_fm` filtert `_rtl_processes` ab v0.11.137. |
| 2026-09-15 | **HW Abnahme** `fba2715`/v0.11.137: **21✓ 2✗ 2⊘** — Webradio+FM grün; DAB-Scan+Spotify SKIP; Scanner ✗ (Spiegel ohne rtl_fm, TK-B); MPRIS2 ✗. Details `docs/ABNAHMEN.md`. |

---

## 11. Nachtrag zum Stand v0.11.137

Grundlage: Nutzerlauf vom 2026-09-15 20:00:16 am Fahrzeug-Pi, dazu zwei WebUI-Ausgaben
(Spektrum-Snapshot, Audio-Debug-Cockpit) aus demselben Zeitfenster. Die Testkette TK-A…E
wirkt — dieser Nachtrag betrifft ausschließlich Befunde, die **nach** ihrer Umsetzung
sichtbar geworden sind.

### 11.1 Der Spektrum-Snapshot des Nutzers war korrekt „belegt"

Die 21 Fenster mit `"error": "RTL-SDR belegt"` sind in diesem Fall **kein Fehler**. Der
Zeitstempel der Aufnahme lautet `ts: 1789495306`, der Testlauf begann um 20:00:16
(= 1789495216). Die Aufnahme entstand also **90 Sekunden in den Testlauf hinein**, zwischen
Abschnitt WEBRADIO und FM RADIO. Zu diesem Zeitpunkt hielt `rtl_fm` aus dem FM-Test das
Gerät rechtmäßig.

Das ist für die Auswertung wichtig, weil dieselbe Meldung im Abnahmebefund
(`Spektrum-Snapshot … trotz Idle`) eine **andere** Ursache hat. Wer beide Fälle vermischt,
sucht den Fehler an der falschen Stelle. Gegenprobe vor jeder weiteren Snapshot-Messung:

```bash
pgrep -a 'rtl_fm|rtl_sdr|welle-cli' ; pidrivectl now
```

Die drei **echten** Befunde in derselben Ausgabe bleiben unverändert offen und sind bereits
im Funkpfad- bzw. WebUI-Auftrag geführt: `"mode": "fm_sweep"` statt Snapshot bei der
eingegebenen Mitte, `"ok": true` bei `"windows_ok": 0`, und die fehlende Darstellung
(`rf-tools.html` gibt ausschließlich `JSON.stringify` aus — ein Bild ist nie implementiert
worden, es fehlt also keine Funktion, sondern sie existiert nicht).

### 11.2 N1 — Der Zombie-Filter sitzt auf der Testseite statt im Modul  [BELEGT]

`test_suite.py` entfernt seit v0.11.137 Zombie-Prozesse aus der Belegtprüfung:

```python
# test_suite.py:104-111
    # Zombies zählen nicht als Belegung (TK-A Nachzug)
    live = []
    for p in procs:
        cmd = (p.get("cmd") or "")
        stat = (p.get("stat") or "")
        if "<defunct>" in cmd or stat.startswith("Z"):
            continue
        live.append(p)
```

Im Modul fehlt dieser Filter:

```python
# modules/radio/rtlsdr.py:118-128
def find_rtl_processes():
    """Laufende RTL-Prozesse (ps — kein Device-Zugriff)."""
    r = _sh(r"ps ax -o pid=,cmd= | grep -E 'rtl_test|rtl_fm|welle-cli' "
            r"| grep -v grep || true", timeout=3)
```

Zwei Folgen. Erstens läuft `is_busy()` (L281) über dasselbe ungefilterte
`find_rtl_processes()`; sein `reap_process()` erntet nur den **selbst registrierten**
Prozess, ein fremder oder verwaister `rtl_fm` zählt weiter als Belegung. Test und Produkt
widersprechen sich damit konstruktiv — genau die Diskrepanz, die in `ABNAHMEN.md` steht
(`RTL=[]` neben `Scanner: RTL-SDR belegt` im Log zur selben Sekunde).

Zweitens ist das Feld `stat` im Testfilter auf dem Normalpfad **immer leer**, weil
`find_rtl_processes()` nur `pid=,cmd=` abfragt. Es greift dort allein `"<defunct>" in cmd`.
Der `stat.startswith("Z")`-Zweig wirkt ausschließlich im `except`-Fallback (L96), der
`stat=` mitliefert. Das ist heute nicht falsch, aber es trägt nicht, sobald jemand den
Fallback entfernt.

### 11.3 N2 — Der Scanner gibt ohne Warten auf  [BELEGT]

```python
# modules/radio/scanner.py:409-413
            if _rtlsdr.is_busy():
                S["radio_type"]   = "SCANNER"
                S["source_error"] = "RTL-SDR belegt"
                log.warn("Scanner: RTL-SDR belegt")
                return
```

Eine einzige Abfrage, null Toleranz. Das Modul hält für genau diesen Fall bereits das
richtige Werkzeug bereit — `wait_until_free(timeout=2.5)` (L248-278) räumt in der Schleife
`reap_process()` ab und löst veraltete Locks auf. Der Suchlauf wurde in W5 auf dieses Muster
umgestellt, der Kanalwechsel nicht. Damit scheitert der Scanner an jedem Rennen direkt nach
einem Quellenwechsel, unabhängig von N1.

### 11.4 N3 — `commit_source` läuft auch dann, wenn der Scan ausgestiegen ist  [BELEGT]

Das ist die **eigentliche Ursache** des Abnahmebefunds `Spiegel=scanner Gerät=False (RTL=[])`
— und sie liegt nicht im Scanner, sondern im Aufrufer:

```python
# trigger/td_scanner.py:70-81
        def _scan_up(b=band):
            _stop_other_sources(S)
            if not source_state.begin_transition(f"scan_up:{b}", "scanner"):
                _blocked()
                return
            try:
                scanner.channel_up(b, S)
                S["scanner_band"] = b
                source_state.commit_source("scanner")
            finally:
                source_state.end_transition()
```

`scanner.channel_up()` kehrt beim Ausstieg aus 11.3 **normal** zurück; es wirft nichts. Der
Fehlschlag wird nur nach `S["source_error"]` geschrieben, und niemand liest das. Folglich
läuft `commit_source("scanner")` unbedingt. Der Spiegel meldet eine Quelle, die kein Gerät
hat.

Dieses Muster wiederholt sich in `td_scanner.py` **zehnmal** identisch: `_scan_up`,
`_scan_down`, `_scan_next`, `_scan_prev`, `_scan_jump_fn`, `_scan_step_fn`,
`_scan_setfreq_fn`, `_scan_setch_fn`, `_input_and_set` und der Bandstart. Eine Korrektur an
einer Stelle genügt nicht.

Zusammenhang mit dem Webradio-Befund aus §10: dort fehlt `commit_source` obwohl mpv läuft,
hier läuft `commit_source` obwohl nichts läuft. Beides ist dieselbe Wurzel — **der Spiegel
wird gesetzt, ohne das Ergebnis zu prüfen**, in beide Richtungen. Das ist Z-Klasse aus
`docs/architektur/ZUSTANDSMASCHINE.md`, nicht nur ein Scannerproblem.

### 11.5 N4 — MPRIS2 `ServiceUnknown` gehört nach vorn  [BELEGT]

Über beide Läufe unverändert: `ServiceUnknown: org.mpris.MediaPlayer2.pidrive`, der Watchdog
meldet das Verschwinden des Dienstes. Im Testlauf des Nutzers ist der Test-Push scheinbar
grün (`MPRIS2 GetAll: Metadaten lesbar`), der Fehler tritt also **später im Lauf** auf — der
Dienst verschwindet unter Last oder bei Quellenwechsel, nicht von Anfang an.

Bewertungsänderung gegenüber §9: dieser Punkt sollte **vor** allen SP-Paketen stehen. MPRIS2
ist der einzige Pfad, auf dem PiDrive das BMW-Display erreicht. Fällt er im Betrieb aus, ist
nicht eine Testzeile rot, sondern die Anzeige im Fahrzeug tot — und damit auch die
Grundannahme des Gateway-Projekts, dass Ausbaustufe S1 (Metadaten über AVRCP) überhaupt
trägt. Ein Zeitraffer-Nachweis ist nötig: wann genau verschwindet der Dienst, und korreliert
das mit einem Quellenwechsel?

### 11.6 N5 — Beobachtungen aus dem Audio-Debug-Cockpit  [ANALYSE]

Die Routing-Entscheidung im Cockpit trägt `"source": "boot_audio_base"` mit
`"ts": 1789494638` — etwa zehn Minuten **vor** dem Testlauf. Die Entscheidung wird also
einmal gefällt und bei Quellenwechseln nicht erneuert. Das ist derselbe Befund wie SP-E,
hier unabhängig von Spotify belegt.

Offen und messbedürftig: `"sink_inputs": []` bei gleichzeitig `SUSPENDED`-Sink. Falls dieser
Schnappschuss während der FM-Wiedergabe entstand, ginge **auch FM** nicht über PipeWire, und
neben DAB und Spotify gäbe es einen dritten Bypass. Aus den Daten ist das nicht
entscheidbar, weil das Cockpit keinen eigenen Zeitstempel mitliefert — nur die Entscheidung
hat einen. Siehe Messung H7.

Kleinbefund ohne Funktionsfehler: `"pulse_active": false` bei aktivem PipeWire-System-Mode
ist irreführend benannt. Das Feld prüft einen PulseAudio-Server, der unter PipeWire
korrekt fehlt, während `pipewire-pulse` die Anfragen bedient. Als Diagnosefeld in einem
Cockpit lädt das zu Fehlschlüssen ein.

### 11.7 Arbeitspakete

| ID | Paket | DoD |
|----|-------|-----|
| **N-A** | Zombie-Filter nach `rtlsdr.py` ziehen: `find_rtl_processes()` fragt `ps ax -o pid=,stat=,cmd=` ab und verwirft `stat` beginnend mit `Z` bzw. `<defunct>` im `cmd`. Filter in `test_suite.py:104-111` danach als reine Rückfallebene belassen. | `is_busy()` liefert `False`, während ein Zombie-`rtl_fm` in `ps` steht. Test und Modul stimmen im selben Moment überein. |
| **N-B** | `scanner.py:409` auf `wait_until_free()` umstellen, analog zum Suchlauf aus W5. Aufgeben erst nach Ablauf des Zeitfensters. | Kanalwechsel unmittelbar nach `radio_stop` gelingt; kein „belegt" mehr im Log bei freiem Gerät. |
| **N-C** | Ergebnisprüfung in `td_scanner.py`: die Scan-Funktionen geben Erfolg zurück (oder `S["source_error"]` wird ausgewertet), `commit_source("scanner")` läuft nur bei Erfolg, sonst `commit_source("idle")`. Alle **zehn** Blöcke. Gleiche Prüfung für die Webradio-Lücke aus §10 gegenprüfen. | Scanner-Test: Spiegel und Gerät stimmen überein — entweder `scanner` **mit** `rtl_fm`, oder `idle` **ohne**. Kein Zustand dazwischen. |
| **N-D** | MPRIS2-Verschwinden einkreisen: Dienstpräsenz im Sekundenraster gegen Quellenwechsel protokollieren, bis der Ausfallmoment reproduzierbar ist. Erst danach Ursachenfixierung. | Protokoll in `ABNAHMEN.md`, das den Ausfall einem Auslöser zuordnet. |

### 11.8 Messungen

| ID | Kommando | Prüft |
|----|----------|-------|
| **H7** | `pidrivectl play fm 104.4; sleep 5; date +%s; pactl list sink-inputs short; pgrep -a mpv` | N5 — geht FM über PipeWire? Leere Liste bei laufendem mpv = dritter Bypass. |
| **H8** | `pgrep -a rtl_fm; ps ax -o pid=,stat=,cmd= \| grep rtl_fm; python3 -c "import sys;sys.path.insert(0,'/home/pidrive/pidrive');from modules.radio import rtlsdr;print(rtlsdr.is_busy())"` | N1 — Zombie im `ps`, aber `is_busy()` soll nach N-A `False` sagen. |
| **H9** | `pidrivectl scan up pmr446; sleep 3; pidrivectl now; pgrep -a rtl_fm` | N3 — Spiegel gegen Gerät nach einem Kanalwechsel. |

### 11.9 Einordnung in die Reihenfolge

```text
N-D  (MPRIS2 — Displaypfad, vor allem anderen)
  ↓
N-A → N-B → N-C  +  H8, H9        (Gerätearbitrierung und Spiegel geradeziehen)
  ↓
SP-A … SP-D                        (Spotify-Semantik, unverändert)
  ↓
H7 → SP-E → SP-F                   (Audio-Pfad; H7 kann FM als dritten Bypass aufdecken)
  ↓
MD-A → MD-B → MD-C → KB-A          (Menü-IDs und Kleinbefunde, unverändert)
```

N-A bis N-C sind zusammen zu nehmen: einzeln behoben verschiebt sich der Fehler nur. Ohne
N-A widerspricht der Test weiter dem Produkt, ohne N-B scheitert der Scanner am Rennen, und
ohne N-C lügt der Spiegel in beiden Fällen weiter.

---

## 12. Nachtrag zum Stand `9db988b`

Grundlage: Pull vom 2026-09-16, fünf Commits — Offline-CI, WLAN-Wiederherstellung nach
Stromausfall, Menüarbeit. Der Stand hat sich substanziell verbessert; die Menü-Duplikate
MD1/MD2 sind an der Wurzel gelöst (Config-`id` bevorzugt, DAB kanalqualifiziert), und die
48 Unit-Tests sind das Sicherheitsnetz, das dem Projekt gefehlt hat. Dieser Nachtrag
behandelt ausschließlich, was dabei in die falsche Richtung läuft.

**Vorab:** MPRIS2 ist aus diesem Dokument herausgelöst und hat einen eigenen Auftrag —
[AUFTRAG-MPRIS2-STABILITAET.md](AUFTRAG-MPRIS2-STABILITAET.md). Grund: der Verdacht, dass
der Core während des Testlaufs abstürzt und damit mehrere der hier geführten Befunde
miterzeugt. Das ist vor allen Einzelfixes zu messen.

### 12.1 W1 — Die WLAN-Wiederherstellung läuft im Fahrzeug dauerhaft ins Leere  [BELEGT]

Das Skript selbst ist sauber gebaut, und der hartkodierte Pfad im Unit wird vom Installer
umgeschrieben (`install.sh:451`) — kein Fehler. Das Problem ist die Auslösebedingung.

```bash
# scripts/wifi-recover.sh:35-40
wlan_ok() {
    local ip ssid
    ip=$(wlan_ipv4)
    ssid=$(wlan_ssid)
    [ -n "$ip" ] && [ -n "$ssid" ]
}
```

Dazu ein Timer ohne jede Einschränkung — kein `Condition*`, keine Abbruchbedingung:

```ini
# systemd/pidrive-wifi-recover.timer:4-9
[Timer]
OnBootSec=3min
OnUnitActiveSec=5min
AccuracySec=30s
```

Zu Hause mit funktionierendem WLAN steigt das Skript nach zwei Zeilen aus (L50-53), dort
ist der Kommentar „Script exit 0 sofort, wenn WLAN ok" korrekt.

Laut Eigentümer ist im Fahrzeug aber **normalerweise kein WLAN verfügbar** — nur gelegentlich
ein Telefon-Hotspot, um Webradio zu nutzen; die Häufigkeit ist offen. Damit ist `wlan_ok`
den Großteil der Fahrzeit falsch, und die vollständige Prozedur läuft **alle fünf Minuten**:
Link ab und auf, `rfkill unblock all`, acht Sekunden warten, dann `modprobe -r brcmfmac`
samt Neuladen (L110-127), weitere acht Sekunden, schließlich `exit 1` mit Warnung ins
Journal. Ein Treiberzyklus alle fünf Minuten für ein Netz, das dort nicht existiert.

**Der Denkfehler ist die Unterscheidung.** Gefragt wird „habe ich eine SSID?", gemeint ist
aber „ist ein Netz da, mit dem ich mich verbinden könnte, und es klappt nicht?". Erst die
zweite Frage trennt Störung von Normalzustand:

| Lage | `wlan_ok` heute | Richtige Reaktion |
|------|-----------------|-------------------|
| Fahrzeug, kein Hotspot | falsch → volle Recovery | **nichts tun**, stiller `exit 0` |
| Fahrzeug, Hotspot an, verbunden | wahr → Ausstieg | nichts tun ✓ |
| Fahrzeug, Hotspot an, **nicht** assoziiert | falsch → volle Recovery | genau hier gehört sie hin ✓ |
| Zuhause nach Stromausfall, Router da | falsch → volle Recovery | genau hier gehört sie hin ✓ |

Die Unterscheidung ist messbar: ein bekanntes Netz muss im Scan sichtbar sein. Etwa über
`nmcli -t -f SSID dev wifi list` gegen `nmcli -t -f NAME connection show` beziehungsweise
`wpa_cli list_networks` gegen `wpa_cli scan_results`. Ist kein **konfiguriertes** Netz in
Reichweite, ist der Zustand normal und nicht zu reparieren.

### 12.2 W2 — `nmcli networking off` schaltet alles ab, nicht nur WLAN  [BELEGT]

```bash
# scripts/wifi-recover.sh:72-79
    # Falls Connect scheitert: kurzer Networking-Reset nur für WiFi
    if ! wlan_ok; then
        nmcli networking off 2>/dev/null || true
        sleep 2
        nmcli networking on 2>/dev/null || true
```

Der Kommentar behauptet „nur für WiFi", das Kommando ist global und nimmt `eth0` mit
herunter. Das ist besonders unglücklich, weil genau dieser Zweig den Stromausfall-Fall
bedienen soll — und in dem war LAN der einzige verbleibende Zugang. Wer per LAN eingeloggt
ist und die Wiederherstellung auslöst, verliert die Sitzung; über den Timer alle fünf
Minuten erneut. Richtig wäre `nmcli radio wifi off/on`, das bereits weiter oben (L69)
verwendet wird.

### 12.3 W3 — Eine Wiederherstellung darf den Stream nicht zerreißen, dem sie dient  [ANALYSE]

Der Hotspot wird laut Eigentümer für **Webradio** eingeschaltet. Reißt die Verbindung kurz
ab, würde `wlan_ok` falsch, und die Wiederherstellung greift zum Treiberneuladen. Das
garantiert einen längeren Ausfall als schlichtes Abwarten, denn `wpa_supplicant` und
NetworkManager reassoziieren von selbst innerhalb von Sekunden. Die Reparatur wäre dann
schädlicher als der Fehler.

PiDrive kennt seinen Zustand. Läuft eine netzabhängige Quelle — `source_current` gleich
`webradio` —, sollte die Wiederherstellung frühestens nach einer deutlich längeren Karenz
eingreifen und den Treiberzyklus gar nicht verwenden.

### 12.4 W4 — Kollision mit der Gateway-Strecke  [ANALYSE]

Die Verbindung zum künftigen `esp32.bt-gateway` läuft laut PDAP **über WLAN**. Eine
Automatik, die alle fünf Minuten „keine SSID, also Stack neu laden" entscheidet, muss mit
dieser Verbindung koexistieren können. Ob der Betrieb als Zugangspunkt betroffen wäre, ist
hier **nicht** behauptbar: `iwgetid -r` verhält sich im AP-Modus je nach Treiber
unterschiedlich. Zu klären ist es, bevor die Gateway-Strecke existiert — siehe Messung H10.

### 12.5 N-A wurde umgesetzt, aber auf der falschen Seite festgeschrieben  [BELEGT]

Der Befund aus §11.2 ist aufgegriffen worden — im Test statt im Modul. Der Filter ist jetzt
eine benannte Funktion `filter_live_rtl_procs` in `test_suite.py:91`/`:116`, abgesichert
durch drei Tests:

```python
# tests/unit/test_rtl_zombie.py:1-4
"""TK-A: Zombie-rtl_fm zählt nicht als Geräte-Belegung."""
from __future__ import annotations

from test_suite import filter_live_rtl_procs
```

In `modules/radio/rtlsdr.py` gibt es weiterhin **keinen** Zombie-Filter, und
`find_rtl_processes()` fragt unverändert nur `pid=,cmd=` ab. Benutzt wird die neue Funktion
ausschließlich innerhalb von `test_suite.py`.

Damit hat sich die Lage verschlechtert. Vorher war die Asymmetrie ein Versehen, jetzt ist
sie **spezifiziert**: der Test sagt „Gerät frei", das Produkt sagt „belegt", und drei grüne
Tests bestätigen, dass es so bleiben soll. Paket **N-A** bleibt offen und bekommt einen
Zusatz: nach der Verlagerung in `rtlsdr.py` muss `test_rtl_zombie.py` gegen die
Modulfunktion prüfen, nicht gegen die Testfunktion.

`pidrive/modules/radio/` und `pidrive/trigger/` sind seit `b2981b2` unverändert — **N-B und
N-C sind unangetastet.** Der Scanner gibt weiter ohne Warten auf, und
`commit_source("scanner")` läuft in allen zehn Blöcken weiter unbedingt.

### 12.6 V1 — Die Version steht seit fünf Commits still  [BELEGT]

`VERSION` und `pidrive/VERSION` stehen über CI-Einführung, WLAN-Wiederherstellung und
Menüumbau hinweg unverändert bei **0.11.137**. Es gibt einen Test dafür, aber er prüft die
falsche Eigenschaft:

```python
# tests/unit/test_version_and_scripts.py:1
"""VERSION-Dateien und install.sh müssen synchron sein."""
```

Synchronität zwischen den Dateien, nicht Fortschritt. Der Pi meldet vor und nach diesen
Änderungen dieselbe Version — damit ist der Auslieferungszustand wieder nicht feststellbar.
Das ist genau das Problem, das als H0 schon einmal eine vollständige Diagnoserunde gekostet
hat, weil `test_menu()` am Pi fehlte, obwohl die Versionszeichenkette passte.

### 12.7 MD4 — Die DAB-Kennungen haben sich geändert, eine Migration fehlt  [ANALYSE]

Die Korrektur aus `9db988b` ist richtig, hat aber eine Nebenwirkung:

```python
# pidrive/menu/menu_builder.py
+            _did = (s.get("id") or "").strip() or (
+                f"dab_{sid}_{ch.lower()}" if sid and ch else
```

Aus `dab_0x1014` wird `dab_0x1014_11b`. Alles, was alte Kennungen dauerhaft speichert —
Favoriten, gemerkte Einstellungen, abgelegte `goto:`-Ziele — löst nach dem Update nicht mehr
auf. Der Golden Master wurde neu erzeugt (3229 geänderte Zeilen in `tests/golden/menu_tree.json`),
für Nutzerdaten sehe ich keine Umstellung. Zu prüfen ist, ob Favoriten nach dem Update noch
auflösen, und falls nicht, ob eine einmalige Umschlüsselung oder ein Rückfall auf das alte
Namensschema nötig ist.

### 12.8 Kleinbefund

`tests/golden/CHANGES.md` enthält den Eintrag vom 2026-09-16 doppelt — einmal mit drei
Details, einmal leer. Kosmetisch, aber der Vergleichsstand ist das Dokument, an dem später
Verluste nachgewiesen werden; dort sollte nichts doppelt stehen.

### 12.9 Arbeitspakete

| ID | Paket | DoD |
|----|-------|-----|
| **W-A** | Vorbedingung in `wifi-recover.sh`: ist ein **konfiguriertes** Netz im Scan sichtbar? Wenn nein, stiller `exit 0` ohne Logwarnung und ohne Eingriff. Beide Stacks bedienen (NetworkManager und `wpa_cli`). Prüffall ist das Hotspot-Netz `pidrive`, das mit `scripts/wifi-add-network.sh` angelegt wird — Einrichtung siehe [TROUBLESHOOTING §9](../../betrieb/TROUBLESHOOTING.md). | Im Fahrzeug ohne Hotspot bleibt das Journal über eine Stunde frei von Recovery-Meldungen; kein `modprobe`-Zyklus. Mit eingeschaltetem Hotspot, aber getrennter Assoziation, greift die Recovery weiterhin. |
| **W-B** | `nmcli networking off/on` (L74-76) durch `nmcli radio wifi off/on` ersetzen. | Eine laufende SSH-Sitzung über `eth0` übersteht einen erzwungenen Recovery-Lauf. |
| **W-C** | Karenz für netzabhängige Quellen: bei `source_current == "webradio"` frühestens nach deutlich längerer Wartezeit eingreifen, Treiberzyklus dort ausschließen. Zusätzlich Ratenbegrenzung für `modprobe -r brcmfmac` — höchstens einmal je Startvorgang. | Ein kurzer Hotspot-Aussetzer während Webradio führt nicht zum Treiberneuladen; der Stream läuft nach Reassoziation weiter. |
| **W-D** | Timer entschärfen: nach mehreren erfolglosen Versuchen Abstand vergrößern statt starr alle fünf Minuten. | Journal zeigt wachsende Abstände statt Dauertakt. |
| **V-A** | CI-Regel: Änderungen unter `pidrive/` ohne Anhebung von `VERSION` machen den Lauf rot. `test_version_and_scripts.py` um diese Prüfung erweitern (Vergleich gegen den Basis-Commit). | Ein Commit, der Code ändert und die Version stehen lässt, scheitert in der Offline-CI. |
| **MD-D** | Auflösung alter DAB-Kennungen prüfen und, falls nötig, einmalige Umschlüsselung gespeicherter Favoriten. | Favoriten, die vor dem Update gesetzt wurden, wählen nach dem Update denselben Sender. |
| **KB-B** | Doppelten Eintrag in `tests/golden/CHANGES.md` zusammenführen. | Ein Eintrag je Datum und Version. |

### 12.10 Messungen

| ID | Kommando | Prüft |
|----|----------|-------|
| **H10** | Am Pi mit aktivem Hotspot: `iwgetid -r; nmcli -t -f SSID dev wifi list \| head; systemctl status pidrive-wifi-recover.timer` — dann Hotspot aus und nach 6 min `journalctl -u pidrive-wifi-recover -b --no-pager \| tail -30` | W1 — läuft die Recovery ohne Netz tatsächlich alle fünf Minuten durch, und wie weit kommt sie? |
| **H11** | `journalctl -u pidrive-wifi-recover -b \| grep -c 'Recovery starten'` nach einer Fahrt | W1 — Anzahl der Leerläufe im Betrieb, als Gegenprobe zur Schätzung. |
| **H12** | Favorit auf einen DAB-Sender setzen, Update einspielen, Favorit aufrufen | MD4 — lösen alte Kennungen noch auf? |

### 12.11 Geänderte Reihenfolge

```text
M-A                                (MPRIS2: messen, ob der Core abstürzt — eigener Auftrag)
  ↓
M-B → M-C → M-D → M-E → M-F        (nur falls M-A den Absturz belegt: zuerst hierher)
  ↓
W-A → W-B → W-C → W-D  +  H10      (WLAN, vor jeder Gateway-Arbeit)
  ↓
N-A → N-B → N-C  +  H8, H9         (Zombie-Asymmetrie und Scanner-Kette, zusammen)
  ↓
SP-A … SP-D                        (Spotify-Semantik)
  ↓
H7 → SP-E → SP-F                   (Audio-Pfad)
  ↓
MD-D, V-A, KB-A, KB-B              (Migration, CI-Regel, Kleinbefunde)
```

M-A steht vorn, weil es billig ist und die Bewertung mehrerer anderer Befunde verändern
kann. Träfe die Absturz-Hypothese zu, wären Teile von N-C und der §10-Webradio-Lücke
Symptombehandlung. Es wäre unwirtschaftlich, sie vorher einzeln zu reparieren.
