# PiDrive — Kontext & Projektdokumentation v0.11.145

> **Pflegehinweis:** Nach jeder Session Changelog + Funktionsstatus aktualisieren.

## Projektbeschreibung

**PiDrive** — Raspberry-Pi Car-Infotainment für BMW iDrive (NBT EVO).
Steuerung: AVRCP, WebUI Port **8080**, `pidrivectl`.

**GitHub:** https://github.com/MPunktBPunkt/pidrive  
**WebUI:** `http://<Pi-IP>:8080`

## Hardware

| Komponente | Details |
|---|---|
| Dev | Futro S920 · Debian 13 · User `pidrive` |
| Ziel-Pi | **192.168.178.105** · User `pidrive` |
| RTL-SDR | 0bda:2838 R820T |
| BMW | 118d 2017 NBT EVO |
| PMR-Referenz | Motorola TLKR T40 (8 ch classic; UI 16 ch PMR446d) |

## Funktionsstatus v0.11.145

| Feature | Status |
|---|---|
| Webradio / FM | ✅ Listen-Klick + Favoriten |
| DAB+ | ✅ SM/Start/Stop; Indoor oft no_lock |
| Spektrum CLI | ✅ scan/peek/last |
| PMR446 Scanner | ✅ 16 Kanäle, Watch, NBFM, Monitor |
| Airband AM | ✅ Presets (EDJA), Scan, AM via rtl_fm |
| Browser-Monitor | ✅ `/api/audio/listen` (niedrige Latenz) |
| WebUI Live-Smoke | ✅ Diagnose + test all |
| BT A2DP | ✅ kein PW-Kill auf Klinke |
| Menü M0–M6 | ✅ Golden 300 Knoten |
| OTA | ✅ |
| BMW Feldtest | 🟡 2026-09-16 Pairing/Now Playing |

## Changelog

### 0.11.145 · 2026-09-19

- PMR NBFM: 24 kHz, FIR, Gain 36, Squelch-Floor 50, `-t 1`
- Monitor-Latenz: ffmpeg/mpv/Reconnect gekürzt; Sprachband-EQ
- Spektrum-Watch: Trigger 14 dB, `primary_ch` UI-Filter
- Abnahme TLKR T40 (K1/K2/K3/K8, Blindtest K2) in `ABNAHMEN.md`

### 0.11.144 · 2026-09-19

- 16-Kanal-PMR446-Grid, Live-Aktivität, sticky Topbar-Monitor

### 0.11.143 · 2026-09-19

- Alltag Listen-Klick Fix (data-attrs statt kaputter JSON.stringify-onclick)
- `play_gen` Race-Schutz; schnellere DAB-Stops; früher Commit bleibt
- WebUI Live-Smoke (Tool, Diagnose, `webui smoke`, Teil von `test all`)
- Spektrum-CLI + UKW-Gain-Doku; Audio-Monitor; BT-Recovery-Fix
- Doku-Index; erledigte AUFTRAG-* → `docs/archiv/auftraege/`

### 0.11.97–0.11.142

DAB-Stabilisierung, BT/PipeWire, MPRIS2, Menü, WebUI W0–W7, OTA, BMW-Feldtest,
USB-MSC-Planung — Details in Git und [`archiv/auftraege/`](archiv/auftraege/).

## Verweise

- [FEATURES.md](FEATURES.md) · [README.md](README.md) · [ABNAHMEN.md](ABNAHMEN.md)
- [architektur/ZUSTANDSMASCHINE.md](architektur/ZUSTANDSMASCHINE.md)
- [betrieb/SPECTRUM-CLI.md](betrieb/SPECTRUM-CLI.md)
