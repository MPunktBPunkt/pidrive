# Review: FM-/AM-Empfang vs. RTL2832U-Stick-Dokumentation

**Datum:** 2026-09-25  
**PiDrive-Stand:** v0.11.167 (lokal; PPM-UI/Live-Status)  
**Bezugsdokument:** [`rtl2832u Stick`](./rtl2832u%20Stick) (Fasizi ELA0065 / RTL2832U + R820T2, GPT-Entwicklerdoku)  
**Ergänzende Messungen:** [`../betrieb/UKW-GAIN-SCAN-2026-09-19.md`](../betrieb/UKW-GAIN-SCAN-2026-09-19.md), Antennenvergleich 2026-09-22  

## 1. Ziel

Prüfen, was aus der Stick-/DSP-Dokumentation in PiDrive **bereits umgesetzt** ist, was mit **geringem Aufwand** verbesserbar ist, und was für den aktuellen Stack (`rtl_fm` | `mpv`) **zu aufwendig** oder falsch priorisiert wäre.

Kein Auftrag zur Implementierung — Entscheidungsgrundlage.

---

## 2. Durchgesehene Sourcedateien

### 2.1 Kern: Empfang / Demod

| Datei | Rolle im Review |
|-------|-----------------|
| `pidrive/modules/radio/fm.py` | UKW-Wiedergabe: `rtl_fm -M wbfm`, Gain/PPM, HP/LP via mpv, Suchlauf |
| `pidrive/modules/radio/scanner.py` | Airband/AM, PMR/NFM, `rtl_fm`-Kommandoaufbau, Live-Tune (Gain/SR/HP/LP), Monitor |
| `pidrive/modules/radio/rtlsdr.py` | USB-Erkennung, Locking, DVB-Module, Diagnose, Reset |
| `pidrive/modules/radio/spectrum.py` | I/Q via `rtl_sdr`, PPM/Gain für Spektrum |
| `pidrive/modules/radio/dab_play.py` | PPM nur Session-Meta; `welle-cli` ohne PPM-Flag |

### 2.2 Settings / Persistenz / Trigger / CLI

| Datei | Rolle |
|-------|--------|
| `pidrive/settings.py` | Defaults: `fm_gain`, Airband-Gain/SR/HP/LP, `ppm_correction`, FM-Audiofilter |
| `pidrive/config/airband_stations.json` | lokale Airband-Presets (Pfad aus scanner.py) |
| `pidrive/trigger/td_hardware.py` | `ppm:`, `fm_gain:`, `dab_gain:` → `save_settings` |
| `pidrive/trigger/td_scanner.py` | `set_ppm:`, Airband-Tune-Steps, Squelch |
| `pidrive/cli/cli.py` | `pidrivectl ppm status\|set\|calibrate` |
| `pidrive/web/shared/constants.py` | erlaubte Cmd-Prefixe (`ppm:`, …) |

### 2.3 WebUI / Installer / Betrieb

| Datei | Rolle |
|-------|--------|
| `pidrive/web/app.py` | `/api/ppm_calibrate/*`, Scanner-Settings-API, Runtime-Settings |
| `pidrive/web/templates/rf-tools.html` | PPM setzen / Auto-Kalibrierung mit Live-Status |
| `pidrive/web/templates/index.html` (Player) | Airband/FM Live-Tune-Steuerung (über Cmds) |
| `install.sh` | `rtl-sdr`, `usbutils`, DVB-Blacklist (`dvb_usb_rtl28xxu` …) |
| `docs/betrieb/UKW-GAIN-SCAN-2026-09-19.md` | Praxis-Gain 20–30 dB, Übersteuerung bei 40+ |
| `docs/referenz/rtl2832u Stick` | Referenzprofile WBFM/Airband, DSP-Pipelines, Kalibrierebenen |

**Nicht** als vollständige Code-Review gelesen (nur Randbezug): `dab_scan.py`, `dab.py`, Pump/ESP, Bluetooth.

---

## 3. Ist-Zustand: PiDrive-Pipelines

### 3.1 UKW-FM (`fm.play_station`)

```text
rtl_fm -M wbfm -f <Hz> -s 250000 -r 32000 [-g fm_gain] [-p ppm] -A fast
  → Pipe → mpv (raw PCM 32 kHz mono) + lavfi highpass/lowpass
```

| Parameter | Default (settings) | Code |
|-----------|-------------------|------|
| Modus | WBFM | fest |
| Intern/Demod `-s` | **250000** | hart in `fm.py` |
| Audio out `-r` | 32000 | hart |
| Gain | **25** (`fm_gain`) | Settings / UI |
| PPM | `ppm_correction` (Host) | Settings / UI / CLI |
| Audio HP/LP | **60 Hz / 12 kHz** | `fm_hp_hz` / `fm_lp_hz`, live stepbar |
| Deemphasis | (implizit in `rtl_fm` wbfm) | nicht konfigurierbar |
| Offset-Tuning | — | **nicht** |
| Stereo / RDS | — | bewusst nein (`fm.py` Kommentar) |

Suchlauf FM: kurz `rtl_fm … -s 200000 -l 30` + Byte-Zähler (`fm.py`).

### 3.2 Airband-AM (`scanner` Modulation `am`)

```text
rtl_fm -M am -f <Hz> -s <SR> [-p ppm] [-g gain] [-l squelch]
       -F 9 -A std -t 1
  → mpv + lavfi highpass/lowpass (Sprache)
```

| Parameter | Default | Anmerkung |
|-----------|---------|-----------|
| Band-Scan-BW (Monitor) | **10 kHz** (`BANDS["airband"]["bw"]`) | nahe Doku 8–10 kHz |
| Listen `-s` | **24000** (`scanner_airband_sample_rate`) | Stufen 12…32 kHz |
| Gain | **45** (`scanner_airband_gain`) | deutlich höher als Doku 10–12,5 |
| HP/LP | **250 / 3500 Hz** | Doku: 250 / ~3000 |
| Squelch Listen | **0** | bewusst offen für ATIS |
| Demod | Envelope (`rtl_fm -M am`) | kein Sync-AM |
| PPM | global `ppm_correction` | ja |

### 3.3 Spektrum / Diagnose

- `spectrum.py`: `rtl_sdr` + PPM/Gain; UKW-Messung empfiehlt Gain 20–30 (Betrieb-Doku).
- PPM-Kalibrierung: `rtl_test -p`, WebUI Live-Status, Persistenz über `ppm:`.
- DVB-Treiber: Blacklist in `install.sh` + Diagnose in `rtlsdr.py`.

---

## 4. Abgleich mit dem Stick-Dokument

Legende: **✓** umgesetzt · **◐** teilweise · **○** offen/machbar · **✕** zu aufwendig / Out-of-Scope für `rtl_fm`-Stack

### 4.1 Kalibrierung & Geräteverwaltung (Kap. 11, 31, 37)

| Doku-Punkt | Status | PiDrive |
|------------|--------|---------|
| DVB-Kernel vs. Userland trennen (Blacklist) | ✓ | `install.sh`, `rtlsdr.py` |
| USB-Erkennung / Tools (`lsusb`, `rtl_test`, `rtl_fm`) | ✓ | + sysfs-Fallback ohne `lsusb` |
| PPM grob via `rtl_test -p` | ✓ | WebUI + CLI; Live-Fortschritt |
| PPM persistent pro Host | ✓ | `ppm_correction` in `settings.json` |
| Stick-Profile / Serial→PPM-Map | ○ | bewusst ein Wert/Host (Stand 2026-09-25) |
| Warmup / Mehrpunkt-PPM / Restoffset pro Band | ○ / ✕ | Messprotokoll möglich; Band-Restoffset lohnt erst bei Hz-Genauigkeit |
| Gain-Sweep / A/B mit Metriken | ◐ | UKW-Gain-Scan-Doku + Spektrum-CLI; keine automatisierte SINAD-Suite |

### 4.2 UKW-FM (Kap. 22, 25, 26, 35)

| Doku-Empfehlung („WBFM Mono robust“) | Status | Ist vs. Soll |
|--------------------------------------|--------|--------------|
| Sample/Kanal ~150–180 kHz bzw. Test `-s 170k` | ◐ | Play: **250 kHz**; Scan: 200 kHz — etwas breit |
| Manual Gain ~14 dB (nicht max) | ◐ | Default **25** (passt zu eigener UKW-Messung 20–30; Doku-14 ist konservativer) |
| Offset-Tuning an | ○ | nicht gesetzt |
| Deemphasis 50 µs | ◐ | `rtl_fm` wbfm intern; nicht als Setting |
| Audio-LP ~15 kHz | ◐ | Default **12 kHz** (robuster bei Rauschen); 15 kHz in Steps wählbar |
| Stereo / RDS / eigene FIR-Pipeline | ✕ | Architekturwechsel (I/Q + Decoder) |

### 4.3 Airband-AM (Kap. 23, 25, 27, 35)

| Doku-Empfehlung | Status | Ist vs. Soll |
|-----------------|--------|--------------|
| FM-Notch / externe Entlastung | ○ Hardware | Software kann Blocking nicht ersetzen |
| Manual Gain ~10–12,5 dB | ○ | Default **45** — Hauptabweichung; Übersteuerung/IM-Risiko |
| Kanal ~8–10 kHz (25-kHz-Raster) | ◐ | Monitor-BW 10 kHz ✓; Listen-`-s` Default 24 kHz eher breit |
| Audio HP 250 / LP ~3 kHz | ◐ | 250 / **3500**; LP-Steps bis 3000 vorhanden |
| Envelope-Demod | ✓ | `rtl_fm -M am` |
| Sync-AM | ✕ | braucht eigenen Demod |
| 8,33-kHz-Profil (5–7 kHz BW) | ○ | kein separates Profil; SR-Stufen erlauben Annäherung |

### 4.4 NFM/PMR (Kap. 24, Rand)

| Doku | Status |
|------|--------|
| Schmalband, Gain manuell, Audio ~3 kHz | ◐ | PMR-Pfad in `scanner.py` mit festen Defaults (Gain oft 36, AF 250–3700) — nicht Fokus dieses Reviews |

### 4.5 Optimierungshebel der Doku (Kap. 36) — Ranking für PiDrive

1. **korrekter Gain** — FM schon brauchbar; **Airband-Default zu hoch**  
2. **Frequenzkalibrierung (PPM)** — erledigt / UI ok  
3. **Kanalfilterung** — nur indirekt über `rtl_fm -s`; FM etwas breit, Airband-Listen etwas breit  
4. **passende Demodulation** — Envelope ok; Sync-AM ✕  
5. **externe Filter (FM-Notch)** — Hardware, besonders Airband am Proxmox-Standort  
6. **reproduzierbare Tests** — Spektrum/CLI da; kein volles Lab-Framework nötig

---

## 5. Was verbessert werden kann (empfohlen, aufwandarm)

Priorität für spätere Umsetzung — jeweils A/B gegen aktuellen Default.

| Prio | Maßnahme | Dateien | Aufwand | Erwartung |
|------|----------|---------|---------|-----------|
| **P1** | Airband-Default-Gain senken (z. B. 12–20 statt 45); UI-Hinweis „nicht maxen“ | `settings.py`, ggf. Web-Defaults | klein | weniger UKW-Blocking/IM, bessere AM-Verständlichkeit |
| **P2** | Airband-Listen-Default-`-s` Richtung 12–16 kHz + Default-LP 3000 | `settings.py`, `scanner.py` Steps ok | klein | engere Selektivität |
| **P3** | FM Play: `-s` von 250k auf **170k–200k** testen (A/B) | `fm.py` (Konstante oder Setting) | klein | etwas weniger Rauschen/CPU; Qualität prüfen |
| **P4** | Optional `rtl_fm` Offset-Tuning (`-E offset` o. ä., Version prüfen) | `fm.py`, `scanner.py` | klein–mittel | weniger DC-Spike |
| **P5** | Band-Profile in Settings (`fm_*` / `airband_*` klar getrennt dokumentieren + RF-Tools-Kurzhilfe) | Docs + RF-Tools Text | klein | Bedienung |
| **P6** | Kurzreferenz „übernommene Stick-Defaults“ neben dem GPT-Langdokument | `docs/referenz/` | klein | Wartbarkeit |

Nicht als Soft-Default ändern ohne Messung: FM-Gain 25 (eigene Messung stützt 20–30).

---

## 6. Was zu aufwendig / bewusst Out-of-Scope ist

| Thema | Warum ✕ für jetzt |
|-------|-------------------|
| Eigene I/Q-Pipeline (FIR, Decimation, Sync-AM, Stereo-MPX, RDS) | Ersatz von `rtl_fm`; großer CPU-/Wartungsaufwand auf Pi |
| R820T2-Register-Feintuning jenseits Gain/PPM | kaum offiziell steuerbar; Doku selbst: Gewinn gering vs. Gain/Filter/Antenne |
| SINAD/THD-Laborautomatisierung | Messgeräte + Offline-IQ-Framework; Spektrum-A/B reicht für Fahrzeug |
| TCXO / Stick-Tausch-Logik | Hardware; PPM-pro-Host reicht |
| Externe FM-Notch „in Software“ | physikalisch nicht ersetzbar bei Frontend-Übersteuerung |
| DAB-PPM an `welle-cli` | Tool hat kein PPM-Flag; eigene Korrektur im Decoder |

---

## 7. Kurzfazit

- PiDrive hat die **Basics der Stick-Doku** schon: Blacklist, PPM, manuelles Gain, Airband-Audiofilter, Spektrum-Diagnose, getrennte Band-Parameter.
- Die größte **softwareseitige Lücke** zur Doku ist der **zu hohe Airband-Gain-Default (45)** und etwas **breite Demod-Bandbreiten** (FM 250 kHz Play, Airband Listen 24 kHz).
- Die größte **empfangsseitige Lücke** für Airband bleibt **Hardware** (Antenne, Abstand Host, optional FM-Notch) — uns die Doku als Priorität #1 nennt.
- Ein Umbau auf Sync-AM / eigene DSP lohnt erst, wenn Parameter-Tuning und Antenne ausgereizt sind.

---

## 8. Nächste sinnvolle Arbeitspakete (Vorschlag)

1. A/B: Airband Gain 45 → 15/20 bei gleichem ATIS; Protokoll 1 Seite.  
2. A/B: FM `-s` 250k → 200k/170k auf bekanntem UKW-Sender.  
3. Bei positivem Ergebnis Defaults in `settings.py` + kurzer Changelog.  
4. Optional Offset-Tuning, wenn `rtl_fm -h` die Option auf den Zielhosts zeigt.

---

*Review erstellt nach Code-Durchsicht der unter §2 genannten Dateien und Abgleich mit Kap. 22–37 / 35–36 der Stick-Referenz.*
