# PiDrive v0.8.25 — Fehleranalyse

**Datum:** 20.04.2026  
**Version:** v0.8.25  
**Diagnose-Basis:** Log-Snapshot 07:49, Diagnose 22:27, SSH-Session 07:38

---

## 1. Audio / Kein Ton auf Klinke

### Symptom
FM spielt (rtl_fm + mpv laufen), WebUI zeigt `effective=klinke`, trotzdem kein Ton.

### GPT-These: mpv hängt nicht an PulseAudio
**Teilweise falsch.** GPT hat einen wichtigen Widerspruch aufgezeigt, aber die Schlussfolgerung stimmt nicht ganz.

**Beleg aus der Diagnose (läuft als root):**
```
✓ Aktive Sink-Inputs: 1
  Input: 3  0  2668  protocol-native.c  float32le 2ch 48000Hz
```
Und WebUI zeigt ebenfalls einen Sink-Input (ID=1, Sink=0). mpv IST also an PulseAudio angebunden.

**Warum `pactl list sink-inputs` als User `pi` leer zurückkommt:**  
PulseAudio läuft in System-Mode (`--system`) → Socket: `/var/run/pulse/native`.  
`pactl` als User `pi` verbindet sich mit `$XDG_RUNTIME_DIR=/run/user/1000/pulse/native` — das ist der User-Socket, der nicht existiert. PulseAudio findet keinen Stream, weil es die falsche Instanz anfragt. GPT interpretiert das fälschlich als "mpv hängt nicht an PA".

### Echter Fehler 1: `Default Sink` ist leer

**Diagnose-Output:**
```
⚠ Default Sink: leer (pactl get-default-sink gab nichts zurück)
```
**WebUI:**
```
Default Sink: –
```
`pactl get-default-sink` liefert leer wenn kein Default Sink explizit gesetzt ist. PulseAudio routet dann nach internem Fallback-Mechanismus. Das erklärt warum mpv manchmal Ton hat, manchmal nicht — der Fallback ist nicht deterministisch.

**Fix:** `pactl set-default-sink alsa_output.0.stereo-fallback` in `setup_bt_audio.sh` persistent setzen.

### Echter Fehler 2: amixer numid=3 Parse-Bug in diagnose.py

**Diagnose-Output:**
```
⚠ Pi Audio-Ausgang (amixer numid=3): Unbekannt (0x00])
```
`diagnose.py` parst `values=0x00000001` (Hex-Format auf manchen Kernel-Versionen) mit `raw = val.split("=")[-1]`. Das ergibt `0x00000001` oder `0x00]` — nicht im Mapping `{"0", "1", "2"}`.  
Der Klinke-Zustand ist unklar. `amixer numid=3=1` wird zwar im Log gelogged, aber die Diagnose kann nicht verifizieren ob er tatsächlich gesetzt ist.

**Fix:** Diagnose muss `int(raw, 0)` für Hex-Parsing nutzen.

### Echter Fehler 3: Gain-Änderungen haben keinen sofortigen Effekt

`rtl_fm -g` wird nur beim Start der Pipe übergeben. Eine Gain-Änderung via WebUI schreibt den Wert in settings.json, aber der laufende Prozess übernimmt ihn nicht. Erst nach `radio_stop` + neu spielen ist die Änderung aktiv.  
**→ Das ist ein Design-Problem, kein Bug. Aber die WebUI erklärt es nicht.**

### Echter Fehler 4: Unterspannung (kritisch)

**Installer:**  
```
⚠ Unterspannung erkannt (throttled=0x20000) — 5V/3A Netzteil empfohlen
```
**Status-JSON:**  
```
throttled=0x50000
```
`0x50000` = bit 16 (Unterspannung aktuell) + bit 18 (gedrosselt seit Boot).  
Unterspannung destabilisiert USB-Bus → betrifft RTL-SDR und BT-Dongle direkt.  
**Das kann die Ursache für unzuverlässigen BT-Verbindungsaufbau und PPM-Kalibrierungsfehler sein.**

---

## 2. Bluetooth — `Device not available`

### Symptom
`bluetoothctl info 00:16:94:2E:85:DB` → `Device not available` für alle Befehle.

### Ursache
BlueZ-Datenbank ist leer (`⚠ Keine gepaarten Geräte in BlueZ-Datenbank`).  
BT-Backup (v0.8.25) wurde noch nie ausgeführt, weil er einen erfolgreichen Connect voraussetzt — der bisher nicht zuverlässig klappte.

### Zustand BT-Agent
```
WARNING: BT agent: default-agent nicht bestätigt — Verbindung trotzdem versuchen
```
`bluetoothctl agent on` + `default-agent` schlägt reproduzierbar fehl. Der persistente bluetoothctl-Prozess (stdin-pipe, v0.8.14) bestätigt `agent on` nicht. Ohne registrierten Agent schlägt `pair` immer fehl, wenn das Gerät nicht bereits vertraut ist.

### Scan-Ergebnis
Beim BT-Scan wurden zwei Geräte gefunden:
- `06:88:6D:24:E5:F9` (random MAC, wahrscheinlich Smartphone)
- `C0:28:8D:FD:5A:B7` (Logitech-Gerät)

**Sennheiser HD 4.40BT (00:16:94:2E:85:DB) wird im Scan nicht gefunden** → Kopfhörer war beim Scan nicht im Pairing-Modus oder außer Reichweite.

### Auto-Restore beim Boot
Hat nicht gegriffen, weil noch kein Backup existiert. v0.8.25-Mechanismus ist korrekt, aber ohne erstes manuelles Pairing nicht nutzbar.

---

## 3. PPM-Kalibrierung schlägt fehl

### Symptom
Kalibrierungs-Button: "Kein automatischer Wert erkannt", auch nach Radio stoppen.

### Analyse
**v0.8.25-Fix** (cumulative PPM Regex) wurde deployed, aber:

1. RTL-SDR war bei allen Kalibrierungsversuchen belegt (`RTL-SDR busy: True | Prozesse: 2`) — FM oder DAB lief noch.
2. Bei gestopptem Radio: `rtl_test -p` läuft 30s, aber in manchen RTL-SDR-Versionen/Treibern gibt es keine `cumulative PPM`-Zeile in der Ausgabe, nur `real sample rate`.
3. Neuer Stick: noch unbekanntes Ausgabeformat.

**PPM-Kalibrierung ist kein kritischer Fehler** — Default 0 ppm bedeutet keine Korrektur, FM/DAB spielen trotzdem.

---

## 4. Gain-Einstellungen hörbar wirkungslos

**Erwartung:** Gain-Änderung FM 30 dB → 49 dB → spürbar mehr Rauschen/Verstärkung.  
**Realität:** Keine hörbare Änderung.

**Ursache:** Gain wird als `-g N` Parameter an `rtl_fm` übergeben, der Prozess läuft aber bereits. Settings.json wird aktualisiert, der laufende rtl_fm-Prozess ignoriert es. Die Änderung greift erst beim **nächsten Start** der Quelle.

**Fix:** Nach Gain-Änderung sollte die aktive Quelle automatisch neu gestartet werden, oder die WebUI muss explizit darauf hinweisen.

---

## 5. Diagnose-Lücken (was fehlt)

| Bereich | Fehlt |
|---|---|
| PulseAudio | `pactl set-default-sink` Status; ob Default Sink explizit gesetzt ist |
| amixer | Hex-Parsing für `0x00000001` Format |
| BT-Backup | Backup-Alter und letzte Restore-Zeit |
| Gain | Hinweis ob Neustart nötig für Wirksamkeit |
| Unterspannung | Detailausgabe `vcgencmd get_throttled` mit Bit-Erklärung |

---

## 6. GPT-Analyse — Bewertung

| GPT-Punkt | Korrekt? | Kommentar |
|---|---|---|
| "mpv hängt nicht an PulseAudio" | ❌ Falsch | mpv IST an PA angebunden (Diagnose als root bestätigt Sink-Input) |
| "pactl list sink-inputs leer → Fehler" | ⚠ Irreführend | User-pi verbindet sich mit falschem Socket (`/run/user/1000`) |
| "Falsche PulseAudio-Session" | ✅ Richtig | Aber als WebUI/Diagnose-Problem, nicht als Playback-Problem |
| "Default Sink leer = Problem" | ✅ Richtig | Echter Fehler, fix nötig |
| "Unterspannung relevant" | ✅ Richtig | 0x50000 ist kritisch für USB-Stabilität |
| "mpv fällt auf ALSA zurück" | ❌ Nicht belegt | Sink-Input ist sichtbar, kein ALSA-Fallback |

---

## 7. Prioritäten für v0.8.26

| Prio | Fehler | Fix |
|---|---|---|
| HOCH | Default Sink leer | `pactl set-default-sink` persistent in setup_bt_audio.sh |
| HOCH | amixer Hex-Parse-Bug | diagnose.py: `int(raw, 0)` statt String-Mapping |
| HOCH | BT Agent-Bestätigung | bluetooth.py: Agent-Bestätigungs-Logik überarbeiten |
| MITTEL | Gain nicht live | WebUI: Hinweis + optional auto-restart aktive Quelle |
| MITTEL | PPM keine Ausgabe | Längerer Timeout oder rtl_test Ausgabe direkt an WebUI streamen |
| NIEDRIG | pactl-Socket für User pi | Nur Diagnose-Schönheitsfehler, kein Playback-Bug |
| HARDWARE | Unterspannung 0x50000 | Besseres Netzteil — 5V/3A mit dickem Kabel |
