# Scanner, Spektrum & PMR-Dauerüberwachung

**Stand:** v0.11.155 · 2026-09-21  
**Zielgruppe:** Entwickler  
**Betriebs-Kurzreferenz:** [`../betrieb/PMR-MONITOR.md`](../betrieb/PMR-MONITOR.md) · Spektrum-CLI: [`../betrieb/SPECTRUM-CLI.md`](../betrieb/SPECTRUM-CLI.md)

Dieses Kapitel beschreibt, **wie der RTL-SDR-Scanner aufgebaut ist**, wo der Code
liegt, und wie die **PMR446-Dauerüberwachung** (Backend-Detektor) reagiert —
inkl. State Machine, WebUI und Fehlerpfaden.

---

## 1. Zwei Schichten: Scanner vs. Detektor

| Schicht | Zweck | Audio? | Stick belegt |
|---------|--------|--------|--------------|
| **Scanner (manuell)** | Einmal-Scan / Kanal wählen / NBFM hören | Ja (`rtl_fm` → mpv) | Während Wiedergabe |
| **Spektrum-Capture** | FFT-Snapshot / Peak-Scan / Kanalenergie | Nein | Kurz (`rtl_sdr`) |
| **PMR-Monitor (Detektor)** | Dauerhaft lauschen, Treffer loggen, optional Autotune | Nur bei Hit + Autotune | Intermittierend Capture, dann ggf. `rtl_fm` |

Wichtig: Die WebUI-Checkbox **„Überwachung: bei Aktivität umschalten“** ist nur das
Setting `scanner_pmr_autotune`. Der laufende Detektor ist der Button
**Dauerbeobachtung** → Trigger `pmr_monitor_start` / `pmr_monitor_stop` im Core.

---

## 2. Dateikarte (kanonische Pfade)

```
pidrive/
├── modules/radio/
│   ├── scanner.py      ← Bänder, Kanalwahl, rtl_fm-Playback, PMR-Monitor-Loop
│   ├── spectrum.py     ← FFT, BandProfile, watch_channels(), UKW-Peaks
│   ├── rtlsdr.py       ← Lock, Diagnose, usb_reset (authorized-Cycle)
│   └── fm.py           ← UKW-Broadcast (wbfm) — getrennt vom Scanner
├── trigger/
│   └── td_scanner.py   ← Trigger: scan_*, pmr_monitor_*, scanner_stop
├── modules/
│   └── source_state.py ← Transitionen, rtl_capture_gate(), refresh_transition()
├── cli/cli.py          ← pidrivectl scanner … / spectrum …
├── web/
│   ├── app.py          ← /api/scanner/*, /api/spectrum/capture, /api/rtlsdr
│   └── templates/
│       ├── index.html  ← Scanner-Tab (Detektor-UI)
│       └── rf-tools.html ← Spektrum-Plot / RTL-Diagnose
└── settings.py         ← scanner_gain, ppm, scanner_pmr_*
```

Kanonischer Pfad: `modules/radio/scanner.py` (keine Compat-Shims mehr).

| Thema | Primärdatei | Einstieg |
|-------|-------------|----------|
| Kanaltabellen PMR/Freenet/… | `scanner.py` | `PMR446_CHANNELS`, `BANDS` |
| Einmal-Scan / next/prev | `scanner.py` + `td_scanner.py` | `scan_next:pmr446` |
| Kanal hören | `scanner.py` | `set_channel` / `play_freq` → `rtl_fm -M fm` |
| FFT / Peak-Detektion | `spectrum.py` | `SpectrumWatcher.watch_channels` |
| Dauer-Detektor | `scanner.py` | `_pmr_monitor_loop`, `start_pmr_monitor` |
| USB freigeben / Owner | `rtlsdr.py` | `recover_busy_device`, `request_owner`, `find_rtl_processes` |
| Quellen-Spiegel | `source_state.py` | `begin_transition` / `rtl_capture_gate` |
| CLI | `cli/cli.py` | `scanner monitor …`, `spectrum scan` |
| Web Capture | `web/app.py` | `api_spectrum_capture` (`preempt_monitor`) |
| Review-Maßnahmen | [`SCANNER-REVIEW-MASSNAHMEN.md`](SCANNER-REVIEW-MASSNAHMEN.md) | P0–P3 Abschluss |

---

## 3. Hardware-Pfad

```
Walkie (PMR446) ──RF──► RTL2838 Stick ──USB──► Raspberry Pi
                              │
              ┌───────────────┼────────────────┐
              ▼               ▼                ▼
         rtl_sdr          rtl_fm           welle-cli
         (I/Q Capture)    (NBFM Audio)     (DAB — anderer Pfad)
              │               │
              ▼               ▼
         spectrum.py      mpv (Pulse)
         FFT → Kanäle
```

- **Ein Stick, exklusiv.** Lock: `/tmp/pidrive_rtlsdr.lock` (+ Prozess-Check).
- Monitor und Spektrum nutzen `rtl_sdr`; Hören nutzt `rtl_fm`.
- DAB (`welle-cli`) und Monitor dürfen nicht parallel den Stick halten —
  der Monitor **preempted** fremde RTL-Quellen.

---

## 4. Scanner-Funktionen (manuell)

### 4.1 Bänder

In `scanner.BANDS` u. a.:

| Band-ID | Typ | Beispiel |
|---------|-----|----------|
| `pmr446` | 16 Kanäle, 12,5 kHz | 446.00625 … 446.19375 MHz |
| `freenet` | 6 Kanäle | ~149 MHz |
| `lpd433` | 69 Kanäle | 433 MHz |
| `cb` | CB-Kanäle | 26/27 MHz |
| `vhf` / `uhf` | Frequenzraster | Range + Step |
| `fm` | UKW-Scanner-Hilfen | getrennt von `fm.py`-Broadcast |

### 4.2 Trigger → Aktion

```
CLI / WebUI / Menü
    → /tmp/pidrive_cmd  (z.B. scan_setch:pmr446:4)
    → main_core.check_trigger()
    → trigger_dispatcher → td_scanner.handle()
    → scanner.set_channel() / scan_next() / …
    → source_state.begin_transition(…, "scanner")
    → rtl_fm + mpv
    → commit_source("scanner") · end_transition()
```

Wichtige Trigger (`td_scanner.py` / `constants.py`):

| Trigger | Wirkung |
|---------|---------|
| `scan_setch:BAND:N` | Kanal N auf Band |
| `scan_next:BAND` / `scan_prev:BAND` | Suchlauf, Ergebnis `/tmp/pidrive_scan_result.json` |
| `scanner_stop` | Audio stoppen **und** Monitor stoppen |
| `pmr_monitor_start` / `pmr_monitor_stop` | Backend-Detektor |
| `rtlsdr_reset` | `rtlsdr.usb_reset()` (td_hardware) |

Audio-Hinweis: Schmalband-PMR = `rtl_fm -M fm`; UKW-Broadcast = `-M wbfm` (`fm.py`).

---

## 5. Spektrum-Engine (`spectrum.py`)

### 5.1 Rollen

1. **UKW-Peak-Scan** — `scan_fm_channels` / CLI `pidrivectl spectrum scan`
2. **Kanalisierte Überwachung** — `BandProfile` + `watch_channels()` für PMR/Freenet
3. **Web-Snapshots** — `/api/spectrum/capture` (range / snapshot / band=pmr446)

### 5.2 PMR446-Profil (Defaults)

`PMR446_PROFILE` in `spectrum.py`:

- 16 Kanäle, Sample-Rate 256 kHz, FFT 2048, Frame ~80 ms  
- Default-Trigger im Profil: `trigger_on_db=14`  
- **Monitor überschreibt** das beim Watch mit strengeren Werten (siehe §6)

`watch_channels()` stellt sicher, dass der **effektive** `FFTProcessor` dem
Profil-`fft_size` entspricht (`build_default_watcher` startet mit Default 512;
Mismatch würde nur die ersten 512 Samples nutzen — siehe
[`SCANNER-REVIEW-MASSNAHMEN.md`](SCANNER-REVIEW-MASSNAHMEN.md)).

`ChannelAnalyzer` berechnet pro Kanal `relative_db` (gegenüber Rauschboden),
`score`, `confidence`. Ein Kanal gilt als **gefunden**, wenn über genug Frames
`relative_db ≥ trigger_on_db`.

### 5.3 Gate vor Capture

`source_state.rtl_capture_gate()`:

1. aktive Transition → blockieren  
2. Quelle `dab` / `fm` / `scanner` → blockieren  
3. PMR-Monitor läuft (Thread **oder** `/tmp/pidrive_pmr_monitor.json`) → blockieren  

`/api/spectrum/capture` setzt standardmäßig **`preempt_monitor=1`**: Monitor stoppen,
warten, dann Snapshot. Abschalten: `preempt_monitor=0`.

---

## 6. PMR-Dauerüberwachung (Backend-Detektor)

### 6.1 Startpfad

```
WebUI „Dauerbeobachtung“ / CLI scanner monitor start
    → Settings: scanner_pmr_autotune, scanner_pmr_hold_s
    → pmr_monitor_start
    → td_scanner: stoppt Webradio/DAB/FM
    → scanner.start_pmr_monitor(...)
         · kill welle-cli / rtl_* , Lock löschen
         · force_end_transition + commit_source("idle")
         · Thread "pmr-monitor" → _pmr_monitor_loop
```

### 6.2 Hauptschleife (`_pmr_monitor_loop`)

```
while not stop:
    if source_state.in_transition():
        sleep; continue          # fremde Quellenwechsel respektieren

    if radio_type in {DAB, FM, WEB, …}:
        stop fremde Quelle       # preempt
        commit_source("idle")
        continue

    profile = PMR446_PROFILE mit Monitor-Overrides:
        watch_seconds ≈ 2.0
        trigger_on_db  = 25.0    # ← Treffer-Schwelle (wichtig!)
        trigger_off_db = 14.0
        min_active_frames = 1
        gain = scanner_gain oder 36 (nie Auto -1)

    result = watcher.watch_channels(profile)

    if Fehler (busy / Timeout):
        force_free_rtl → nach 3× usb_reset
        continue

    cycles++

    if result.found und best_candidate:
        hits++
        log event=activity
        if autotune:
            begin_transition(pmr_monitor:pmr446, scanner)
            set_channel(...) → rtl_fm hören
            commit_source("scanner")
            hold_s Sekunden mit refresh_transition()   # > STALE_TIMEOUT
            end_transition(); scanner.stop()
            log listen_end
    else:
        last_event = scan
        optional peek-Log wenn stärkster Kanal ≥ 6 dB
            (Diagnose — kein Treffer!)
```

### 6.3 Schwellen — warum „kein Treffer“ trotz Senden

| Signal | Bedeutung |
|--------|-----------|
| `peek` ~+18…20 dB, `triggered:false` | Unter Monitor-Trigger; oft Dauerrauschen K8/K9 |
| `activity` + `relative_db ≥ 25` | **Echter Treffer** |
| Nahfeld-Walkie (Erfahrung) | oft **+40…+60 dB** |

Monitor-Konstanten in `scanner.py`:

```text
PMR_MONITOR_TRIGGER_ON_DB  = 25.0
PMR_MONITOR_TRIGGER_OFF_DB = 14.0
PMR_MONITOR_WATCH_S        = 2.0
PMR_MONITOR_HOLD_S         = 15.0
PMR_MONITOR_DEFAULT_GAIN   = 36
```

Kommentar im Code: *9–20 dB = Dauer-Falsch (K8/K9)*.

### 6.4 Status & Log

| Datei | Inhalt |
|-------|--------|
| `/tmp/pidrive_pmr_monitor.json` | `running`, `cycles`, `hits`, `last_event`, `error`, … |
| `/var/log/pidrive/pmr_monitor.jsonl` | Events: `start`, `peek`, `activity`, `tuned`, `listen_end`, `error`, `usb_reset`, `heartbeat`, `preempt_source`, … |

Web: `GET /api/scanner/pmr-monitor?n=20`  
CLI: `pidrivectl scanner monitor status|log`

### 6.5 State Machine beim Autotune

| Phase | `source_current` | `transition` |
|-------|------------------|--------------|
| Scan-Idle | `idle` | nein |
| Hit → Tune | `scanner` nach commit | ja (Owner `pmr_monitor:pmr446`) |
| Hold | `scanner` | ja, `refresh_transition()` alle ~0,4 s |
| Ende | idle nach Stop | nein |

Ohne `refresh_transition` würde der Stale-Watchdog (`STALE_TIMEOUT_S=12`) die
Transition bei Hold=15 s mitten im Hören löschen.

`begin_transition` **False** → kein Tune (`tune_blocked` im Log).

---

## 7. WebUI-Verhalten

**Scanner-Tab** (`web/templates/index.html`):

- Button startet/stoppt **Backend**-Monitor (nicht mehr Browser-Capture-Loop).
- Statuszeile `pmrBackendStatus` pollt `/api/scanner/pmr-monitor` alle 2 s.
- „Scan einmal“: Capture mit `preempt_monitor=1` (Detektor kurz aus, Snapshot).
- Autotune-Checkbox schreibt nur `scanner_pmr_autotune`.

**RF-Tools:** Spektrum-Plot; Capture preempted Monitor standardmäßig.

---

## 8. Fehler & Recovery

| Symptom | Typische Ursache | Reaktion |
|---------|------------------|----------|
| `Device busy` / `authorized=0` | USB soft-getrennt | `usb_reset` → authorized 0→1 |
| `rtl_sdr Timeout` | Stick hängt | Auto: hard-Recover + Retry, dann USB-Reset (60 s Cooldown); manuell: RF-Tools **Reset** / `rtlsdr_reset` |
| Diagnose `Operation not permitted … json` | `/tmp` Sticky, root vs pidrive | In-Place-Write (v0.11.155) |
| Spektrum 409 „PMR-Monitor aktiv“ | Gate | `preempt_monitor=1` (Default) |
| hits=0, viele peeks ~19 dB | unter Trigger 25 dB | näher senden / Gain / Trigger |

`rtlsdr.usb_reset()`: sysfs-Pfad über `idVendor=0bda`, dann authorized-Cycle;
Fallback `usbreset` + erzwungenes `authorized=1`.

---

## 9. Settings

| Key | Default / typisch | Wirkung |
|-----|-------------------|---------|
| `scanner_gain` | 25–36 | Monitor: Auto(-1) → 36 |
| `ppm_correction` | kalibriert (z. B. 49) | Frequenzkorrektur |
| `scanner_pmr_autotune` | false / CLI-start true | Hit → umschalten |
| `scanner_pmr_hold_s` | 15 | Hörzeit nach Tune |
| `scanner_squelch` | ~50 | nur `rtl_fm`-Audio |
| `scanner_use_spectrum` | — | ältere Scan-Hilfen |

---

## 10. Tests

| Test | Was |
|------|-----|
| `tests/unit/test_source_spectrum_pmr.py` | Gate, refresh vs. Stale, Tune-Block |
| `tests/unit/test_rtlsdr_usb_reset.py` | sysfs-Pfad, kein dict.splitlines |
| `tests/unit/test_source_state.py` | Transitionen allgemein |
| Live | `pidrivectl scanner monitor log` + Walkie |

---

## 11. Schnelldiagnose

```bash
pidrivectl scanner monitor status
pidrivectl scanner monitor log -n 30
pidrivectl source state
cat /tmp/pidrive_pmr_monitor.json
# Treffer?
grep '"event":"activity"' /var/log/pidrive/pmr_monitor.jsonl | tail
# Stick
for d in /sys/bus/usb/devices/*; do
  [ -f "$d/idVendor" ] || continue
  [ "$(cat $d/idVendor):$(cat $d/idProduct)" = "0bda:2838" ] || continue
  echo "$d authorized=$(cat $d/authorized)"
done
```

Echter Treffer sieht z. B. so aus:

```json
{"event":"activity","ch":4,"relative_db":60.01,"action":"tune","freq_mhz":446.04375,…}
{"event":"tuned","ch":4,"hold_s":15.0,…}
{"event":"listen_end","ch":4,…}
```

---

## 12. Verwandte Docs

| Doc | Fokus |
|-----|--------|
| [`DEVELOPER_GUIDE.md`](DEVELOPER_GUIDE.md) | Wo liegt welcher Code |
| [`ZUSTANDSMASCHINE.md`](ZUSTANDSMASCHINE.md) | `source_state` allgemein |
| [`RUNTIME_FLOWS.md`](RUNTIME_FLOWS.md) | FM/Scanner-Laufzeitpfade |
| [`../betrieb/PMR-MONITOR.md`](../betrieb/PMR-MONITOR.md) | CLI-Kurzreferenz |
| [`../betrieb/SPECTRUM-CLI.md`](../betrieb/SPECTRUM-CLI.md) | UKW spectrum CLI |
| [`../betrieb/TROUBLESHOOTING.md`](../betrieb/TROUBLESHOOTING.md) | authorized=0, Diagnose-Write |
| [`SCANNER-REVIEW-MASSNAHMEN.md`](SCANNER-REVIEW-MASSNAHMEN.md) | Review-Nachbewertung, P0–P3 |

---

## 13. Airband (AM) — Phase 1–3

Manueller Empfang im Band **118.000–136.975 MHz** mit expliziter Modulation `am`,
**lokale Presets**, und **Preset-Scan** (Signal-Suche).

| | |
|--|--|
| Band-ID | `airband` in `scanner.BANDS` |
| Modulation | `rtl_fm -M am` via `play_freq(..., modulation="am")` |
| Schritt | 25 kHz (`scan_step:airband:±0.025`) |
| Presets | `config/airband_stations.json` → `ch` / next / prev |
| Preset-Scan | `scan_next:airband` / `scan_prev:airband` — Detect mit `-M am` |
| Startfrequenz | 121.500 (Emergency) |
| CLI | `scanner airband list\|ch N\|freq F\|next\|prev\|scan` |
| Trigger | `scan_setch:airband:N`, `scan_setfreq:airband:<mhz>`, `scan_up/down:airband`, `scan_next/prev:airband` |
| WebUI | Scanner-Tab → Airband-Karte + Presets + **Suchen** |
| API | `GET /api/scanner/airband-stations` |
| Setting | `scanner_airband_last_freq` |

**Noch nicht:** Dauer-Monitor analog PMR, Spektrum-Profil über ganzes Airband (Span zu groß).  
Zentrale Runtime-Hilfe: `scanner._get_band_runtime(band_id)` → `modulation` / `audio_profile` / `bw`.  
Presets neu laden: `scanner.refresh_airband_channels()` (auch bei jedem `_get_channels("airband")`).
