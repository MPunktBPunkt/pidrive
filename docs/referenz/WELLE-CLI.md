# welle.io — Technische Referenz für PiDrive

> **Herkunft und Geltung.** Erstellt am 2026-04-21 aus einer Quellcode-Analyse von
> welle.io-master (`src/welle-cli/`, `src/input/rtl_sdr.cpp`, `src/backend/`,
> `src/various/channels.cpp`), damals für PiDrive v0.9.4. **Keine Messung am installierten
> Stand** — die Fassung auf dem Pi kann abweichen. Vor tragenden Entscheidungen
> `welle-cli --help` auf dem Gerät abrufen und die Ausgabe nach `docs/ABNAHMEN.md` legen.
>
> Am 2026-09-16 gegen v0.11.139 gegengelesen. Ergebnis in
> [`../auftraege/AUFTRAG-DAB-AUDIOWEG.md`](../auftraege/AUFTRAG-DAB-AUDIOWEG.md) §5
> als DA-P1 bis DA-P5. Bestätigt: die Gain-Umrechnung in `dab_helpers.py`
> `_get_dab_gain()` folgt dieser Referenz korrekt (Index statt dB) — **nicht „begradigen"**.

---

## Inhaltsverzeichnis

1. [Projektüberblick](#1-projektüberblick)
2. [Architektur](#2-architektur)
3. [welle-cli — vollständige Kommandoreferenz](#3-welle-cli--vollständige-kommandoreferenz)
4. [Betriebsmodi](#4-betriebsmodi)
5. [RTL-SDR Eingabe: Samples, Gain, AGC](#5-rtl-sdr-eingabe-samples-gain-agc)
6. [DAB-Signalverarbeitung intern](#6-dab-signalverarbeitung-intern)
7. [Webserver-Modus: alle HTTP-Endpunkte](#7-webserver-modus-alle-http-endpunkte)
8. [mux.json — vollständige Struktur](#8-muxjson--vollständige-struktur)
9. [Spektrum-Endpunkte: Datenformat und Nutzung](#9-spektrum-endpunkte-datenformat-und-nutzung)
10. [Kanal-Frequenztabelle (Band III + Band L)](#10-kanal-frequenztabelle-band-iii--band-l)
11. [Gain-Index-Tabelle (R820T, 29 Stufen)](#11-gain-index-tabelle-r820t-29-stufen)
12. [PiDrive-Nutzungsmuster](#12-pidrive-nutzungsmuster)

---

## 1. Projektüberblick

welle.io ist ein Open-Source-DAB/DAB+-Empfänger (GNU GPL v2+), der ursprünglich als
Qt-GUI-Anwendung entwickelt wurde und neben dem grafischen Frontend auch `welle-cli` als
reines Kommandozeilen-/Server-Werkzeug enthält. Das Projekt basiert auf SDR-J von
Jan van Katwijk und wurde von Albrecht Lohofener und Matthias P. Braendli
weiterentwickelt.

**Für PiDrive relevant ist ausschließlich `welle-cli`**, nicht die Qt-GUI.

---

## 2. Architektur

```
         ┌─────────────────────────────────────────────────┐
         │                   welle-cli                     │
         │                                                 │
         │  parse_cmdline()                                │
         │       │                                         │
         │       ▼                                         │
         │  CVirtualInput (Abstrakte Eingabe-Schicht)      │
         │  ┌──────────┐ ┌──────────┐ ┌──────────────┐    │
         │  │CRTL_SDR  │ │rtl_tcp   │ │CRAWFile (IQ) │    │
         │  │(RTL-SDR) │ │(Netzwerk)│ │(.iq Datei)   │    │
         │  └──────────┘ └──────────┘ └──────────────┘    │
         │       │                                         │
         │       ▼                                         │
         │  RadioReceiver (OFDM + FIC + MSC)               │
         │  ┌────────────────────────────────────────┐     │
         │  │ OFDM-Processor                         │     │
         │  │   → Synchronisation (Null-Symbol)      │     │
         │  │   → FFT (T_u=2048 Punkte)              │     │
         │  │   → Frequenzkorrektur (coarse+fine)    │     │
         │  │   → TII-Decoder (Senderkennnung)       │     │
         │  ├────────────────────────────────────────┤     │
         │  │ FIC-Handler (Fast Information Channel) │     │
         │  │   → FIB-Decoder (FIG-Parsing)          │     │
         │  │   → Ensemble-Label, Service-Liste      │     │
         │  │   → CRC-Prüfung                        │     │
         │  ├────────────────────────────────────────┤     │
         │  │ MSC-Handler (Main Service Channel)     │     │
         │  │   → DAB/DAB+-Audio-Decoder             │     │
         │  │   → Reed-Solomon-Fehlerkorrektur       │     │
         │  │   → Viterbi-Dekodierung                │     │
         │  │   → AAC/MP2-Dekodierung                │     │
         │  └────────────────────────────────────────┘     │
         │       │                                         │
         │       ▼                                         │
         │  WebRadioInterface (Webserver) ──── Port X      │
         │  RadioControllerInterface (Callbacks)           │
         └─────────────────────────────────────────────────┘
```

**Zwei grundlegende Betriebspfade:**

- **Ohne `-w`:** Direkte ALSA-Ausgabe (`AlsaProgrammeHandler`) oder Datei-Dump
- **Mit `-w PORT`:** Webserver-Modus (`WebRadioInterface`), HTTP-Streaming und mux.json-API

---

## 3. welle-cli — vollständige Kommandoreferenz

### 3.1 Übersicht aller Optionen

```
welle-cli [OPTIONEN]
```

| Option | Argument | Bedeutung |
|---|---|---|
| `-c` | `KANAL` | DAB-Kanal einstellen (z.B. `11D`, `5A`, `10B`) |
| `-p` | `PROGRAMM` | Programm per Name via ALSA abspielen (z.B. `Bayern 1`) |
| `-g` | `INDEX` | Gain-**Index** 0–28 setzen, oder `-1` für Software-AGC |
| `-w` | `PORT` | HTTP-Webserver auf Port aktivieren |
| `-C` | `N` | N Programme im Carousel-Modus dekodieren |
| `-P` | *(kein Arg)* | Carousel wartet auf DLS+Slide statt 10s-Timer |
| `-D` | *(kein Arg)* | Alle Programme + FIC in Dateien dumpen |
| `-d` | *(kein Arg)* | Einzelnes Programm in `.msc`-Datei dumpen |
| `-f` | `DATEI` | IQ-Datei als Quelle (u8-Format, oder `FORMAT.iq`) |
| `-F` | `TREIBER` | Eingabe-Frontend festlegen |
| `-u` | *(kein Arg)* | Coarse Frequency Corrector deaktivieren |
| `-T` | *(kein Arg)* | TII-Dekodierung deaktivieren (CPU sparen) |
| `-O` | `CODEC` | Audio-Codec für Webstreaming: `mp3` (Standard) oder `flac` |
| `-s` | `ARGS` | SoapySDR-Treiberargumente |
| `-A` | `ANTENNE` | SoapySDR-Antenne setzen |
| `-t` | `TEST_ID` | Internen Test ausführen |
| `-h` | *(kein Arg)* | Hilfe anzeigen |
| `-v` | *(kein Arg)* | Versionsinformation anzeigen |

### 3.2 Detailbeschreibung kritischer Optionen

#### `-g GAIN_INDEX` — Gain-Steuerung

**KRITISCH: `-g` erwartet einen Gain-INDEX, NICHT einen dB-Wert.**

Intern lädt `CRTL_SDR` beim Öffnen alle unterstützten Gain-Werte vom Treiber:

```cpp
uint32_t gainsCount = rtlsdr_get_tuner_gains(device, NULL);
gains.resize(gainsCount);
gainsCount = rtlsdr_get_tuner_gains(device, gains.data());
```

Beim Aufruf von `setGain(gain_index)` wird dann `gains[gain_index]` (in 1/10 dB) an den
Treiber übergeben:

```cpp
float CRTL_SDR::setGain(int gain_index) {
    if ((size_t)gain_index >= gains.size()) {
        std::clog << "RTL_SDR: Unknown gain count" << gain_index;
        return 0;
    }
    currentGain = gains[gain_index];
    rtlsdr_set_tuner_gain(device, currentGain);
    return currentGain / 10.0;  // Rückgabe in dB
}
```

**Folge:** `welle-cli -g 40` übergibt Index 40, der für einen R820T mit 29 Stufen
(Index 0–28) außerhalb des gültigen Bereichs liegt → `"Unknown gain count40"` → Gain
bleibt bei 0 dB.

**Korrekt:** `-g -1` für AGC, `-g 22` für ~40 dB, `-g 28` für ~49.6 dB (maximum).

Vollständige Tabelle: [Abschnitt 11](#11-gain-index-tabelle-r820t-29-stufen).

> **PiDrive:** `dab_helpers.py` `_get_dab_gain()` nimmt die Einstellung `dab_gain` in **dB**
> und rechnet sie über `_RTL_GAIN_TABLE` in den nächstliegenden Index um; `-1` wird
> unverändert als AGC durchgereicht. Das ist richtig so und darf nicht „vereinfacht"
> werden.

#### `-g -1` — Software-AGC

```cpp
if (options.gain == -1) {
    in->setAgc(true);
}
```

`setAgc(true)` aktiviert die welle.io-eigene AGC-Logik in einem dedizierten Thread
(`agc_timer_thread`), der alle 50 ms den Amplitudenbereich der IQ-Samples prüft:

- **Overload** (min=0 oder max=255): Gain-Index um 1 verringern
- **Headroom vorhanden**: Gain-Index schrittweise erhöhen, falls Simulation ergibt dass
  kein Clipping entsteht
- **Bei deaktivierter AGC + Overload**: Warnung `"ADC overload"` in stderr

Der Unterschied zur Hardware-AGC (`rtlsdr_set_agc_mode`): welle.io nutzt immer den
manuellen Gain-Modus des Tuners, steuert ihn aber selbst im Software-Loop.

**Log-Ausgabe beim Start:** `RTL_SDR: gain 0.9` bedeutet: AGC startete bei Index 1
(= 0.9 dB). Das ist normal und korrekt.

#### `-C N` — Carousel-Modus

Wenn ein Ensemble mehrere Programme hat und die CPU nicht alle gleichzeitig dekodieren kann:

- `N` Programme werden gleichzeitig aktiv gehalten
- alle 10 Sekunden wird gewechselt (Standard)
- mit `-P` zusätzlich: Wechsel erst wenn DLS **und** Slide dekodiert wurden (maximal
  80 Sekunden pro Programm)

**Für PiDrive:** `-C 1` bedeutet: nur das aktuell aufgerufene Programm wird im Carousel
dekodiert. Damit werden Ensemble-Daten und mux.json gesammelt, ohne dass alle Sender
gleichzeitig Audio produzieren müssen. Das ist der korrekte Scan-Modus für PiDrive.

> **Achtung für die Wiedergabe:** der Carousel **wechselt** das Programm zyklisch. Für die
> Tonwiedergabe eines festen Senders ist `-C` deshalb falsch — siehe DA-P3 in
> [AUFTRAG-DAB-AUDIOWEG.md](../auftraege/AUFTRAG-DAB-AUDIOWEG.md).

#### `-P` — Carousel-PAD-Modus

Wird **ausschließlich** zusammen mit `-C` und `-w` verwendet. Kontrolliert nur die
Carousel-Weiterschalt-Logik:

```cpp
if (options.carousel_pad) {
    ds.strategy = DS::CarouselPAD;  // warte auf DLS + Slide, max 80s
} else {
    ds.strategy = DS::Carousel10;   // wechsle alle 10s
}
```

**Kein PPM-Korrektur-Flag.** PPM-Korrektur wird intern durch den `coarse_corrector`
erledigt.

#### `-u` — Coarse Corrector deaktivieren

Der welle.io-Empfänger hat zwei Frequenzkorrekturschichten:

- **Fine Corrector:** korrigiert kleine Drifts, läuft immer
- **Coarse Corrector:** korrigiert große Frequenzoffsets (mehrere kHz), z.B. durch
  PPM-Fehler des RTL-SDR

`-u` deaktiviert den Coarse Corrector. Für RTL-SDR-Sticks mit hohem PPM-Fehler (typisch
30–100 ppm) sollte `-u` **nicht** verwendet werden. Der Coarse Corrector gleicht den
PPM-Fehler automatisch aus.

#### `-F` — Frontend-Treiber

| Wert | Beschreibung |
|---|---|
| `auto` (Standard) | Automatische Erkennung (erst RTL-SDR, dann andere) |
| `rtl_sdr` | Explizit RTL-SDR USB |
| `rtl_tcp` | RTL-TCP Netzwerk-Frontend |
| `airspy` | Airspy HF+ |
| `soapysdr` | SoapySDR-Abstraktion |
| `android_rtl_sdr` | Android RTL-SDR |

Für `rtl_tcp` mit Adresse: `-F rtl_tcp,192.168.1.100:1234`

#### `-O` — Output-Codec

| Wert | Format | Bemerkung |
|---|---|---|
| `mp3` (Standard) | MPEG Audio Layer 3 | immer verfügbar |
| `flac` | Free Lossless Audio Codec | nur wenn mit `HAVE_FLAC` kompiliert |

Gilt für den `/mp3/<sid>` bzw. `/flac/<sid>` HTTP-Stream-Endpunkt.

---

## 4. Betriebsmodi

### 4.1 ALSA-Direktwiedergabe (ohne `-w`)

```bash
welle-cli -c 11D -g -1 -p "Bayern 1"
```

Ablauf intern:

1. RTL-SDR öffnen, Frequenz für `11D` (222.064 MHz) setzen
2. `RadioReceiver::restart(false)` starten
3. Auf `synced == true` warten (Null-Symbol gefunden)
4. Auf nicht-leere Service-Liste warten
5. Weitere 3 Sekunden warten (Service-Liste vervollständigen)
6. `playSingleProgramme()` für das passende Programm
7. `AlsaProgrammeHandler::onNewAudio()` → PCM an ALSA-Output
8. Läuft bis Ctrl-C oder `stdin`-Eingabe von `.`

Stderr zeigt Service-Liste:
`[0x1234] Bayern 1 [component 0 ASCTy: DAB+] [subch 5 bitrate:128 at SAd:348]`

**Für PiDrive:** welle-cli wird per Pipe an mpv übergeben:

```bash
welle-cli -c 11D -g -1 -p 'Bayern 1' | mpv --no-video --ao=pulse -
```

Dafür muss ALSA-Support vorhanden sein; alternativ: Webserver-Modus + mpv-HTTP-Stream.

### 4.2 Webserver-Modus (`-w PORT`)

```bash
welle-cli -c 11D -g -1 -C 1 -w 7979
```

`WebRadioInterface` wird instanziiert, bindet den TCP-Port und startet einen
Blockierungs-Server-Loop (`serve()`). Jede HTTP-Verbindung wird in einem neuen Thread
behandelt. Gleichzeitig läuft `RadioReceiver` und befüllt interne Datenstrukturen.

### 4.3 Dump-Modus (`-D`)

```bash
welle-cli -c 10B -D
```

Schreibt für jeden Service:

- `<name>.wav` — PCM-Audio (WAV-Format, 48 kHz stereo)
- `<name>.msc` — Rohe MSC-Daten (Subchannel-Payload)
- `dump.fic` — FIC-Rohdaten (32 Byte pro FIB, nur valide CRC)

### 4.4 IQ-Datei-Modus (`-f DATEI`)

```bash
welle-cli -f recording.iq -p GRIFF
welle-cli -f recording.u8.iq -t 1
```

Format: u8 (unsigned 8-bit), I/Q alternierend. Bei Dateinamen mit `FORMAT.iq`-Suffix wird
das Format aus dem Dateinamen gelesen. Nützlich für Offline-Tests und Debugging.

---

## 5. RTL-SDR Eingabe: Samples, Gain, AGC

### 5.1 Sample-Rate und Puffer

```cpp
#define INPUT_RATE 2048000   // 2.048 Msps — exakt für DAB Mode 1
#define READLEN_DEFAULT 8192  // Bytes pro USB-Callback (~4096 IQ-Samples)
```

Die Sample-Rate von 2.048 MHz ist nicht zufällig: DAB Mode 1 hat einen OFDM-Frame von
T_F = 196.608 Samples = 96 ms. Mit 2.048 MHz passt genau T_u = 2048 Samples in ein
OFDM-Symbol.

**Zwei Ringpuffer:**

- `sampleBuffer(1024 * 1024)` — Haupt-IQ-Puffer für den RadioReceiver
- `spectrumSampleBuffer(8192)` — separater kleiner Puffer für Spektrum-Snapshots

Beide werden vom gleichen USB-Callback `rtlsdr_read_callback` befüllt.

### 5.2 USB-Async-Callback

```cpp
void CRTL_SDR::rtlsdr_read_callback(uint8_t* buf, uint32_t len, void* ctx)
{
    // buf = uint8_t, unsigned 8-bit IQ, I und Q alternierend
    // len = 8192 Bytes = 4096 IQ-Paare

    sampleBuffer.putDataIntoBuffer(buf, len);        // → RadioReceiver
    spectrumSampleBuffer.putDataIntoBuffer(buf, len); // → getSpectrumSamples()

    // Amplitudenbereich für AGC-Steuerung prüfen:
    minAmplitude = min(buf[i] for all i)
    maxAmplitude = max(buf[i] for all i)
}
```

### 5.3 IQ-Sample-Konvertierung

```cpp
// u8 → DSPCOMPLEX (float32 I/Q, Bereich ca. -1.0 bis +1.0)
buffer[i] = DSPCOMPLEX(
    (float(tempBuffer[2*i]     - 128)) / 128.0,  // I
    (float(tempBuffer[2*i + 1] - 128)) / 128.0   // Q
);
```

### 5.4 Software-AGC Logik

Läuft in `agc_timer_thread` alle 50 ms:

```
if (AGC aktiv):
    if (minAmplitude == 0 OR maxAmplitude == 255):
        → Overload: gain_index -= 1  (Gain senken)
    else:
        nächster Gain-Schritt simulieren:
        DeltaGain_dB = gains[index+1] / 10 - gains[index] / 10
        LinGain = 10^(DeltaGain_dB / 20)
        NewMax = maxAmplitude * LinGain
        NewMin = minAmplitude / LinGain
        if (NewMin >= 0 AND NewMax <= 255):
            → kein Clipping: gain_index += 1  (Gain erhöhen)
```

Die AGC hält den Gain so hoch wie möglich ohne Clipping.

---

## 6. DAB-Signalverarbeitung intern

### 6.1 DAB Mode 1 Parameter (Standard in Europa)

| Symbol | Wert | Bedeutung |
|---|---|---|
| `T_u` | 2048 | Nutzanteil eines OFDM-Symbols (Samples) |
| `T_s` | 2552 | Gesamtlänge Symbol inkl. Guard-Intervall |
| `T_g` (Guard) | 504 | Cyclic Prefix / Guard-Intervall |
| `T_null` | 2656 | Null-Symbol (Synchronisation) |
| `T_F` | 196608 | Gesamter DAB-Frame (~96 ms) |
| K | 1536 | Nutzträger (OFDM-Subcarrier) |
| L | 76 | OFDM-Symbole pro Frame |
| Bandbreite | ~1.54 MHz | gesamte DAB-Kanalbreite |

### 6.2 Verarbeitungspipeline

```
USB-Samples (u8, 2048000/s)
    ↓
u8 → DSPCOMPLEX (float32 I/Q)
    ↓
OFDM-Processor:
    Null-Symbol-Detektion (Synchronisation)
    ↓
    Coarse Frequency Corrector (PPM-Kompensation)
    ↓
    FFT (2048-Punkt, Hanning-Fenster)
    ↓
    Fine Frequency Corrector
    ↓
    QPSK-Demodulation der 1536 Träger
    ↓
    Frequency-Deinterleaving
    ↓
    Zeitdeinterleaving
    ↓
FIC-Handler (Fast Information Channel, 3 FIBs/Frame):
    Faltungsdekodierung (Viterbi)
    ↓
    CRC-16 Prüfung
    ↓
    FIB-Parsing (FIG 0/1: Ensemble, Services, Subchannels)
    ↓
    Service-Liste aufbauen
    ↓
MSC-Handler (Main Service Channel):
    Subchannel-Extraktion (nach SAD + Bitrate)
    ↓
    EEP/UEP Reed-Solomon-Fehlerkorrektur
    ↓
    DAB/DAB+-Dekodierung:
        DAB:  MPEG-1 Layer 2 (MP2)
        DAB+: AAC-LC / HE-AAC
    ↓
    PCM-Output (int16, 48000/s, stereo)
    ↓
    MP3/FLAC-Kodierung (Webserver-Modus)
    ↓
    HTTP-Stream an Client
```

### 6.3 FIC — Fast Information Channel

Der FIC überträgt die Metadaten des gesamten Ensembles. Jeder DAB-Frame enthält 3 FIBs
(Fast Information Blocks) zu je 32 Bytes. Der FIC-Handler:

- Prüft CRC-16 jedes FIB
- Zählt `num_fic_crc_errors` bei Fehler (sichtbar in mux.json als
  `demodulator.fic.numcrcerrors`)
- Parst FIG 0 (Subchannel-Konfiguration, Service-Linking) und FIG 1 (Labels, Sprache,
  Programmtyp)
- Stellt Ensemble-ID, ECC, Service-Liste zur Verfügung

**Der FIC-Lock ist die kritische Größe beim Scan:** Erst wenn FIBs mit valider CRC
ankommen, kann das Ensemble identifiziert und die Service-Liste aufgebaut werden. Bei
schlechtem SNR scheitert genau dieser Schritt.

```
SNR:  0–3 dB  → FIC kann nicht dekodiert werden → services=[], ensemble=''
SNR:  3–7 dB  → FIC sporadisch, Lock möglich nach 10–30s
SNR:  7–12 dB → FIC stabil nach 3–8s
SNR: 12+ dB   → sofortiger FIC-Lock
```

### 6.4 TII — Transmitter Identification Information

TII-Daten werden im Null-Symbol übertragen und identifizieren den sendenden Sender
(Comb + Pattern → eindeutiger Sender). `tii-decoder.cpp` dekodiert diese und berechnet
sogar die ungefähre Entfernung in km (basierend auf dem Delay des Impulse Response).

In mux.json: `tii[].comb`, `tii[].pattern`, `tii[].delay_km`.

TII-Dekodierung kann mit `-T` deaktiviert werden (CPU-Einsparung auf schwacher Hardware).

---

## 7. Webserver-Modus: alle HTTP-Endpunkte

Aktivierung: `welle-cli -c KANAL -g -1 -C N -w PORT`

Der Webserver ist ein einfacher HTTP/1.0-Server, keine Bibliothek. Jede Verbindung bekommt
einen eigenen Thread.

### 7.1 GET-Endpunkte

| URL | Content-Type | Beschreibung |
|---|---|---|
| `/` | text/html | Eingebettete Web-UI (index.html aus compilierter Resource) |
| `/index.js` | text/javascript | JavaScript der Web-UI |
| `/favicon.ico` | image/x-icon | Icon |
| `/mux.json` | application/json | **Vollständiges Ensemble+Demodulator-Statusobjekt** |
| `/mux.m3u` | application/mpegurl | M3U-Playlist aller Audio-Services |
| `/fic` | application/octet-stream | **Rohe FIB-Daten** (32 Byte/FIB, binär, nur valide CRC) |
| `/impulseresponse` | application/octet-stream | **CIR-Daten** (float32, binär) |
| `/spectrum` | application/octet-stream | **Aktuelles OFDM-Spektrum** (2048 × float32-Komplex, binär) |
| `/nullspectrum` | application/octet-stream | **Null-Symbol-Spektrum** (2048 × float32-Komplex, binär) |
| `/constellation` | application/octet-stream | **Konstellationspunkte** (float32-Phasen, binär) |
| `/channel` | text/plain | Aktueller Kanalname (z.B. `11D`) |
| `/slide/<hex_sid>` | image/* | MOT-Slideshow-Bild des Service mit SID `hex_sid` |
| `/mp3/<hex_sid>` | audio/mpeg | **Audio-Stream** (MP3, HTTP-Streaming, blockierend) |
| `/flac/<hex_sid>` | audio/flac | Audio-Stream (FLAC, nur mit `HAVE_FLAC`) |

### 7.2 POST-Endpunkte

| URL | Body | Aktion |
|---|---|---|
| `/channel` | Kanalname (Text) | Kanal wechseln, Receiver neu starten |
| `/fftwindowplacement` | Placement-String | FFT-Fensterposition ändern |
| `/enablecoarsecorrector` | `"true"` / `"false"` | Coarse Corrector ein/ausschalten |

### 7.3 Stream-Endpunkte: `/mp3/<sid>` und `/flac/<sid>`

Die SID ist der Hexadezimal-Wert des Service-Identifiers aus mux.json (z.B. `0x1234` →
URL-Teil `0x1234`).

Der Stream ist ein **echter HTTP-Streaming-Response**: Die Verbindung bleibt offen, so
lange Audio vorhanden ist. mpv kann diesen Stream direkt konsumieren:

```bash
mpv --no-video --ao=pulse http://127.0.0.1:7979/mp3/0x1234
```

Der `ProgrammeSender`-Mechanismus registriert sich beim entsprechenden
`WebProgrammeHandler`, der die dekodierten Audio-Frames direkt in die HTTP-Verbindung
schreibt.

---

## 8. mux.json — vollständige Struktur

mux.json ist die wichtigste API für PiDrive. Sie enthält alles was welle.io über das
aktuelle Ensemble weiß.

```json
{
  "receiver": {
    "hardware": {
      "name": "RTL2838UHIDIR",
      "gain": 0.9
    },
    "software": {
      "name": "welle.io",
      "version": "...",
      "fftwindowplacement": "ThresholdBeforePeak",
      "coarsecorrectorenabled": true,
      "freqsyncmethod": "...",
      "lastchannelchange": 1776700000
    }
  },
  "ensemble": {
    "label": {
      "label": "BR Bayern",
      "shortlabel": "BR Bayern",
      "fig2label": "",
      "fig2rfu": 0,
      "fig2charset": "Undefined"
    },
    "id": "0x1001",
    "ecc": "0xe1"
  },
  "services": [
    {
      "sid": "0x1234",
      "programType": 0,
      "ptystring": "No programme type",
      "language": 0,
      "languagestring": "Unknown language",
      "label": {
        "label": "Bayern 1",
        "shortlabel": "BR 1",
        "fig2label": "",
        "fig2rfu": 0,
        "fig2charset": "Undefined"
      },
      "components": [
        {
          "componentnr": 0,
          "primary": true,
          "caflag": false,
          "transportmode": "audio",
          "ascty": "DAB+",
          "scid": null,
          "dscty": null,
          "label": {"label": "", "shortlabel": ""},
          "subchannel": {
            "subchid": 5,
            "bitrate": 128,
            "cu": 84,
            "sad": 348,
            "protection": "EEP 3-A",
            "language": 0,
            "languagestring": "Unknown language"
          }
        }
      ],
      "url_mp3": "/mp3/0x1234",
      "channels": 2,
      "samplerate": 48000,
      "mode": "DAB+",
      "audiolevel": {
        "time": 1776700010,
        "left": -18,
        "right": -17
      },
      "mot": {
        "time": 1776700000,
        "lastchange": 1776700005
      },
      "dls": {
        "label": "Aktueller Titel — Interpret",
        "time": 1776700000,
        "lastchange": 1776700003
      },
      "errorcounters": {
        "frameerrors": 0,
        "rserrors": 0,
        "aacerrors": 0,
        "time": 1776700010
      },
      "xpaderror": {
        "haserror": false
      }
    }
  ],
  "demodulator": {
    "fic": {
      "numcrcerrors": 42
    },
    "snr": 12.5,
    "frequencycorrection": 29099,
    "time_last_fct0_frame": 1776700010000
  },
  "utctime": {
    "year": 2026,
    "month": 4,
    "day": 20,
    "hour": 17,
    "minutes": 30,
    "lto": 2.0
  },
  "tii": [
    {
      "comb": 5,
      "pattern": 12,
      "delay": 1024,
      "delay_km": 150.0,
      "error": 0.01
    }
  ],
  "cir_peaks": [
    {"index": 1024, "value": 0.85},
    {"index": 2048, "value": 0.12}
  ],
  "messages": [
    "2026-04-20 17:30:00.000 INFO : Service list updated"
  ]
}
```

### 8.1 Scan-relevante Felder

| Feld | Typ | Scan-Bedeutung |
|---|---|---|
| `ensemble.label.label` | string | Ensemble-Name (leer = kein FIC-Lock) |
| `ensemble.id` | string | Ensemble-ID (0x0000 = kein Lock) |
| `ensemble.ecc` | string | Extended Country Code |
| `services[]` | array | Leer = kein Lock oder keine Services |
| `services[].sid` | string | Service-Identifier (hex) — eindeutig |
| `services[].label.label` | string | Programm-Name |
| `services[].url_mp3` | string | Stream-URL `/mp3/<sid>` |
| `services[].components[].ascty` | string | `"DAB"` oder `"DAB+"` |
| `services[].components[].subchannel.bitrate` | int | Bitrate in kbps |
| `demodulator.snr` | float | Signal-Rausch-Abstand in dB |
| `demodulator.fic.numcrcerrors` | int | FIC-CRC-Fehler seit Start — **wichtigster Lock-Indikator** |
| `demodulator.frequencycorrection` | float | Frequenzkorrektur in Samples (Coarse+Fine) |
| `demodulator.time_last_fct0_frame` | int | Timestamp letzter FCT-0-Frame (ms) |
| `receiver.hardware.gain` | float | Aktuell gesetzter Gain in dB |

### 8.2 Interpretation im Scan

```
services=[]  AND  fic.numcrcerrors > 100  AND  snr < 3    → kein Signal
services=[]  AND  fic.numcrcerrors > 100  AND  snr 3–8    → Signal, aber Lock noch nicht stabil → WAIT_LOCK erhöhen
services=[]  AND  fic.numcrcerrors = 0    AND  snr > 8    → Lock fast da, noch mehr Zeit geben
services=N   AND  ensemble != ''                           → erfolgreich!
```

---

## 9. Spektrum-Endpunkte: Datenformat und Nutzung

### 9.1 `/spectrum` — OFDM-Empfangsspektrum

**Quelle:** `getSpectrumSamples(dabparams.T_u)` → 2048 frische IQ-Samples aus dem
`spectrumSampleBuffer`, direkt vom USB-Callback.

**Verarbeitung:**

```cpp
DSPCOMPLEX* spectrumBuffer = spectrum_fft_handler.getVector();
auto samples = input.getSpectrumSamples(dabparams.T_u);  // 2048 Samples
copy(samples.begin(), samples.end(), spectrumBuffer);
spectrum_fft_handler.do_FFT();  // In-Place FFT über 2048 Punkte
return send_fft_data(s, spectrumBuffer, dabparams.T_u);
```

**Ausgabe:** `Content-Type: application/octet-stream`, binäre float32-Daten.

Format: 2048 × Komplex-float32 (I/Q), FFT-verschoben (DC-Bin in der Mitte).
Gesamtgröße: 2048 × 8 Bytes = **16.384 Bytes** pro Anfrage.

**Python-Auswertung:**

```python
import numpy as np, urllib.request

r = urllib.request.urlopen('http://127.0.0.1:7979/spectrum')
raw = r.read()
# 2 float32 pro Bin (Real + Imag)
data = np.frombuffer(raw, dtype=np.float32).reshape(-1, 2)
iq = data[:,0] + 1j * data[:,1]
power_db = 20 * np.log10(np.abs(iq) + 1e-12)
# Frequenzachse: -1024 bis +1023 kHz (bei 2.048 MHz SR)
freqs_khz = np.fft.fftshift(np.fft.fftfreq(2048, d=1/2048.0))
```

**Anwendung:** Sichtbarkeit des DAB-Ensembles (1.54 MHz Breite um Mittenfrequenz). Zeigt
ob überhaupt ein DAB-Signal vorhanden ist, bevor man auf FIC-Lock wartet.

### 9.2 `/nullspectrum` — Null-Symbol-Spektrum

**Quelle:** Letztes gespeichertes Null-Symbol (`last_NULL`) aus `onNewNullSymbol()`. Das
Null-Symbol ist der kurze Signalausfall zwischen DAB-Frames und enthält die
TII-Information.

Gleiche Binärstruktur wie `/spectrum`.

**Unterschied zu `/spectrum`:**

- `/spectrum`: frische Samples aus dem USB-Puffer (aktuelle Empfangsqualität)
- `/nullspectrum`: gespeichertes Null-Symbol (für TII-Analyse, Sender-Fingerprint)

Das Null-Symbol-Spektrum zeigt charakteristische Muster pro Sender (TII) und ist für die
Sender-Identifikation interessant. Bei mehreren Sendern im Single-Frequency-Network sind
mehrere Peaks sichtbar.

### 9.3 `/constellation` — Konstellationsdiagramm

**Quelle:** `last_constellation` aus `onConstellationPoints()` — QPSK-Demodulations-Ausgabe
des OFDM-Dekoders.

```cpp
const size_t decim = OfdmDecoder::constellationDecimation;
const size_t num_iqpoints = (dabparams.L - 1) * dabparams.K / decim;
// Mode 1: (76-1) * 1536 / decim = 115200 / decim Punkte
```

Ausgabe: float32-Phasen-Array (in Grad: -180 bis +180). Kein Komplex, nur Phasen.

**Anwendung:** Qualitätsbewertung des QPSK-Signals. Gut → 4 scharfe Cluster. Schlecht →
verschmiertes Muster. Kann zur visuellen SNR-Schätzung genutzt werden.

### 9.4 `/impulseresponse` — Channel Impulse Response (CIR)

**Quelle:** `last_CIR` aus `onNewImpulseResponse()` — Kanalimpulsantwort vom
OFDM-Prozessor.

Ausgabe: float32-Array (lineare Skala, kein Komplex).

**Anwendung:**

- Mehrwegeausbreitung sichtbar (Peaks = reflektierte Signalwege)
- TII-Peak-Berechnung: welle.io berechnet aus den 6 stärksten CIR-Peaks die Entfernung zum
  Sender in km
- In mux.json als `cir_peaks[]` verfügbar (Index, Wert, Entfernung aus
  `3e8 / 1000 / 2048000 km/Sample`)

### 9.5 `/fic` — Rohe FIC-Daten

Binärer Stream der validen FIBs: jeweils 32 Bytes pro FIB, nur wenn CRC-Prüfung bestanden.

**Anwendung:** Tiefe Analyse der FIG-Daten (z.B. Service-Linking, Announcement, Extended
Services). Für PiDrive normalerweise nicht benötigt, da mux.json alle relevanten Daten
enthält.

---

## 10. Kanal-Frequenztabelle (Band III + Band L)

Aus `channels.cpp` (Frequenzen in Hz):

### Band III (174–240 MHz) — 38 Kanäle

| Kanal | Freq (MHz) | Kanal | Freq (MHz) | Kanal | Freq (MHz) |
|---|---|---|---|---|---|
| 5A | 174.928 | 7C | 192.352 | 10B | 211.648 |
| 5B | 176.640 | 7D | 194.064 | 10C | 213.360 |
| 5C | 178.352 | 8A | 195.936 | 10D | 215.072 |
| 5D | 180.064 | 8B | 197.648 | 11A | 216.928 |
| 6A | 181.936 | 8C | 199.360 | 11B | 218.640 |
| 6B | 183.648 | **8D** | **201.072** | 11C | 220.352 |
| 6C | 185.360 | 9A | 202.928 | **11D** | **222.064** |
| 6D | 187.072 | 9B | 204.640 | 12A | 223.936 |
| 7A | 188.928 | 9C | 206.352 | 12B | 225.648 |
| 7B | 190.640 | 9D | 208.064 | 12C | 227.360 |
| — | — | **10A** | **209.936** | **12D** | **229.072** |
| 13A | 230.784 | 13C | 234.208 | 13E | 237.488 |
| 13B | 232.496 | 13D | 235.776 | 13F | 239.200 |

**Fett:** wichtige Kanäle für Bayern/Allgäu (BR Bayern auf 11D, Bundesmux auf 5C/5D, SWR
auf 8D)

### Band L (1452–1479 MHz) — 16 Kanäle

| Kanal | Freq (MHz) | Kanal | Freq (MHz) |
|---|---|---|---|
| LA | 1452.960 | LI | 1466.656 |
| LB | 1454.672 | LJ | 1468.368 |
| LC | 1456.384 | LK | 1470.080 |
| LD | 1458.096 | LL | 1471.792 |
| LE | 1459.808 | LM | 1473.504 |
| LF | 1461.520 | LN | 1475.216 |
| LG | 1463.232 | LO | 1476.928 |
| LH | 1464.944 | LP | 1478.640 |

Band L ist für RTL-SDR-Sticks normalerweise **nicht empfangbar** (zu hohe Frequenz für
R820T ohne speziellen Upconverter).

---

## 11. Gain-Index-Tabelle (R820T, 29 Stufen)

Die Tabelle wird zur Laufzeit vom Treiber geladen (`rtlsdr_get_tuner_gains`). Für den
R820T Tuner (RTL2838 DVB-T Stick, ID `0bda:2838`) sind folgende 29 Stufen typisch:

| Index | dB | Index | dB | Index | dB |
|---|---|---|---|---|---|
| **0** | **0.0** | 10 | 19.7 | 20 | 38.6 |
| 1 | 0.9 | 11 | 20.7 | 21 | 39.7 |
| 2 | 1.4 | 12 | 22.9 | **22** | **40.2** |
| 3 | 2.7 | 13 | 25.4 | 23 | 42.1 |
| 4 | 3.7 | 14 | 28.0 | 24 | 43.4 |
| 5 | 7.7 | 15 | 29.7 | 25 | 43.9 |
| 6 | 8.7 | 16 | 32.8 | 26 | 44.5 |
| 7 | 12.5 | 17 | 33.8 | 27 | 48.0 |
| 8 | 14.4 | 18 | 36.4 | **28** | **49.6** |
| 9 | 15.7 | 19 | 37.2 | — | — |

**Empfehlungen für PiDrive:**

- `-g -1` → Software-AGC (wählt automatisch, empfohlen für Fahrzeugeinsatz)
- `-g 22` → ~40.2 dB (guter Innenraumempfang ohne externe Antenne)
- `-g 28` → 49.6 dB (maximale Verstärkung, schwaches Signal/schlechte Antenne)

**`getGainCount()` gibt `gains.size() - 1` zurück** = 28 (max. gültiger Index).

---

## 12. PiDrive-Nutzungsmuster

### 12.1 Standard-Wiedergabe

```bash
# Bayern 1 auf 11D mit AGC
welle-cli -c 11D -g -1 -p 'Bayern 1' 2>/tmp/pidrive_dab_welle.err | \
    mpv --no-video --really-quiet --title=pidrive_dab --ao=pulse -
```

**Was passiert intern:**

1. RTL-SDR öffnet auf 222.064 MHz, 2.048 MHz SR
2. `rtlsdr_read_async()` startet, befüllt Ringpuffer
3. OFDM-Processor sucht Null-Symbol → Sync
4. FIC-Handler liest Ensemble-Daten
5. MSC-Handler dekodiert Bayern-1-Subchannel
6. PCM → stdout → mpv → PulseAudio → Klinke/BT

> **Abweichung im heutigen PiDrive (v0.11.139):** dieser Pipe-Weg wird **nicht** genutzt.
> `dab_play.py` lässt `welle-cli` selbst auf ALSA ausgeben und entzieht ihm dazu die
> PipeWire-Umgebung — deshalb ist DAB über Bluetooth unerreichbar. Siehe
> [AUFTRAG-DAB-AUDIOWEG.md](../auftraege/AUFTRAG-DAB-AUDIOWEG.md).

### 12.2 Scan mit mux.json

```bash
# Kanal 11D scannen: welle-cli 20s laufen lassen, dann mux.json abfragen
welle-cli -c 11D -g -1 -C 1 -w 7981 2>/tmp/welle_scan.err &
sleep 20
curl -s http://127.0.0.1:7981/mux.json | python3 -m json.tool
pkill -f welle-cli
```

**Was aus mux.json gelesen werden soll:**

- `ensemble.label.label` → Ensemble-Name (leer = kein Lock)
- `ensemble.id` → `0x0000` = kein Lock
- `demodulator.snr` → Signal vorhanden?
- `demodulator.fic.numcrcerrors` → Lock-Qualität
- `services[].label.label` + `services[].sid` + `services[].url_mp3` → Senderliste

### 12.3 Spektrum-Diagnose (direkt per curl)

```bash
welle-cli -c 11D -g -1 -C 1 -w 7979 2>/dev/null &
sleep 5
python3 - << 'EOF'
import numpy as np, urllib.request
raw = urllib.request.urlopen('http://127.0.0.1:7979/spectrum').read()
data = np.frombuffer(raw, dtype=np.float32).reshape(-1, 2)
iq = data[:,0] + 1j * data[:,1]
power_db = 20 * np.log10(np.abs(iq) + 1e-12)
print(f"Spektrum: {len(power_db)} Bins, Peak {max(power_db):.1f} dB, Mittel {np.mean(power_db):.1f} dB")
EOF
pkill -f welle-cli
```

### 12.4 Diagnose-Endpunkte in der Reihenfolge

Empfohlene Reihenfolge beim Debuggen eines Kanals:

1. **`/mux.json`** → Ensemble vorhanden? SNR? FIC-Fehler?
2. **`/spectrum`** → Ist überhaupt ein Signal sichtbar?
3. **`/nullspectrum`** → TII erkennbar? Mehrere Sender?
4. **`/constellation`** → QPSK-Qualität (4 Cluster scharf = gut)?
5. **`/impulseresponse`** → Mehrwegeausbreitung? Sender-Entfernung?

### 12.5 Kardinale Fehler vermeiden

| Fehler | Symptom | Richtig |
|---|---|---|
| `-g 40` (dB statt Index) | `"Unknown gain count40"`, Gain=0 | `-g -1` oder `-g 22` |
| `-P` als PPM-Flag | keine PPM-Korrektur, kein Fehler | PPM wird intern durch Coarse Corrector korrigiert |
| `-C` bei der Wiedergabe | Ton wechselt alle 10 s den Sender | `-C` nur beim Scan |
| Port-Kollision | `bind()` schlägt fehl | Scan-Port `7981`, Diagnose-Port `7979`, Wiedergabe eigener Port |
| WAIT_LOCK zu kurz | SNR vorhanden, aber services=[] | 20s bei schwachem Signal |
| welle-cli nicht pkill'd | zweiter Start schlägt fehl | immer `pkill -f welle-cli` vor neuem Start |

---

*Erstellt auf Basis von welle.io-master Quellcode (src/welle-cli/, src/input/rtl_sdr.cpp,
src/backend/, src/various/channels.cpp) — dokumentiert für PiDrive v0.9.4, 2026-04-21.
Gegengelesen und in die Auftragslage eingeordnet am 2026-09-16 (v0.11.139).*
