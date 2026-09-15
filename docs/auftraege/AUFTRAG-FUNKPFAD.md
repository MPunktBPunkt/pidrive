> **Arbeitsauftrag — Funkpfad: vier Zeilen, die den Scanner blockieren**
> Stand: 2026-09-15 · Basis: v0.11.128 (`f749a42`) · Befund-Präfix: **K**

---

## 0. Zweck und Abgrenzung

Dieses Dokument ist **neu angelegt**, weil parallel an
[AUFTRAG-WEBUI-SANIERUNG.md](AUFTRAG-WEBUI-SANIERUNG.md) gearbeitet wird. Es gilt weiter
**ein Schreiber pro Datei**: an jener Datei arbeitet die andere Instanz, an dieser hier
niemand sonst.

Inhaltlich überschneidet es sich mit den dortigen Befunden C1, C2, C3 und C7 — aber es
**korrigiert deren Ursachenbeschreibung**. Die dortigen Beschreibungen sind teils falsch,
weil sie vor v0.11.128 entstanden sind. Abschnitt 7 listet auf, was in jenem Dokument
nachzuziehen ist; **diese Nachträge macht die Instanz, die jenes Dokument besitzt**, nicht
diese hier.

Die Befunde tragen bewusst ein eigenes Präfix **K** (Korrektur), damit keine Nummer mit
S, V, C, F, W, Z, E, H, R, M, G oder B kollidiert.

**Warum das ein eigenes, vorgezogenes Paket ist:** es sind vier geänderte Zeilen, und sie
entscheiden darüber, ob der Scanner — der ursprüngliche Zweck des Geräts — überhaupt
messbar ist. Ohne sie sind alle Scanner-Messungen aus W4/W5/W8 wertlos, weil sie einen
Zustand messen, in dem drei Schutzmechanismen stillgelegt sind.

---

## 1. Ausgangslage v0.11.128

Gegen den Stand `f749a42` geprüft. **Behoben und bestätigt:**

| Befund | Stand |
|---|---|
| C16 — Closure-Fehler `source_state` in `td_hardware.py` | behoben, lokaler Import entfernt |
| S11 — `safe_run` ohne Import in `web/shared/audio.py` | behoben, Import in Z. 8 |
| S12 — `sys` ohne Import in `web/shared/view_model.py` | behoben, Import in Z. 4 |
| Versionsdisziplin (H0) | greift — `VERSION` = 0.11.128 mit funktionaler Änderung angehoben |
| `degraded_imports` sichtbar | greift — `ipc.py:108` schreibt das Feld in die Statusdatei |

Das letzte Element ist für dieses Paket zentral: **die Befunde K1 und K2 sind am Pi in
zehn Sekunden beweisbar**, ohne Fahrzeug, ohne Funkgerät.

**Noch offen und hier behandelt:** K1–K4.

---

## 2. Befunde

### K1 Falscher Importpfad in `modules/radio/` — die echte Ursache von C2 `[BELEGT]` — kritisch

**C2 gilt als „Shim ergänzt". Der Shim ist da, aber er zeigt auf einen Pfad, der nicht
existiert.** Damit ist die Wirkung unverändert: die Geräte-Arbitrierung bleibt still
abgeschaltet, nur wird sie jetzt gemeldet.

Die Module liegen in `modules/radio/`, importiert wird aus `modules/`:

| Stelle | Import | auflösbar |
|---|---|:-:|
| `modules/radio/fm.py:18` | `from modules import rtlsdr as _rtlsdr` | **nein** |
| `modules/radio/scanner.py:24` | `from modules import rtlsdr as _rtlsdr` | **nein** |
| `modules/radio/scanner.py:39` | `from modules import spectrum as _spectrum` | **nein** |
| `modules/radio/dab_helpers.py:11` | `from modules import rtlsdr as _rtlsdr` | **nein** |
| `modules/radio/spectrum.py:33` | `from modules import rtlsdr as _rtlsdr` | **nein** |

Gegenprobe: `modules/rtlsdr.py` und `modules/spectrum.py` existieren nicht, die Dateien
liegen unter `modules/radio/rtlsdr.py` und `modules/radio/spectrum.py`.

**Von außerhalb wird überall die richtige Form benutzt** — `main_core.py:350`,
`trigger/td_hardware.py:295`, `web/app.py:669` und `:725`, `web/shared/view_model.py:162`
schreiben alle `from modules.radio import …`. Der Fehler sitzt ausschließlich *innerhalb*
von `modules/radio/`, was zur Relokation dieser Dateien passt: beim Verschieben wurden die
internen Importe nicht mitgezogen. Das ist dieselbe Fehlerklasse wie S13 (Aufteilung von
`web/shared.py` in das Paket `web/shared/`).

**Vermutliche Quelle der Kopien:** der Docstring in `modules/radio/rtlsdr.py:17` zeigt als
Nutzungsbeispiel noch `from modules import rtlsdr`. Der ist mitzukorrigieren, sonst
entsteht der Fehler beim nächsten neuen Modul erneut.

**Wirkung.** Kein Absturz, sondern stilles Abschalten. `_rtlsdr` bleibt `None`, und die
Aufrufstellen sind durchgängig defensiv formuliert — `fm.py:187` lautet `if _rtlsdr:` und
überspringt die Arbitrierung einfach. Damit erklärt sich in einem Zug:

- **RTL-SDR-Konflikte** zwischen DAB, FM und Scanner. `rtlsdr.acquire_lock()` (Z. 343) und
  `acquire_runtime_lock()` (Z. 300) sind vollständig implementiert und werden **nie**
  erreicht.
- **Falsche „kein Signal"-Urteile** in `pidrivectl test all`: der DAB-Scan startet einen
  zweiten `welle-cli` neben dem laufenden, beide greifen auf denselben Stick zu.
- **FastScan liefert seit immer eine leere Liste** (Befund F1). `scanner.py:39` bekommt das
  Spektrum-Modul nie zu sehen, und die spektrumgestützten Zweige für PMR446 und Freenet
  (`scanner.py:572`, `:587`) sind damit dauerhaft deaktiviert.

**Korrektur:** `modules` → `modules.radio` an den fünf Stellen, plus Docstring.

Wichtig: nach der Korrektur werden Sperren erstmals wirksam. Es ist damit zu rechnen, dass
Abläufe, die bisher „irgendwie" liefen, nun mit einer Sperrmeldung abbrechen. **Das ist der
gewünschte Zustand** und kein Rückschritt — aber es gehört in die Abnahme, weil es wie eine
Regression aussieht.

### K2 Bandbreiten-Untergrenze macht Schmalband unhörbar `[BELEGT]` — kritisch

**Dies ist die Antwort auf die Ausgangsfrage des Eigentümers, warum
Walkie-Talkie-Empfang nie funktioniert hat.**

`scanner.py:363-372`:

```python
if bandwidth_hz >= 150000:
    _rtl_sr = 250000          # Wideband FM — korrekt
    _out_sr = 32000
    _modulation = "wbfm"
else:
    _rtl_sr = max(200000, int(bandwidth_hz) * 4)   # ← Untergrenze
    _out_sr = 32000
    _modulation = "fm"
```

Die Untergrenze `200000` macht die Rechnung `bandwidth_hz * 4` für **jedes** Schmalband
wirkungslos. Gegen die Bandtabelle (`scanner.py:140-180`) gerechnet:

| Band | `bw` | `bandwidth_hz * 4` | tatsächlich `-s` | Faktor zu breit |
|---|--:|--:|--:|--:|
| PMR446 | 12 500 | 50 000 | **200 000** | **16×** |
| Freenet | 12 500 | 50 000 | **200 000** | **16×** |
| LPD433 | 12 500 | 50 000 | **200 000** | **16×** |
| CB-Funk | 10 000 | 40 000 | **200 000** | **20×** |
| VHF | 25 000 | 100 000 | **200 000** | **8×** |
| UHF | 25 000 | 100 000 | **200 000** | **8×** |
| FM/UKW | 200 000 | — | 250 000 (wbfm) | korrekt |

`rtl_fm` demoduliert damit einen 12,5-kHz-Kanal über 200 kHz Bandbreite. Aus dem
Lautsprecher kommt überwiegend Rauschen mit Nachbarkanälen darin — unabhängig davon, ob ein
Signal anliegt. Das ist kein Empfangsproblem und keine Antennenfrage.

**Der einzige Zweig, der funktioniert, ist der einzige, der getestet wird:**
`test_scanner_fm("103.0")` (`test_suite.py:486`) prüft ausschließlich WBFM — also den
`>= 150000`-Pfad. Alle sechs Schmalbandbänder sind ungetestet. Deshalb ist der Fehler nie
aufgefallen.

**Korrektur.** Die Untergrenze muss weg. Der Zielwert ist jedoch **zu messen, nicht zu
raten**: bei `rtl_fm` ist `-s` die Demodulationsbandbreite, und die übliche Aufrufform für
PMR446 setzt sie auf die Kanalbandbreite (`-s 12500 -r 32000`). Auch die ursprünglich
gemeinte Formel `bandwidth_hz * 4` wäre mit 50 kHz noch viermal zu breit.

Empfohlenes Vorgehen: `_rtl_sr = int(bandwidth_hz)` als Ausgangspunkt, dann Messreihe nach
Abschnitt 4 (K2-Messung). Erst das Messergebnis wird eingecheckt, mit der Messung im
Kommentar.

**Im selben Durchgang zu prüfen:** `_scan_bw_fast(band_id, bw)` (`scanner.py:638`, `:675`)
liefert die Bandbreite für den Suchlauf und gibt an einer Stelle unbedingt `25000` zurück
(`scanner.py:555`). Ob das zu den korrigierten Werten passt, ist mitzuentscheiden — sonst
sucht der Suchlauf mit anderer Bandbreite als die Wiedergabe.

### K3 Der Suchlauf bricht sich selbst ab `[BELEGT]` — kritisch

**Genaue Ursache von C1, mit Zeilen.** Der Suchlauf öffnet eine Transition und bricht dann
ab, weil eine Transition offen ist.

Aufrufseite, `trigger/td_scanner.py:92-101`:

```python
def _scan_next(b=band):
    _stop_other_sources(S)
    if source_state.begin_transition(f"scan_next:{b}", "scanner"):   # öffnet
        try:
            scanner.scan_next(b, S, settings)                        # läuft darin
            ...
```

Empfangsseite, `modules/radio/scanner.py:640-645`:

```python
for _ in range(n):
    if (_scan_abort
            or (_src_state and _src_state.in_transition())           # ← trifft sofort zu
            or S.get("radio_type") not in ("", "SCANNER")):
        log.info(f"Scanner scan-list: abgebrochen band={band_id} radio_type={...}")
        return None
```

Die Bedingung ist in der **ersten** Iteration wahr. Kein Kanal wird geprüft, die Funktion
liefert `None`, und die Logzeile „abgebrochen" erscheint. Identisch bei Bereichssuche:
`scanner.py:677-682`.

`_src_state` ist hier **nicht** `None` — `scanner.py:34` importiert
`from modules import source_state as _src_state`, und `modules/source_state.py` existiert
tatsächlich. Die Abfrage ist also live. (Das ist der Unterschied zu K1: dort zeigt der
Import auf `modules/radio/`-Dateien, hier auf eine Datei, die wirklich in `modules/`
liegt.)

**Korrektur — Entscheidung nötig, siehe Abschnitt 8.** Zwei Wege:

1. Die Abbruchprüfung soll „*fremde* Transition" bedeuten, nicht „irgendeine". Dann muss
   der Eigentümer verglichen werden — was eine `owner`-Konvention voraussetzt, die laut
   Z6 heute nicht existiert.
2. Der Suchlauf läuft nicht innerhalb der Transition: `begin_transition` sichert nur den
   Wechsel, `end_transition` kommt vor dem Scan, `commit_source` danach.

Weg 2 ist der kleinere Eingriff und passt zum Zweck von `begin_transition` (Wechsel
absichern, nicht Dauerbetrieb). Weg 1 ist die sauberere Semantik, greift aber in die
Zustandsmaschine ein und gehört dann in W7/Stufe 3.

### K4 `begin_transition` mit unbekanntem Schlüsselwort `[BELEGT]` — hoch

**Genaue Ursache von C7.** `modules/radio/scanner.py:330`:

```python
_src_state.begin_transition("scanner", reason="user_select")
```

Signatur, `modules/source_state.py:100`:

```python
def begin_transition(owner: str, target: str, timeout_s: float = STALE_TIMEOUT_S) -> bool:
```

Zwei Fehler in einer Zeile: `target` fehlt, und `reason` existiert nicht. Der Aufruf löst
einen `TypeError` aus. Der Rückgabewert wird zudem nicht geprüft, sodass die Transition
**nie** geöffnet wird und niemand es merkt.

**Korrektur:** `_src_state.begin_transition("scanner", "scanner")`. Der Zielname `"scanner"`
ist durch `commit_source("scanner")` belegt — an zehn Stellen in `td_scanner.py` und in
`scanner.py:431`. Den Rückgabewert prüfen, nach dem Muster aus `trigger/td_radio.py:96-101`
(Meldung an den Nutzer, Nebensperre freigeben, Abbruch). **Kein neues Muster erfinden.**

Reihenfolge beachten: K4 öffnet eine Transition, die es heute nicht gibt. Wird K4 **vor**
K3 korrigiert, verschärft sich K3 an dieser Stelle. **K3 zuerst.**

### K5 Was die vier Befunde gemeinsam erklären

Nicht als eigener Fehler, sondern als Lesehilfe für die Abnahme — diese vier Zeilen
erklären zusammen die gesamte Symptomlage des Funkpfads:

| Symptom | verursacht durch |
|---|---|
| „Scanner nicht mehr verifizierbar" (Ausgangsbeschwerde) | K2 — Empfang ist Rauschen |
| Suchlauf findet nie etwas | K3 — bricht in der ersten Iteration ab |
| RTL-SDR-Konflikte zwischen DAB, FM, Scanner | K1 — Arbitrierung nie erreicht |
| `pidrivectl test all` meldet „kein DAB-Signal" | K1 — zweiter `welle-cli` auf demselben Stick |
| FastScan liefert immer `[]` (F1) | K1 — Spektrum-Modul nie geladen |
| Spektrumgestützte Suche für PMR446/Freenet wirkungslos | K1 — `scanner.py:572`, `:587` deaktiviert |

**Folge für die Reihenfolge der anderen Pakete:** Scanner-Messungen aus W4, W5 und W8 sind
vor diesem Paket nicht aussagekräftig. Sie messen einen Zustand, in dem Arbitrierung,
Spektrumhilfe und Bandbreite gleichzeitig defekt sind. Dieses Paket ist deshalb
**vorzuziehen**.

---

## 3. Arbeitsschritte

Reihenfolge ist bindend; sie folgt aus der Abhängigkeit in K4.

| # | Schritt | Datei(en) | Umfang |
|---|---|---|---|
| 1 | Baseline aufnehmen (Abschnitt 4, Schritt 0) | — | 5 min |
| 2 | **K1** — Importpfade korrigieren, Docstring mit | `fm.py:18`, `scanner.py:24`, `:39`, `dab_helpers.py:11`, `spectrum.py:33`, `rtlsdr.py:17` | 6 Zeilen |
| 3 | K1 verifizieren: `degraded_imports` muss leer sein | — | 2 min |
| 4 | **K3** — Suchlauf aus der Transition lösen (Entscheidung E-K1) | `td_scanner.py`, evtl. `scanner.py:640`, `:677` | klein |
| 5 | **K4** — Aufruf reparieren, Rückgabewert prüfen | `scanner.py:330` | 4 Zeilen |
| 6 | **K2** — Untergrenze entfernen, dann **messen** | `scanner.py:370`, evtl. `:555` | 1 Zeile + Messreihe |
| 7 | Tests aus Abschnitt 5 ergänzen und in `run_all()` aufnehmen | `test_suite.py` | — |
| 8 | `VERSION` anheben, Abnahme in `docs/ABNAHMEN.md` protokollieren | — | — |

Nach Schritt 2 **nicht** gleich weiterarbeiten: die Wirkung von K1 ist so groß, dass sie
einzeln abgenommen werden sollte. Sonst ist später nicht unterscheidbar, welche Korrektur
welche Änderung bewirkt hat.

---

## 4. Hardware-Verifikation am Pi

Host `192.168.178.105`. Jede Messung nennt den Commit-Hash, sonst ist sie nicht
zuordenbar (H0).

### Schritt 0 — Baseline

```bash
cd <pidrive-repo> && git rev-parse --short HEAD && git status --short
pidrivectl test all 2>&1 | tee /tmp/baseline_funkpfad_$(date +%F_%H%M).log
cp /tmp/pidrive_status.json /tmp/baseline_status.json
```

### K1 — vor und nach der Korrektur

Der schnellste Nachweis im ganzen Projekt, weil `ipc.py:108` das Feld bereits schreibt:

```bash
python3 -c "import json;print(json.load(open('/tmp/pidrive_status.json')).get('degraded_imports'))"
```

| | Erwartung |
|---|---|
| **vor** K1 | enthält `modules.rtlsdr` **und** `modules.spectrum` |
| **nach** K1 | leer |

Zweiter Nachweis, dass die Sperre nun greift:

```bash
# DAB starten, dann parallel FM anfordern
pidrivectl dab play "BAYERN 3" ; sleep 3
pidrivectl fm play 104.4
journalctl -u pidrive_core -n 40 --no-pager | grep -iE "lock|rtlsdr|belegt"
```

| | Erwartung |
|---|---|
| **vor** K1 | keine Sperrmeldung, zwei Prozesse am Stick, Tonaussetzer oder Fehlverhalten |
| **nach** K1 | Sperrmeldung mit Eigentümer, der zweite Zugriff wird geordnet abgewiesen |

### K2 — Messung statt Hörtest

Der bisherige „5 s Hörtest" (H4.5) besteht, sobald der Prozess startet, und ist als
Nachweis untauglich. Stattdessen:

```bash
pidrivectl scanner pmr446 ch 1
ps aux | grep -- "[r]tl_fm"          # -s ablesen
```

| | Erwartung |
|---|---|
| **vor** K2 | `-s 200000` |
| **nach** K2 | `-s 12500` (oder der gemessene Zielwert) |

Für den Nachweis, dass tatsächlich Empfang entsteht, braucht es eine **Gegenprobe mit
bekanntem Signal** — ein Handfunkgerät auf PMR446 Kanal 1, das im Wechsel sendet und
schweigt:

| Zustand | zu erfassen | Erwartung nach K2 |
|---|---|---|
| Gegenstelle sendet | RMS-Pegel am `rtl_fm`-Ausgang | deutlich über Ruhepegel |
| Gegenstelle schweigt | dito | Ruhepegel, mit Squelch nahe Null |

Ohne diese Gegenprobe ist „kein Signal" von „defekt" nicht unterscheidbar (H4.6). Falls
kein Funkgerät verfügbar ist, ersatzweise ein bekannter Ortssender im VHF- oder
UHF-Bereich — dann aber mit `bw` 25000, also einem anderen Faktor.

**Messreihe zum Zielwert:** `-s` über 12500, 25000, 50000 durchfahren und je Wert
Sprachverständlichkeit sowie Ruhepegel notieren. Das Ergebnis mit Datum in den Kommentar
über `scanner.py:370`.

### K3 und K4

```bash
pidrivectl scanner pmr446 scan
journalctl -f -u pidrive_core | grep -iE "scan-list|abgebrochen|transition"
```

| | Erwartung |
|---|---|
| **vor** K3 | „Scanner scan-list: abgebrochen" in der **ersten** Iteration, kein `rtl_fm` in `ps` |
| **nach** K3 | je Kanal eine `FAST`-Zeile, insgesamt so viele wie das Band Kanäle hat |
| **nach** K4 | Transition wird geöffnet und geschlossen; ein paralleler Wechselversuch wird **sichtbar** abgewiesen |

---

## 5. Tests, die mit diesem Paket entstehen

Keine Korrektur ohne zugehörige Prüfung. Alle in `run_all()` aufnehmen.

| Test | prüft | zu K |
|---|---|---|
| `test_imports_intact` | Alle Module in `modules/radio/` importieren; `degraded_imports` ist leer. **Verhindert die Wiederkehr der ganzen Fehlerklasse** — auch S13 wäre damit aufgefallen | K1 |
| `test_rtlsdr_arbitration` | Zweiter Zugriff bei laufendem Erstzugriff wird abgewiesen, mit Eigentümer im Log | K1 |
| `test_scanner_narrowband` | PMR446 Kanal 1: `-s` entspricht der Bandbreite, Bytes am Ausgang, Pegel | K2 |
| `test_scanner_scan` | Suchlauf prüft **alle** Kanäle des Bands, nicht null | K3 |
| `test_source_reject` | Paralleler Wechsel wird sichtbar abgelehnt | K4 |

`test_imports_intact` ist der wichtigste davon. K1 und S13 sind dieselbe Fehlerklasse —
Importe, die nach einer Verschiebung nicht mitgezogen wurden und still fehlschlagen. Ein
Test, der alle Module einmal lädt und `degraded_imports` prüft, kostet wenige Zeilen und
schließt die Klasse.

---

## 6. Was ausdrücklich nicht zu tun ist

- **`AUFTRAG-WEBUI-SANIERUNG.md` nicht anfassen.** Dort arbeitet die andere Instanz.
  Nachträge stehen in Abschnitt 7 und werden von dort aus eingearbeitet.
- **Keine W-Nummern umnummerieren**, keine C-Befunde dort löschen oder umschreiben.
- **Die `try/except`-Hüllen um die Importe nicht entfernen.** Sie sind richtig — nur der
  Pfad darin ist falsch. Ohne Hülle stürzt der Core bei einem echten Importfehler ab.
- **`_scan_abort` und die `radio_type`-Prüfung in der Abbruchbedingung nicht anrühren.**
  Nur der `in_transition()`-Teil ist zu klären (K3).
- **Keinen Zielwert für `-s` einchecken, der nicht gemessen wurde.** Die Untergrenze war
  vermutlich genau so entstanden.
- **Keine Änderung an der Zustandsmaschine über K3/K4 hinaus.** Übergangstabelle,
  Eigentümerprüfung und Zusammenführung der Sperrschichten bleiben in W7/Stufe 3.
- **Nicht über den Funkpfad hinaus aufräumen.** Die Befunde D1–D3 in
  [AUFTRAG-DISPLAY-RUECKMELDUNG.md](AUFTRAG-DISPLAY-RUECKMELDUNG.md) und P-F1 sind
  angrenzend, aber nicht Teil dieses Pakets. **Achtung:** D3 fasst `scanner.py:709-780` an,
  dieses Paket `scanner.py:24`, `:39`, `:330`, `:370`. Verschiedene Stellen, dieselbe
  Datei — nicht gleichzeitig bearbeiten, dieses Paket zuerst.

---

## 7. Nachzuziehen in `AUFTRAG-WEBUI-SANIERUNG.md`

Zur Einarbeitung durch die Instanz, die jenes Dokument besitzt — **nach** Abschluss der
laufenden Pakete, damit keine Zwischenstände kollidieren.

| Stelle | heute | richtig |
|---|---|---|
| C2 (L296, L320, L886) | „toter Code" bzw. „Shim fehlt" | Shim vorhanden, aber falscher Pfad — Wirkung unverändert. Siehe **K1** |
| C1 | „Suchlauf bricht ab" | Ursache benannt: `td_scanner.py:94` öffnet die Transition, `scanner.py:642` bricht daran ab. Siehe **K3** |
| C3 | „Bandbreite 200000 statt 25000" | Zahl korrigieren: PMR446 hat `bw` 12500, also Faktor **16**, nicht 8. CB liegt bei Faktor 20. Siehe **K2** |
| C7 | „nicht existierendes Schlüsselwort" | zusätzlich fehlt `target`; Zielname ist `"scanner"`. Siehe **K4** |
| F1 | „FastScan liefert `[]`" | Ursache ist K1, nicht die Spektrumlogik selbst |
| §7 Reihenfolge | W4 vorziehen | dieses Paket **vor** W4/W5/W8, Begründung in **K5** |

Zusätzlich ist **dieses Dokument in `docs/README.md` zu registrieren** — eine Zeile in der
Dokumententabelle. Absichtlich nicht selbst eingetragen: an jener Datei kam es bei der
Menü-Arbeit schon zu einem Konflikt, und sie wird während der laufenden Pakete vermutlich
angefasst. Vorschlag für die Zeile:

```
| [auftraege/AUFTRAG-FUNKPFAD.md](auftraege/AUFTRAG-FUNKPFAD.md) | Arbeitsauftrag Funkpfad — Importpfade, Bandbreite, Suchlauf | Entwickler | 2026-09-15 |
```

Gleiches gilt für `docs/architektur/ZUSTANDSMASCHINE.md`, wo C2 an den Stellen L114 und
L347 als „toter Code" geführt wird — richtig ist „unerreichbar wegen Importfehler".

---

## 8. Entscheidungen beim Eigentümer

| # | Frage | Empfehlung |
|---|---|---|
| **E-K1** | Wie wird K3 behoben — Suchlauf aus der Transition lösen, oder Eigentümervergleich in der Abbruchprüfung? | **Suchlauf herauslösen.** Kleinerer Eingriff, und `begin_transition` ist zum Absichern eines Wechsels gedacht, nicht für Dauerbetrieb. Der Eigentümervergleich setzt eine `owner`-Konvention voraus, die laut Z6 heute nicht existiert, und gehört damit in W7/Stufe 3. |
| **E-K2** | Welcher `-s`-Wert wird eingecheckt? | Erst nach der Messreihe aus Abschnitt 4 entscheiden. Ausgangspunkt `_rtl_sr = int(bandwidth_hz)`. |
| **E-K3** | Muss `_scan_bw_fast()` zu den korrigierten Bandbreiten passen, oder ist eine breitere Suchbandbreite gewollt? | Eine breitere Bandbreite beim **Suchen** ist sinnvoll — sie findet Signale schneller. Beim **Hören** ist sie falsch. Vorschlag: Suche breit lassen, Wiedergabe schmal, und den Unterschied im Code kommentieren, damit er nicht wieder als Fehler „korrigiert" wird. |
| **E-K4** | Ist ein Handfunkgerät für die Gegenprobe verfügbar? | Ohne Gegenprobe bleibt K2 unbewiesen, und der Scanner damit weiterhin „nicht verifizierbar" — also genau der Ausgangszustand. |

---

## 9. Definition of Done

- `degraded_imports` in der Statusdatei ist am Pi **leer**; `test_imports_intact` läuft in
  `run_all()` mit.
- Ein zweiter RTL-SDR-Zugriff bei laufendem Erstzugriff wird abgewiesen, mit Eigentümer im
  Log — nachgewiesen am Pi.
- `pidrivectl scanner pmr446 scan` prüft alle Kanäle des Bands; die Logzeile
  „abgebrochen" erscheint **nicht** mehr in der ersten Iteration.
- `ps aux | grep rtl_fm` zeigt bei PMR446 Kanal 1 die gemessene Bandbreite, nicht 200 000.
- Gegenprobe mit bekanntem Signal bestanden: Sendung und Ruhe sind am Pegel
  unterscheidbar.
- Ein paralleler Quellenwechsel während des Scans wird **sichtbar** abgewiesen, nicht
  stumm verworfen.
- `pidrivectl test all` zeigt gegen die Baseline aus Schritt 0 keine neuen Fehler. Neue
  **Sperrmeldungen** sind erwartet und kein Rückschritt (siehe K1).
- `VERSION` angehoben, Abnahme mit Commit-Hash in `docs/ABNAHMEN.md`.
- Abschnitt 7 an den Eigentümer der anderen Datei übergeben.

---

## 10. Historie

| Datum | Änderung |
|---|---|
| 2026-09-15 | Angelegt. Befunde K1–K5 gegen v0.11.128 (`f749a42`) belegt. Anlass: Prüfung, was nach Abschluss von W0/W1 dringend offen ist. Als eigenes Dokument geführt, weil `AUFTRAG-WEBUI-SANIERUNG.md` parallel bearbeitet wird. |
