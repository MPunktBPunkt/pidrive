# Lab-Gate E-1: FM-Sender (vor jeder Antenne)

Stand: 2026-10-16 · Status: **offen** (noch kein Lauf)
Konzept: [KONZEPT-FM-TX.md](KONZEPT-FM-TX.md)

Ziel: erste gemessene Werte für Träger, Oberwellen, RDS und Nebenwirkungen am
Pi 4, bevor der Sender an eine Antenne darf. Die Ergebnisse gehen als Evidence
in `technology-audit` ein (erste R1-Feldwerte für `rpi-gpio-fm-tx`).

## Aufbau (geschirmt, keine Abstrahlung)

```text
GPIO 4 (Pin 7) ──[ optional Tiefpass fg≈110 MHz ]──[ 40 dB Dämpfung ]──┬── 50-Ω-Dummy-Load
GND   (Pin 9) ─────────────────────────────────────────────────────────┘
                                         └──[ weitere 20–30 dB ]── RTL-SDR (PiDrive selbst oder zweiter Stick)
```

- Pi in geschirmter Box bzw. HF-dichter Tüte, kein Draht am Pin außer Koax.
- Betriebsart: `pidrivectl fmtx mode lab --confirm`.
- RTL-Gain klein halten (`--gain 0`), sonst übersteuert der Stick und erzeugt
  eigene Harmonische.
- Zweiter Stick empfohlen: PiDrives eigener Stick misst den eigenen Sender,
  dabei laufen DAB/FM-Empfang nicht.

## Vorbereitung

```bash
sudo systemctl status pidrive-fmtx       # Dienst läuft, state=off
pidrivectl fmtx backend pifmrds
pidrivectl fmtx source tone              # 1-kHz-Dauerton
pidrivectl fmtx rds ps "PIDRIVE"
pidrivectl fmtx runtime 15
vcgencmd get_config gpu_freq             # rpitx: 250 erwartet
```

## Messpunkte

| # | Prüfung | Kommando / Vorgehen | Erwartung | Ergebnis |
|---|---|---|---|---|
| E1-1 | Träger 88,0 MHz | `pidrivectl fmtx freq 88.0 && pidrivectl fmtx selftest` | Träger erkannt | ☐ |
| E1-2 | Träger 90,0 MHz | dto. `90.0` | Träger erkannt | ☐ |
| E1-3 | Träger 93,0 MHz | dto. `93.0` | Pi-4-Grenze laut markondej | ☐ |
| E1-4 | Träger 100,0 MHz | dto. `100.0` | ggf. instabil auf Pi 4 | ☐ |
| E1-5 | 2. Harmonische ohne Tiefpass | `selftest` → `h2_rel_db` | Wert notieren (dB rel. Träger) | ☐ |
| E1-6 | 2. Harmonische mit Tiefpass | Tiefpass einsetzen, `selftest` | deutlich kleiner als E1-5 | ☐ |
| E1-7 | 3. Harmonische mit/ohne Tiefpass | Report `measurements[2]` | Wert notieren | ☐ |
| E1-8 | Frequenzgenauigkeit | `pidrivectl spectrum peek <f>` → `peak_f` (ppm-korrigiert) | Abweichung < 5 kHz | ☐ |
| E1-9 | RDS-Dekodierung | zweiter Stick: `rtl_fm -f 88.0M -M fm -s 171k -A std -l 0 -E deemp -r 171k - \| redsea` | PI D3A2, PS PIDRIVE, RT | ☐ |
| E1-10 | RDS live | `pidrivectl fmtx rds rt "Test 123"` während E1-9 | RT ändert sich ≤ 10 s | ☐ |
| E1-11 | Spiegel Webradio | `fmtx source mirror`, Webradio starten | Ton am Empfänger, 0,5–2 s Latenz | ☐ |
| E1-12 | Spiegel DAB | DAB-Sender nach TX-Start neu wählen | Ton am Empfänger (welle-cli über Pulse) | ☐ |
| E1-13 | Klinke parallel | Kopfhörer an Klinke während TX | Störungen notieren (PWM) | ☐ |
| E1-14 | HDMI / BT / ESP parallel | jeweils Ausgang wählen | kein Abbruch, Ton auf beiden | ☐ |
| E1-15 | CPU / Throttling | `top`, `vcgencmd get_throttled` über 10 min | < 30 % CPU, throttled=0x0 | ☐ |
| E1-16 | Laufzeitlimit | `fmtx runtime 1`, starten | Stopp nach 60 s, Fehlertext „Laufzeitlimit“ | ☐ |
| E1-17 | Stopp nach kill -9 | `sudo kill -9 $(pidof pi_fm_rds)` | Watchdog-Neustart (max. 3), danach `error` | ☐ |
| E1-18 | Dienst-Stopp nach Absturz | `sudo systemctl kill -s KILL pidrive-fmtx` | `ExecStopPost` setzt GPIO 4 auf Eingang, kein Träger mehr | ☐ |
| E1-19 | DAB-Konflikt | DAB 5B spielen, `fmtx freq 88.0`, Start | Start blockiert (2× 88,0 = 176,0 MHz in 5B) | ☐ |
| E1-20 | RTL-Konflikt | UKW-Empfang 88,4, `fmtx freq 88.4`, Start | Start blockiert (Δ ≤ 1 MHz) | ☐ |
| E1-21 | PMR446 nur Labor | `fmtx mode cable --confirm`, `fmtx band pmr446` | Start abgelehnt | ☐ |
| E1-22 | PMR446 Labor (rpitx) | `fmtx mode lab --confirm`, `fmtx band pmr446 --channel 8`, Start | Träger 446,09375 MHz am Dummy-Load | ☐ |
| E1-23 | Chip-Backend (falls Modul da) | `fmtx backend chip`, I2C-Adresse prüfen (`i2cdetect -y 1`) | Träger + RDS, Oberwellen ≪ GPIO | ☐ |
| E1-24 | Boot-Ansage | `fmtx freq 91.0`, `fmtx autostart boot-only`, Consent lab, `sudo reboot`; Empfänger auf 91,0 MHz | ca. 3 s nach `boot_phase=steady` „PiDrive is starting“ (ohne WAV: 1-kHz-Beep), RT „PiDrive is starting“, danach Träger aus, kein Fehlertext; mit `always` danach Quelle hörbar; zweiter `systemctl restart pidrive-fmtx` ohne erneute Ansage | ☐ |

## Auswertung

- `selftest` schreibt `/tmp/pidrive_fmtx_selftest.json`. Die RTL-Pegel sind
  relativ (dBFS bei festem Gain), **kein kalibrierter Leistungswert**.
  Absolutwerte nur mit kalibriertem Messempfänger/Spektrumanalysator.
- Freigabe für Antennenbetrieb erst, wenn E1-6 einen Tiefpass belegt und die
  Rechtslage (SRD-Grenzwert) geklärt ist.

## Evidence-Vorlage (technology-audit)

```yaml
evidence_id: EVID-FMTX-PIDRIVE-2026-xx-xx-001
tech_slug: rpi-gpio-fm-tx
setup: Pi 4B, PiFmRds 2707ecc, GPIO4, 40 dB + Dummy-Load, RTL-SDR R820T gain 0
measurements:
  carrier_88_0: { detected: null, freq_err_khz: null }
  h2_rel_db_no_lpf: null
  h2_rel_db_lpf: null
  rds_decoded: null
  jack_pwm_interference: null
  cpu_percent: null
  stop_after_kill9: null
status: UNKNOWN
```
