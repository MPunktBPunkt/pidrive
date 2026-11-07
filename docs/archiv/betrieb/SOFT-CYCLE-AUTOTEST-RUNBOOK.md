# Soft-Cycle-Autotest: Betrieb und Qualifizierung

Dieses Runbook beschreibt den sicheren Betrieb von
[`tools/soft_cycle_orchestrator.py`](../../tools/soft_cycle_orchestrator.py)
und die Freigabekriterien für Lab und Auto. Der Orchestrator betätigt nur
ESP-Softwarepfade; er steckt keine Hardware um. Ein physischer Replug kann nur
als manueller Marker protokolliert werden.

**Verbindlicher Messstand:** ESP-Mess-Firmware **0.4.52**. Jeder echte Lauf
muss sie mit `--require-version 0.4.52` prüfen. Ein Dry-run prüft lediglich
CLI, Ablauf und Artefakterzeugung.

## Topologie

```text
Bedienhost ── HTTP /api/* ──> ESP32-S3 ── USB-OTG/MSC ──> Lab-Host oder HU
                                  ^
Pi/Bridge ───── Live-Audio/TCP ───┘
```

- Alle Befehle werden im Root von `pidrive-main` ausgeführt.
- Bedienhost und ESP müssen sich stabil per HTTP erreichen.
- Im Live-Aufbau liefert der Pi/Bridge Audio per TCP an den ESP; dafür ist
  `ram_local` der Default und der einzig zulässige Capture-Modus.
- `ram_wifi_off` ist ausschließlich eine Lab-Baseline **ohne** Live-TCP. Es
  verlangt `--profile lab --no-live-audio` und darf nicht als Live-Nachweis
  oder Auto-Konfiguration verwendet werden.
- Zusatzhardware und physisches Umstecken gehören nicht zum automatisierten
  Ablauf. Ein manueller Replug ist eine getrennte, ausdrücklich markierte
  Beobachtung.

## Gates vor und während jedes Laufs

1. **Preflight:** `/api/status` muss Daten liefern, `otgUp=true`, Stall muss
   deaktiviert sein und die Version muss `0.4.52` enthalten. Ein bereits
   sichtbarer Panic-, Brownout- oder Watchdog-Grund sperrt den Lauf.
2. **Freeze:** `stallEnable` beziehungsweise jede bekannte Stall-Darstellung
   bleibt `false`. Der Orchestrator darf keine Stall-Experimente mit dieser
   Qualifizierung vermischen.
3. **Quiet:** Vor jeder Zelle ruft der Orchestrator `/api/lab/stop` auf.
   Stream und MSC-Phase müssen danach ruhig sein; sonst gilt `not-quiet`.
4. **Panic:** Uptime darf zwischen Episode A und B nicht zurückspringen.
   Panic, Brownout, Watchdog oder ein geänderter Reset-Code sind ein Hard Stop.
5. **Capture:** `/api/lab/mess` muss Command-Capture melden. Akzeptiert wird
   nur `complete=true`, `overflow=0`, `cmdCapture=true` und der erwartete
   Capture-Modus. Alle Seiten werden bis zum Ende exportiert.
6. **Identity:** Pro Matrixzelle dürfen nur die erwarteten Felder wechseln:
   `soft-usb` und `media-hide` keine; `serial` Product-Revision plus
   USB-Serial; `label` BPB- plus Root-Label; `volume-id` nur BPB Volume-ID.

Ein Gate-Fehler ist kein negatives Produktresultat, sondern macht die Zelle
ungültig und beendet die Kampagne.

## Selection Barrier nur als getrenntes Experiment

`selectionBarrierEnable` bleibt im Produktionsdefault `false`. Die Barrier
darf erst nach einer grünen Baseline als eigene Matrixvariante aktiviert
werden; sie hält den ersten relevanten Head-READ höchstens
`selectionBarrierMaxMs` zurück, bis ID3 und `selectionBarrierLeadBytes`
Audiovorlauf bereitstehen. Timeout, expliziter Stop, Remount und
Plug-Zustandswechsel sind Kill-Pfade.

Ein Barrier-Lauf muss die Status-KPIs `selectionBarrier.busy`, `ready`,
`timeouts` und `kills` sichern. Nur `ready>0`, kein neuer Timeout/Kill und
anschließender Head/LIVE-Read sind ein positiver Mechanismusnachweis. Ein
Timeout fällt auf den normalen Payloadpfad zurück und ist kein Live-Audio-
PASS. Barrier und Identity-/Lifecycle-Dimension dürfen nicht in derselben
Zelle geändert werden.

## CLI-Beispiele

Zuerst den vollständigen Ablauf ohne Hardware proben:

```bash
python3 tools/soft_cycle_orchestrator.py \
  --dry-run --profile auto --require-version 0.4.52 \
  --out artifacts/soft-cycle-dry-run
```

Live-TCP im Lab oder Auto verwendet den Default `ram_local`:

```bash
python3 tools/soft_cycle_orchestrator.py \
  --esp http://192.168.178.89 \
  --profile auto --capture-mode ram_local --live-audio \
  --require-version 0.4.52 \
  --out artifacts/soft-cycle-auto-001
```

Reine Lab-Baseline bei abgeschaltetem Live-TCP:

```bash
python3 tools/soft_cycle_orchestrator.py \
  --esp http://192.168.178.89 \
  --profile lab --capture-mode ram_wifi_off --no-live-audio \
  --require-version 0.4.52 --cells soft-usb \
  --out artifacts/soft-cycle-wifi-off-baseline
```

Eine einzelne Identity-Dimension isolieren:

```bash
python3 tools/soft_cycle_orchestrator.py \
  --esp http://192.168.178.89 \
  --profile lab --require-version 0.4.52 \
  --cells volume-id --out artifacts/soft-cycle-volume-id-01
```

Ein beobachteter, manuell ausgeführter Replug darf nur beschriftet werden:

```bash
python3 tools/soft_cycle_orchestrator.py \
  --esp http://192.168.178.89 --profile lab \
  --require-version 0.4.52 --cells soft-usb \
  --physical-replug-marker "operator replug after baseline" \
  --out artifacts/soft-cycle-manual-marker
```

## Qualifizierung im Lab

Ziel des Overnight-Laufs:

- **100** gültige `soft-usb`-Soft-Cycles;
- danach je **6** gültige, isolierte Wiederholungen der Identity-Zellen
  `serial`, `label` und `volume-id`;
- `media-hide` mindestens in der vorausgehenden vollständigen Matrixprobe;
- keine zusammengelegten Identity-Änderungen und kein automatisierter
  physischer Replug.

Der Orchestrator besitzt absichtlich keinen Repeat-Schalter. Die
Kampagnensteuerung startet jeden Lauf mit eigenem `--out`-Verzeichnis, prüft
den Exitcode und `SUMMARY.json` und stoppt beim ersten Fehler. Beispiel für
eine POSIX-Shell auf dem Lab-Host:

```bash
set -e
for n in $(seq -w 1 100); do
  python3 tools/soft_cycle_orchestrator.py \
    --esp http://192.168.178.89 --profile lab \
    --capture-mode ram_local --live-audio --require-version 0.4.52 \
    --cells soft-usb --out "artifacts/overnight/soft-usb-$n"
done

for cell in serial label volume-id; do
  for n in $(seq -w 1 6); do
    python3 tools/soft_cycle_orchestrator.py \
      --esp http://192.168.178.89 --profile lab \
      --capture-mode ram_local --live-audio --require-version 0.4.52 \
      --cells "$cell" --out "artifacts/overnight/$cell-$n"
  done
done
```

Die Sollzahlen zählen nur Zellen mit `valid=true`, gesundem Capture und
`SUMMARY.json` mit `pass=true`. Fehlversuche werden nicht durch Wiederholung
überschrieben oder aus der Kampagne entfernt.

## Qualifizierung im Auto

Das Auto-Fenster ist auf **25–40 Minuten** begrenzt. Vorher müssen Dry-run,
vollständige Lab-Matrix und Overnight-Ziel grün sein. Im Auto gilt:

- Mess-FW 0.4.52, `--profile auto`, `ram_local` und Live-TCP;
- zuerst eine vollständige Matrix, danach nur die im Auftrag festgelegten
  Wiederholungen innerhalb des Zeitfensters;
- keine `ram_wifi_off`-Baseline, keine Stall-Aktivierung und kein
  automatisierter Replug;
- Bedienereingriffe nur als Marker; keine stillen Änderungen zwischen Zellen.

Nach 40 Minuten wird kein neuer Lauf mehr begonnen. Ein begonnenes
Artefaktverzeichnis wird sauber abgeschlossen oder als Hard Stop erhalten.

## Artefaktvertrag

Jeder Aufruf erzeugt im eigenen Ausgabeverzeichnis:

- `run.yaml` und `run-manifest.json`: Run-ID, Git-Stand, Host, Profil,
  Capture-Modus, Live-Audio-Deklaration, Matrix und Preflight;
- `events.jsonl`: monotone Ereignisachse einschließlich Hard Stop;
- `marks.jsonl`: Bedienermarker, auch leer als Datei vorhanden;
- `status-poll.jsonl`: Statuszeitreihe mit Zelle und Episode;
- `CELL-REPORT.json`: aggregierte Reports aller ausgeführten Zellen;
- `SUMMARY.json`: PASS, Hard-Stop-Grund, Soll-/Ist-Zellen und Outcomes;
- `ERGEBNIS.md`: lesbare Kurzfassung.

Pro Zelle entstehen zusätzlich `a-snapshot.json`, `b-snapshot.json`,
`before-snapshot.json`, `after-snapshot.json`, `CELL-REPORT.json` und
`offline-bot-trace.json`. Der Trace enthält Capture-Modus, Seitennachweis,
Command-Anzahl, Sequenzgrenzen, Commands und Capture-Health.

Für jeden Lauf muss der Bediener ein neues, leeres `--out`-Verzeichnis wählen;
der Orchestrator erzwingt das derzeit nicht. Sonst können angehängte JSONL-
Zeilen und ersetzte Reports verschiedene Läufe vermischen. Für eine Auswertung
müssen Manifest, Summary, alle Zellreports und Traces gemeinsam aufbewahrt
werden.

## Episode A/B ist nicht Outcome A–E

- **Episode A/B** bezeichnet den Messzeitpunkt: A vor der Soft-Aktion, B
  danach. Das sind Snapshots, keine Ergebnisnoten.
- **Outcome A–E** klassifiziert unabhängig davon die Beobachtung:
  **A** Head/LIVE, **B** Mid-/Body-Read, **C** kein relevanter neuer
  Read/Cache, **D** Transport-Reset oder Panic, **E** unvollständige oder
  mehrdeutige Evidenz.

Ein Outcome allein ist kein PASS. PASS verlangt zusätzlich alle Gates und
`valid=true`.

## Stopregeln

Die Kampagne stoppt sofort bei `panic`, `uptime-rollback`,
`freeze-violation`, `not-quiet`, `identity-drift`, `preflight-failed`,
`operation-failed` oder `capture-incomplete`. Ebenfalls stoppen bei
verlorener HTTP-Verbindung, unbekanntem Firmwarestand, vermischten
Identity-Dimensionen oder Überschreitung des Auto-Zeitfensters.

Nicht blind weiterlaufen und einen fehlgeschlagenen Ordner nicht
überschreiben. Zeitpunkt, Bedienhandlung und beobachtete Infrastruktur im
Marker beziehungsweise Übergabeprotokoll ergänzen.

## Recovery

1. Fehlgeschlagenes Artefaktverzeichnis unverändert sichern.
2. Hard-Stop-Grund in `SUMMARY.json`, `events.jsonl` und Zellreport prüfen.
3. Bei `not-quiet` den Stream regulär stoppen und erst nach stabilem
   Quiet-Status neu preflighten.
4. Bei Capture-Fehler `complete`, `overflow`, `cmdCapture`, Modus und
   Pagination prüfen; neuen Lauf mit leerem Ausgabeverzeichnis starten.
5. Bei Identity-Drift keine weitere Dimension testen. Erwartete
   Ausgangsidentity kontrolliert wiederherstellen und mit einem neuen
   Preflight beginnen.
6. Bei Panic, Reset, Uptime-Rollback oder Verbindungsverlust Ursache und
   Reset-Grund sichern. Erst nach stabiler Versorgung, stabilem Status und
   erneut bestandenem Preflight fortsetzen.
7. Ein Recovery-Lauf erhält eine neue Run-ID und ein neues Verzeichnis; der
   ursprüngliche Fehlversuch bleibt Bestandteil der Evidenz.

## Aussagegrenze dieses Stands

Die aktuelle lokale Umgebung hatte weder die benötigte Hardware noch den
Lab-/Fahrzeugaufbau verfügbar. Dokumentation und CLI-Vertrag konnten daher
offline geprüft werden, aber **es wird ausdrücklich kein Hardware-PASS, kein
Lab-PASS und kein Auto-PASS behauptet**. Diese Aussagen dürfen erst nach den
oben beschriebenen Läufen mit vollständigen Artefakten getroffen werden.
