# pidrivectl scanner monitor — PMR446 Dauer-Überwachung

**Stand:** v0.11.155 · 2026-09-21

> **Architektur (ausführlich):** [`../architektur/SCANNER-PMR.md`](../architektur/SCANNER-PMR.md)
> — Dateikarte, Monitor-Schleife, Trigger-Schwellen, State Machine, WebUI.

Hintergrund-Detektor: spektrum-basiert auf PMR446 lauschen, Treffer ins JSONL-Log
schreiben, optional auf den Kanal umschalten (Autotune).

## CLI

```bash
pidrivectl scanner monitor status          # läuft? cycles/hits/peek/latenz
pidrivectl scanner monitor start           # starten (Default: mit Autotune)
pidrivectl scanner monitor start --no-tune # nur loggen, nicht umschalten
pidrivectl scanner monitor start --hold 20 # Hörzeit nach Treffer (Sekunden)
pidrivectl scanner monitor start --trigger-on 18   # Lab: niedrigere Hit-Schwelle
pidrivectl scanner monitor start --trigger-off 12
pidrivectl scanner monitor start --watch 0.8       # schnelleres Watch-Fenster
pidrivectl scanner monitor stop
pidrivectl scanner monitor log             # letzte Activity-Events
pidrivectl scanner monitor log -n 80
```

Hilfe: `pidrivectl scanner monitor -h` · `pidrivectl scanner monitor start -h`

## Status & Log

| Pfad | Inhalt |
|------|--------|
| `/tmp/pidrive_pmr_monitor.json` | Live-Status inkl. peek/activity/error/latenz/`monitor_effective_state` |
| `/var/log/pidrive/pmr_monitor.jsonl` | Event-Log (`peek`, `activity`, `tuned`, `error`, `usb_reset`, …) |

WebUI: Scanner-Tab zeigt Monitor-Status + Debugzeile; Trigger-dB einstellbar.
Peek unter Trigger markiert den Kanal (grün), Activity erst ab `trigger_on_db`.

Review-Maßnahmen P0–P3: [`../architektur/SCANNER-REVIEW-MASSNAHMEN.md`](../architektur/SCANNER-REVIEW-MASSNAHMEN.md)
(umsetzbar erledigt; optional offen: persistenter Mehrprozess-IQ-Streamer).

## Settings (`config/settings.json`)

| Key | Bedeutung | Default |
|-----|-----------|---------|
| `scanner_pmr_autotune` | Bei Hit auf Kanal umschalten | `false` (CLI-`start` setzt `true`, außer `--no-tune`) |
| `scanner_pmr_hold_s` | Hörzeit nach Tune | `15` |
| `scanner_pmr_trigger_on_db` | Hit-Schwelle relativ Noise | `25` (Lab oft `16`–`20`) |
| `scanner_pmr_trigger_off_db` | Hysterese unter Trigger | `14` |
| `scanner_pmr_watch_s` | Watch-Fenster pro Zyklus | `1.0` (0.5–2.5) |
| `scanner_gain` | Gain; Monitor ersetzt Auto(`-1`) durch festen Nahfeld-Gain | typ. `25`–`36` |
| `ppm_correction` | Quarzkorrektur | kalibriert |

## State Machine (`source_state`)

| Phase | Erwartung |
|-------|-----------|
| Scan-Idle | `source_current=idle`, keine Transition; Capture pausiert wenn `in_transition()` |
| Autotune-Hit | `begin_transition(pmr_monitor:…, scanner)` — bei `False` kein Tune |
| Listening | `commit_source("scanner")`, Hold mit `refresh_transition()` (Hold > Stale-Timeout) |
| Listen-Ende | `end_transition()` + Scanner-Stop |
| Spektrum parallel | `rtl_capture_gate()`; Standard `preempt_monitor=1` stoppt Detektor und nimmt Snapshot |

WebUI Scanner-Tab: Button **Dauerbeobachtung** steuert den Backend-Detektor
(`pmr_monitor_start/stop`), Statuszeile „Backend-Detektor AKTIV …“.

## Recovery / bekannte Fehler

Ab v0.11.154 sucht `rtlsdr.usb_reset()` den Stick **primär über sysfs**
(`idVendor=0bda`) und setzt danach zwingend `authorized=1`.

Früherer Bug: `_run(["lsusb"])` liefert ein **dict**; `usb_reset` rief
`.splitlines()` darauf auf → Pfad-Suche scheiterte, Fallback `usbreset` ließ den
Stick bei `authorized=0` → Dauer-`Device busy` / `usb_claim_interface`.

Manuell freigeben:

```bash
# sysfs (als root / via Core-Trigger)
echo rtlsdr_reset > /tmp/pidrive_cmd
# oder:
for d in /sys/bus/usb/devices/*; do
  [ -f "$d/idVendor" ] || continue
  [ "$(cat $d/idVendor):$(cat $d/idProduct)" = "0bda:2838" ] || continue
  echo 1 | sudo tee "$d/authorized"
done
pidrivectl scanner monitor start --no-tune
```

Siehe auch [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md) § RTL `authorized=0`.
