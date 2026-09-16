# Arbeitsauftrag — MPRIS2-Stabilität und die Folgen des Core-Absturzes

| | |
|---|---|
| Stand | v0.11.137 / `9db988b` |
| Angelegt | 2026-09-16 |
| Anlass | `ServiceUnknown: org.mpris.MediaPlayer2.pidrive` über zwei HW-Läufe unverändert |
| Gilt für | `pidrive/mpris2.py`, `pidrive/main_core.py`, `pidrive/test_suite.py` |
| Vorrang | **vor** SP-* und vor N-A…N-C aus `AUFTRAG-SPOTIFY-UND-TESTKETTE.md` §11 |

> **Dateieigentum:** dieses Dokument schreibt die Analyse-Instanz. Fortschritt bitte
> ausschließlich in §7 anhängen, damit es keine Konflikte gibt.

---

## 0. Warum das oben steht

MPRIS2 ist der einzige Pfad, auf dem PiDrive das BMW-Display erreicht. Fällt er aus, ist
nicht eine Testzeile rot, sondern die Anzeige im Fahrzeug tot — und damit auch die
Grundannahme des Gateway-Projekts, dass Ausbaustufe S1 (Metadaten über AVRCP) trägt.

Bisher wurde der Befund als isolierter D-Bus-Fehler behandelt. Die Analyse unten legt nahe,
dass er **Symptom eines Prozessabsturzes** ist, und dass dieser Absturz einen erheblichen
Teil der übrigen offenen Befunde miterklärt. Falls das zutrifft, ist hier nicht ein Fehler
zu beheben, sondern einer, der acht andere erzeugt.

---

## 1. Der Beweis liegt im eigenen Quelltext

Im Testcode steht seit längerem ein Workaround, der die Ursache benennt:

```python
# test_suite.py:655-658
def test_dab(sender_nr=22):
    """8. DAB+."""
    _section(f"DAB+ (Sender #{sender_nr})", "📻")
    # _send_to_bmw absichtlich NICHT aufgerufen — würde MPRIS2-Push triggern → SIGABRT
```

Ein MPRIS2-Push löst also ein **SIGABRT** aus. Das ist keine Vermutung, das hat jemand
gemessen und umgangen, indem der Push aus dem DAB-Test entfernt wurde. Behoben wurde nichts.

`SIGABRT` ist in diesem Zusammenhang aussagekräftig: Python wirft das nicht. Es kommt aus
`abort()` in einer C-Bibliothek — hier mit hoher Wahrscheinlichkeit aus einer
Assertion in `libdbus`. Und es ist aus Python **nicht abfangbar**: der gesamte
Core-Prozess stirbt, samt aller Threads.

---

## 2. M1 — Drei Threads auf einer D-Bus-Verbindung, ohne `threads_init()`  [BELEGT]

`dbus-python` ist nicht von sich aus threadsicher. Wer eine Verbindung aus mehreren Threads
benutzt, während eine GLib-Hauptschleife sie bedient, muss die Thread-Unterstützung
ausdrücklich einschalten. Im ganzen Modul gibt es kein `threads_init()` — weder
`dbus.mainloop.glib.threads_init()` noch `GLib.threads_init()`.

Der Aufbau sieht so aus:

```python
# mpris2.py:265-284
        try:
            bus = dbus.SystemBus()
        # ...
        _player = PiDrivePlayer(bus, _write_trigger)
        _loop   = GLib.MainLoop()

        t = threading.Thread(target=_loop.run, daemon=True, name="mpris2-glib")
        t.start()
```

Die Verbindung wird von Thread `mpris2-glib` bedient. Auf sie greifen aber noch zwei
weitere Threads zu:

| Thread | Zugriff | Stelle |
|--------|---------|--------|
| `mpris2-glib` | bedient die Verbindung (Dispatch) | `mpris2.py:283` |
| Core-Hauptschleife | `update()` → `update_metadata()` → `PropertiesChanged` | `mpris2.py:533`, gerufen aus `main_core.py` |
| Trigger-Verarbeitung | `push_test_metadata()` → `PropertiesChanged` direkt | `mpris2.py:401` |
| `mpris2-watchdog` | `dbus.service.BusName(SERVICE_NAME, bus)` auf derselben Verbindung | `mpris2.py:309` |

Das sind vier Zugriffspfade auf eine Verbindung ohne Thread-Initialisierung. Das ist das
Lehrbuchmuster für `libdbus`-Aborts.

**Die vorhandene Sperre schützt nicht davor.** `self._lock` (L66) wird in
`update_metadata()` gehalten, während das Python-Wörterbuch `self._metadata` gebaut wird
(L87-99). Sie schützt die Datenstruktur, nicht die Verbindung. Das Senden selbst liegt
außerhalb jeder Absicherung. Diese Sperre erzeugt den Eindruck von Sorgfalt an der
falschen Stelle — das ist der Grund, warum das Problem so lange unentdeckt blieb.

---

## 3. M2 — Der Watchdog kann den Fall nicht heilen, für den er gebaut ist  [BELEGT]

```python
# mpris2.py:300-316
                    if SERVICE_NAME not in r.stdout:
                        log.warn("MPRIS2 Watchdog: Service vom Bus verschwunden — Neustart")
                        try:
                            if _loop and _loop.is_running():
                                _loop.quit()
                        # ...
                        try:
                            new_name = dbus.service.BusName(SERVICE_NAME, bus)
                            _loop = GLib.MainLoop()
```

Zwei Lücken.

Erstens wird `bus` **nie neu erzeugt**, und `_player` auch nicht. Wiederhergestellt werden
nur die Hauptschleife und der Namensanspruch. Ist die Verbindung selbst gestorben — der
häufigste Grund, warum ein Name vom Bus verschwindet — dann schlägt
`dbus.service.BusName(SERVICE_NAME, bus)` auf der toten Verbindung fehl, der Watchdog
protokolliert alle 30 Sekunden „Neustart" und kommt nie wieder hoch.

Zweitens, und grundsätzlicher: gegen `SIGABRT` hilft er prinzipiell nicht. Der Watchdog
lebt im selben Prozess. Bricht der ab, ist der Watchdog mit weg. Er kann nur den Fall
behandeln, dass der Name verloren geht, während der Prozess weiterläuft — nicht den Fall,
der laut §1 tatsächlich eintritt.

---

## 4. M3 — Arbeitshypothese: ein Core-Neustart erklärt acht offene Befunde  [MESSEN]

Wenn §1 und §2 zutreffen, ist die Kette:

```
MPRIS2-Push aus falschem Thread
  → libdbus-Assertion → SIGABRT
  → Core-Prozess stirbt vollständig
  → systemd startet pidrive_core neu
  → im Neustartfenster ist der Bus-Name weg      → "ServiceUnknown"
  → source_state ist zurückgesetzt                → Spiegel sagt "idle"
  → Kindprozesse überleben als Waisen             → mpv / rtl_fm / welle-cli laufen weiter
  → laufende Transition wurde nie beendet         → "hängt in Transition"
```

Damit sind folgende Befunde **möglicherweise dasselbe Problem**, nicht acht verschiedene:

| Befund | Bisherige Deutung | Alternative über M3 |
|--------|-------------------|---------------------|
| `ServiceUnknown` (MPRIS2-Test) | D-Bus-Registrierung defekt | Neustartfenster |
| §10: `play web` startet mpv, `source_current` bleibt `idle` | fehlendes `commit_source("webradio")` | Spiegel nach Neustart zurückgesetzt, mpv als Waise weiter |
| §10: `welle-cli`-Waise nach Boot-Resume, nicht per User-`pkill` killbar | Core läuft als root | Waise eines abgestürzten root-Core |
| §10: `radio_stop` hängt in Transition | Transitionslogik | `finally: end_transition()` läuft nie, wenn der Prozess mitten im `try` stirbt |
| §11.4 / N3: Spiegel=`scanner`, Gerät leer | `commit_source` ohne Ergebnisprüfung | zusätzlich: Neustart zwischen Commit und Prüfung |
| TK1/TK2: „RTL-SDR belegt" durch übrig gebliebene Prozesse | Testkette stoppt falsche Quelle | Waisen nach Absturz |
| Z3: Stale-Transition-Watchdog läuft nicht periodisch | eigener Befund | wird durch M3 erst schmerzhaft |
| Spektrum „belegt trotz Idle" (Abnahmebefund) | Stale-Lock | Waise nach Absturz hält das Gerät |

**Das ist eine Hypothese, kein Befund.** Sie ist aber billig zu prüfen, und sie ist
entscheidungsrelevant: träfe sie zu, wären mehrere der geplanten Einzelfixes Behandlung von
Symptomen. Deshalb steht die Messung M-A vor jeder Codeänderung.

Wichtig für die Auslegung: `RemainAfterExit=no` und ein `Restart=`-Eintrag im Core-Unit
führen dazu, dass ein Absturz **unauffällig** bleibt. Im Terminal sieht man nichts, im
Testlauf nur die Folgeschäden. Genau deshalb ist der Verdacht so lange nicht aufgefallen.

---

## 5. Arbeitspakete

Reihenfolge ist verbindlich: **M-A vor allem anderen.** Ohne die Messung weiß niemand, ob
M-B..M-D die Ursache oder ein Symptom behandeln.

| ID | Paket | DoD |
|----|-------|-----|
| **M-A** | **Messen, nicht ändern.** Neustartzähler und Abbruchspuren des Core über einen vollständigen `test all`-Lauf erfassen (Kommandos in §6). Ergebnis nach `docs/ABNAHMEN.md`. | Belegt oder widerlegt: stürzt der Core während des Laufs ab, und wie oft? Bei `NRestarts > 0` ist M3 bestätigt. |
| **M-B** | Thread-Sicherheit herstellen: `dbus.mainloop.glib.threads_init()` direkt nach `DBusGMainLoop(set_as_default=True)` beim Modulimport (L35). Zusätzlich prüfen, ob `gi.repository.GLib` eine eigene Initialisierung braucht. | Ein Push aus der Core-Hauptschleife **und** einer aus der Triggerverarbeitung, 200-mal in Folge im Wechsel, ohne Absturz. |
| **M-C** | Sendepfad serialisieren: alle `PropertiesChanged`-Emissionen über die GLib-Schleife einreihen (`GLib.idle_add`) statt sie im aufrufenden Thread auszuführen. Betrifft `update_metadata()` (L87ff) und `push_test_metadata()` (L389-404). Ergebnis: **genau ein** Thread berührt die Verbindung. | Kein Aufruf von `PropertiesChanged` außerhalb des `mpris2-glib`-Threads mehr im Code nachweisbar. |
| **M-D** | Watchdog reparieren: bei Verlust auch `bus` und `_player` neu aufbauen, nicht nur Schleife und Name. Nach N erfolglosen Versuchen laut aufgeben (Log `error`) statt endlos zu wiederholen. Den `BusName`-Aufruf aus dem Watchdog-Thread in die Schleife einreihen (siehe M-C). | Erzwungener Verbindungsverlust (`systemctl reload dbus`) wird innerhalb von 60 s vollständig geheilt; Nachweis per `dbus-send ... ListNames`. |
| **M-E** | Workaround zurücknehmen: `_send_to_bmw` im DAB-Test (`test_suite.py:658`) wieder aktivieren, Kommentar entfernen. Erst **nach** M-B/M-C. | DAB-Test läuft mit Push durch, ohne Absturz. Der Test darf den Fehler wieder finden können. |
| **M-F** | Absturz sichtbar machen: Core-Neustarts zählen und im Testbericht ausweisen. Ein Lauf, in dem der Core neu startet, darf nicht als bestanden gelten. | `pidrivectl test all` meldet „Core-Neustarts während des Laufs: n" und setzt bei n>0 den Exit-Status. |

**Nicht tun:** den Workaround aus §1 auf weitere Tests ausdehnen. Jeder weggelassene Push
versteckt den Fehler zusätzlich. Ebenso nicht: den Watchdog-Intervall verkürzen — das
behandelt das Symptom und verschleiert M3.

---

## 6. Messung M-A

Vor dem Lauf:

```bash
systemctl show pidrive_core -p NRestarts -p Restart -p ExecMainStartTimestamp
sudo coredumpctl list 2>/dev/null | tail -5
```

Testlauf in einem zweiten Terminal beobachten:

```bash
journalctl -u pidrive_core -f -o short-precise | \
  grep -iE 'abort|SIGABRT|core-dump|Main process exited|Scheduled restart|Started PiDrive'
```

Dann `pidrivectl test all` laufen lassen. Danach:

```bash
systemctl show pidrive_core -p NRestarts
journalctl -u pidrive_core -b --no-pager | \
  grep -iE 'abort|SIGABRT|core-dump|Main process exited|Scheduled restart' | tail -20
sudo coredumpctl list 2>/dev/null | tail -5
grep -c 'MPRIS2 Watchdog' /var/log/pidrive.log 2>/dev/null || true
```

### Deutungsschlüssel — vorab festgelegt

| Befund | Bedeutung |
|--------|-----------|
| `NRestarts` steigt während des Laufs | **M3 bestätigt.** Die Einzelbefunde aus §4 sind neu zu bewerten, bevor sie einzeln behoben werden. |
| `Main process exited … signal=ABRT` im Journal | Ursache ist der Abort aus §1, nicht eine Python-Ausnahme. |
| `coredumpctl` zeigt Einträge zu `python3`/`pidrive` | Abbruchstelle ist auswertbar — `coredumpctl info` nennt die Bibliothek. |
| `NRestarts` unverändert, aber `ServiceUnknown` trotzdem | Der Prozess lebt; dann ist es Namensverlust ohne Absturz, und M-D ist der Hebel, nicht M-B. |
| Viele „MPRIS2 Watchdog: Service vom Bus verschwunden" ohne folgendes „neu gestartet" | M2 bestätigt: der Watchdog dreht sich auf einer toten Verbindung. |

### Gezielte Gegenprobe für §1

Reproduziert den Abort isoliert, ohne den ganzen Testlauf:

```bash
pidrivectl play dab 22     # oder eine beliebige Quelle starten
sleep 5
for i in $(seq 1 30); do
  echo "mpris_push:Test $i|Artist $i|Album $i" >> /tmp/pidrive_cmd
  sleep 0.2
done
sleep 3
systemctl show pidrive_core -p NRestarts
```

Steigt `NRestarts`, ist die Ursache eingekreist und M-B/M-C sind die richtigen Pakete.

---

## 7. Fortschritt

| Datum | Stand |
|-------|--------|
| 2026-09-16 | Angelegt. M1/M2 gegen `9db988b` belegt, M3 als Hypothese mit Messplan M-A. Auslöser: `ServiceUnknown` über zwei HW-Läufe unverändert, plus der Workaround-Kommentar in `test_suite.py:658`, der SIGABRT ausdrücklich benennt. |
| 2026-09-16 | **M-A gemessen** am Pi `192.168.178.107` (@ `9db988b`/v0.11.137): Gegenprobe 30+30+50 `mpris_push` (Web + DAB-Versuch + Stress). **`NRestarts` unverändert (0)**, kein `SIGABRT`/`Main process exited` im Journal, MPRIS-Name am Bus präsent. **M3 in diesem Lauf nicht bestätigt.** Deutung laut §6: Namensverlust ohne Absturz → Hebel eher **M-D** als M-B; M-B/M-C bleiben optional bis reproduzierbarer Abort. Teil D (Q-K…) darf weiter. |
