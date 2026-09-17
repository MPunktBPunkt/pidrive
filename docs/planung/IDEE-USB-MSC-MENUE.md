# Idee: USB-MSC-Menü (ESP32-S3 / virtuelle MP3)

**Status:** Idee ausgearbeitet — **kein** Arbeitsauftrag, **keine** Implementierung  
**Erfasst:** 2026-09-17 · **Weiterentwickelt:** 2026-09-17  
**Anlass:** Nach negativer AVRCP-Browsing-Probe (G1) fehlt ein Weg zu einem echten Listenmenü am NBT Evo.  
**Bezug:**
- [../fahrzeug/BMW-AVRCP-PROBE.md](../fahrzeug/BMW-AVRCP-PROBE.md) — PSM `0x001B` wird nicht geöffnet → S3/Browsing gestrichen
- [../auftraege/AUFTRAG-MENUE-UND-GATEWAY.md](../auftraege/AUFTRAG-MENUE-UND-GATEWAY.md) — 3-Zeilen-Pfad bleibt BT-Zielbild
- [../menue/MENU-ERGONOMIE.md](../menue/MENU-ERGONOMIE.md) — Skip-only-Kosten des heutigen Menüs
- Schwesterprojekt `esp32.bt-gateway` — Classic-ESP32 für A2DP/AVRCP; **bewusst kein** ESP32-S3
- Referenzprodukt: [Dension DAB+U](https://www.ars24.com/dab-nachruestung/16605/dension-dab-u-interface-zum-nachruesten-von-dab-am-werks-autoradio-per-usb) (virtuelle MP3 über USB)

---

## 1. Kerngedanke

Statt Menü und Metadaten über Bluetooth (AVRCP 3 Zeilen / gescheitertes Browsing) erscheint ein Gerät am **USB-Anschluss des BMW** als Massenspeicher. Der NBT Evo rendert seine **eigene USB-Medienliste** (Ordner, Dateien, Dreh-Drück) — dieselbe UI-Idee, die AVRCP-Browsing liefern sollte.

| Schicht | Vorschlag |
|---------|-----------|
| Hardware | ESP32-S3 mit nativem **USB-OTG** (Device-Mode), oder Pi als USB-Gadget |
| USB-Klasse | Mass Storage (MSC) — „virtueller Stick“ |
| Dateisystem | Virtuelles FAT; Ordner = Menüebenen, Dateinamen = Einträge / Aktionen |
| Aktivierung | BMW spielt eine Datei → Gerät erkennt Read-Muster → Trigger / Senderwechsel |
| Audio | **On-the-fly-MP3** über USB (siehe §3 / §9 — Hybrid mit BT ist der schwächere Pfad) |

Das ist eine **Alternative** zum BT-Listenmenü, kein Auftrag an `esp32.bt-gateway`.

---

## 2. Warum die Idee jetzt auf dem Tisch liegt

1. **G1 negativ:** kein AVRCP-Browsing → kein Listenmenü über BT.
2. **3-Zeilen-Ergonomie** ist teuer ([MENU-ERGONOMIE.md](../menue/MENU-ERGONOMIE.md)).
3. **USB-Medien-UI** im Auto existiert; Dension beweist, dass Werksradios virtuelle MP3-Sticks akzeptieren.
4. **BMW NBT / NBT Evo** sind in der Dension-Welt ausdrücklich adressiert (Config/Firmware-Matrix) — die Fahrzeugklasse ist kein Blindflug.

---

## 3. Referenz: Warum Dension DAB+U gelingt

Produkt: USB-powered DAB-Empfänger, erscheint dem Werksradio als **USB-Stick mit MP3-Dateien**. Sender = virtuelle MP3s; Funktionen wie Scan/About ebenfalls als abspielbare Dateien (`Settings/Scan.mp3`). Bedienung = normale USB-Medien-UI + Lenkrad Next/Prev.

Quellen: [ars24-Produktseite](https://www.ars24.com/dab-nachruestung/16605/dension-dab-u-interface-zum-nachruesten-von-dab-am-werks-autoradio-per-usb), [dension.com USB-DAB](http://dab.dension.com/usb-connected-dab/), Support [Konfiguration](https://techsupport.dension.com/602008-B-Configuration) / [Kompatibilität](https://techsupport.dension.com/781736-A-First-steps---compatibility), BMW-Hinweise [dension.de/dab/dabu-bmw](https://www.dension.de/dab/dabu-bmw).

### 3.1 Was Dension *technisch* macht (abgeleitet)

| Mechanismus | Bedeutung |
|-------------|-----------|
| **Ein Pfad für UI und Ton** | Das Radio spielt „MP3 von USB“. Dension liefert den Bitstream on-the-fly aus dem DAB-Decoder. Kein paralleles BT/Klinke für denselben Hörvorgang. |
| **Virtuelles FAT + virtuelle Dateien** | Senderliste und Befehle sind Dateinamen/Ordner — das HU braucht kein Spezialprotokoll. |
| **Puffer vor dem HU (ABSA)** | *Automatic Buffer Size Assessment*: das Gerät puffert 4–60 s (modellabhängig), damit das Read-ahead / die USB-Wiedergabe des Radios nicht stockt. Umschalten kostet bewusst Zeit. |
| **HU-spezifische Config-Files** | `K61`, `K8`, … ändern USB-/Timing-Verhalten. Ohne passendes File: nicht erkannt oder unbrauchbar. |
| **Firmware-Varianten** | Klassisches MSC vs. „Gerätesteuerung / iPod-ähnlich“ (z. B. `DBU3P211`) — je nach HU-Software. |
| **Enger Produktumfang** | Nur DAB(+)/DMB-R → flache Senderliste + wenige Action-MP3s. Kein Spotify, kein 287-Knoten-Baum, kein Live-Menü-Rebuild jede Sekunde. |
| **Strom vom USB-Port** | Kein Extra-Kabel; Gerät hängt dauerhaft an der Werksbuchse. |

### 3.2 BMW in der Dension-Matrix (Relevanz für PiDrive)

Aus Händler-/Support-Listen (Auszug):

| HU | Hinweis |
|----|---------|
| BMW NBT (SW `MN-…`) | Config **K61**, Buffer ~**5 s** |
| BMW CIC (`MX-…` / `MV-…`) | K62, ~10 s |
| BMW NBT Evo / EntryNav2 (F-Serie, SW z. B. `MB…`, `MT…`) | Feldberichte: Firmware **DBU3P208/P211** bzw. 1.22+K61; Umschaltzeiten von ~1–2 s bis ~5 s je Setup |

**Fazit:** Das Prinzip „virtueller Stick + on-the-fly-MP3“ ist am **BMW-USB-Medienpfad** inklusive NBT-Evo-Fahrzeugen bereits kommerziell bewiesen — nicht nur an Opel/Toyota.

Einschränkungen laut Produkt/Support (lernen!):

- Nicht jedes Werksradio; Config **muss** passen.
- Sender, deren Name mit `.` beginnt, waren zeitweise nicht abspielbar.
- Lange Bufferzeiten (bis 60 s) bei manchen HUs sind akzeptiertes Produktschicksal.
- Metadaten/Titelzeile je HU unzuverlässig (Kundenfeedback: oft nur Sendername).

### 3.3 Warum es *dort* klappt — und was PiDrive schwerer hat

| Dension | PiDrive-Idee |
|---------|----------------|
| Eine Quelle (DAB), eine Audio-Pipeline | Viele Quellen (DAB, FM, Webradio, Spotify, Scanner, Library) |
| Senderliste nach Scan relativ stabil | Dynamischer Menübaum, Statuszeilen, Rebuilds |
| Umschalten = neuer Stream + Puffer ok | Nutzer erwarten snappiges Menü (Favoriten, Zurück) |
| Next/Prev = Senderwechsel | Next/Prev muss Cursor *oder* Track bedeuten — Semantik klären |
| Jahre Config-Matrix pro HU | Wir starten bei **einem** Auto (NBT Evo F20/F21) |
| Kein BT parallel nötig | Heute hängt PiDrive an A2DP — Parallelbetrieb verwirrt |

**Kurz:** Dension gelingt, weil sie **Variante B** (Ton = USB-MP3) mit **Puffer**, **HU-Tuning** und **minimaler Dateibaum-Semantik** liefern — nicht weil USB magisch ein Menü-API freischaltet.

---

## 4. Voraussetzungen, damit es bei PiDrive gelingen kann

Ohne diese Voraussetzungen ist die Idee eher Spielerei als Produktpfad. Als Checkliste (P = Pflicht zum Erfolg, W = wichtig, O = optional/später).

### 4.1 Fahrzeug & USB-Host (BMW)

| ID | Prio | Voraussetzung |
|----|------|----------------|
| P-V1 | P | NBT Evo erkennt das Gadget als **USB-Massenspeicher** und zeigt Ordner/Dateien in der Medien-UI (Dreh-Drück). |
| P-V2 | P | NBT Evo **spielt MP3 von USB** (nicht nur listet) — sonst kein on-the-fly-Ton. |
| P-V3 | P | Dateinamen/Ordner sind in der UI lesbar genug (Länge, Zeichensatz, kein führender `.`). |
| P-V4 | W | Scan-/Index-Verhalten ist erträglich (Erststecken, nach Rebuild). Dension rebootet nach Scan sichtbar — wir müssen Rebuild-Politik planen. |
| P-V5 | W | Next/Prev am Lenkrad steuern USB-Titel (Sender/Einträge), nicht nur stumm. |
| O-V6 | O | ID3/Anzeige von „Now Playing“-Text über Dateiname oder Tags — nice-to-have, bei Dension schon wackelig. |

**Gate:** Stick-Spike (§7) muss P-V1–P-V3 am eigenen Fahrzeug grün machen, bevor Hardware/Firmware lohnt.

### 4.2 Architektur-Entscheidung: ein Audio-Pfad

| ID | Prio | Voraussetzung |
|----|------|----------------|
| P-A1 | P | Im USB-Hörbetrieb gilt: **Ton kommt vom USB-MP3-Stream** (wie Dension). Variante A (nur Menü über USB, Ton über BT) ist als Hauptziel **abzulehnen** — Quellumschaltung und „stille Stub-MP3“ kämpfen gegen das HU. |
| P-A2 | P | Klarer Betriebsmodus: z. B. `source=usb_gadget` vs. `source=bt` — nicht beides gleichzeitig für denselben Inhalt. |
| W-A3 | W | Live-Quellen (DAB/Spotify/…) → PCM → **CBR-MP3 in Echtzeit** mit ausreichend Vorlaufpuffer (Dension: oft 5–15 s, manchmal mehr). |
| W-A4 | W | Seek/Read-ahead des BMW: Datei muss als „lang genug“ / kontinuierlich lesbar erscheinen (virtuelle Größe, Ringpuffer, Stub am Dateiende). |
| O-A5 | O | Klinke/BT bleiben für Fälle ohne USB-Gadget oder Debugging. |

### 4.3 Virtuelles Dateisystem & Semantik

| ID | Prio | Voraussetzung |
|----|------|----------------|
| P-F1 | P | Stabiles virtuelles FAT (Sektor-Reads deterministisch, keine Korruption bei Parallel-Reads). |
| P-F2 | P | Abbildung Menübaum → Ordner/Dateien über die **kopflose UID-API** (Renderer, keine zweite Menülogik). |
| W-F3 | W | Action-Dateien analog Dension (`Scan.mp3`, `Zurueck.mp3`, `Refresh.mp3`) für Befehle ohne „Song“. |
| W-F4 | W | Rebuild-Strategie: möglichst **selten** die Directory-Struktur ändern; Status lieber in Now-Playing-Name/ID3 oder einer einzigen `Status.mp3`-Metazeile — sonst HU-Rescan. |
| W-F5 | W | Auswahl-Erkennung: anhaltendes sequentielles Lesen einer Datei = Play; Directory-Scan ≠ Aktivierung (Heuristik + Logs). |
| O-F6 | O | Flache „Stations“-Ansicht für Radio (dension-ähnlich) *zusätzlich* zum tiefen PiDrive-Baum — bessere UX für den Hauptfall. |

### 4.4 Timing / Puffer (das eigentliche Produktheimnis)

| ID | Prio | Voraussetzung |
|----|------|----------------|
| P-T1 | P | Ausreichend großer **Jitter-/Vorbuffer**, abgestimmt auf NBT-Evo-Read-ahead (Vorbild ABSA; Startwert z. B. 3–8 s, messen). |
| P-T2 | P | Akzeptanzkriterium für Sender-/Quellenwechsel (z. B. ≤ 5 s hörbar) — oder bewusst kommuniziert wie bei Dension. |
| W-T3 | W | Tuning-Parameter (Sector size, Max LUN readiness, stall timing, reported capacity) — das Äquivalent zu Dension-`Kxx`-Files, auch wenn nur für *ein* Auto. |
| W-T4 | W | Unterbrechungsfreie Wiedergabe ≥ 2–3 min am Stück als Abnahmetest (Dension-Support-Kriterium). |

### 4.5 Hardware & Rollen

| ID | Prio | Voraussetzung |
|----|------|----------------|
| P-H1 | P | USB **Device**-Port zur BMW-Buchse (Kabel A–A / werksseitig), stromversorgt (Bus oder 5 V). |
| W-H2 | W | Dediziertes Gadget (ESP32-S3 oder anderer MCU mit native USB) **oder** Pi-Gadget — Konflikt mit RTL-SDR/BT-Dongle am Pi klären. |
| W-H3 | W | Ausreichend CPU/RAM für MP3-Encode + MSC + Link zum Pi (WLAN/UART/USB-Host-nebenbei). |
| O-H4 | O | Bypass/zweite USB-Buchse wie Dension Connector Port (Stick weiter nutzbar). |

**Chip-Hinweis:** ESP32-S3 eignet sich für USB-OTG; Classic-BT-Gateway bleibt separates Gerät. Zwei Rollen nicht auf einen S3 zwingen.

### 4.6 Software-Vertrag PiDrive

| ID | Prio | Voraussetzung |
|----|------|----------------|
| P-S1 | P | Menü bleibt UID-Baum + Navigations-API; USB-Gadget = weiterer Renderer. |
| P-S2 | P | Protokoll Pi ↔ Gadget: welche UID spielt, PCM oder schon MP3, Rebuild-Hints, Buffer-Status. |
| W-S3 | W | Quellenstart: „Play Datei X“ = `activate(uid)` inkl. Encoder-Umschaltung. |
| W-S4 | W | CLI/Abnahme: `pidrivectl` muss Gadget-Status und „welche Datei wird gelesen“ zeigen (Fahrzeug-Debug ohne Display). |

### 4.7 Produkt- / UX-Voraussetzungen

| ID | Prio | Voraussetzung |
|----|------|----------------|
| W-U1 | W | Nutzer akzeptiert USB als Hörquelle (nicht „Bluetooth Audio“-Kachel) — anderes mentales Modell. |
| W-U2 | W | Tiefe Menübäume vs. flache Senderliste: ggf. **zwei Präsentationen** (Radio-flach / System-tief). |
| O-U3 | O | Parallele BT-Steuerung nur für Nicht-Hör-Fälle (Telefon, …) klar trennen. |

---

## 5. Varianten (neu bewertet)

### Variante A — Menü-only (Stub-MP3s, Ton über BT) — **unwahrscheinlich**

Bleibt als Spike denkbar, aber Dension und die HU-Logik sprechen dagegen: Play auf USB **ist** die Hörquelle. Stubs erzeugen Stille oder Konflikt.

### Variante B — On-the-fly-MP3 (Ton + Menü über USB) — **Zielbild, falls Idee trägt**

Entspricht Dension. Voraussetzungskatalog §4 zielt hierauf.

### Variante C — Hybrid / abgestuft

- Phase 1: nur Radio-Favoriten als flache virtuelle Senderliste (dension-ähnlich).
- Phase 2: Ordner für Quellengruppen.
- Phase 3: voller PiDrive-Baum + Action-MP3s.  
Sinnvoll als Risikominimierung.

### Variante D — Stick-Spike (ohne ESP) — **erster Gate**

Echter Stick mit Ordnern + kurzen echten MP3s → misst P-V1–P-V5 ohne Firmware.

### Variante E — Gadget am Pi

Möglich, aber Host-Device-Konflikt und Strom am USB-C des Pi prüfen.

### Variante F — Dension kaufen / nachbauen als Messgerät — **optional**

Ein DAB+U am eigenen NBT Evo zeigt Bufferzeiten, Dateibaum-UX und ob „Gerätesteuerungs“-Firmware nötig ist — teurer Shortcut zu P-T*/P-V*.

---

## 6. Technische Baustellen (Untersuchung)

| ID | Thema | Offene Frage |
|----|--------|--------------|
| U1 | NBT Evo USB-Medien | MSC ok? Limits Dateien/Tiefe/Zeichensatz? |
| U2 | Bibliotheks-Scan | Index beim Stecken? Verhalten nach Directory-Change? |
| U3 | Auswahl-Erkennung | Prefetch vs. Play — Schwellen? |
| U4 | Quellumschaltung | (für Variante A) — eher obsolet wenn B Pflicht ist |
| U5 | On-the-fly-Encoder | CBR-MP3, Bitrate, Latenz, CPU auf S3 vs. Encode auf Pi |
| U6 | Kabel / Buchse | Armlehne, Strombudget |
| U7 | Rollentrennung | S3-Gadget vs. Pi-Gadget vs. Classic-ESP BT |
| U8 | Menüvertrag | UID-API → FAT-Export |
| U9 | Alternativen | Display, WebUI, 3-Zeilen |
| U10 | **HU-Tuning** | Welche Timing-/Descriptor-Parameter braucht *unser* NBT Evo? (Dension-K61/DBU3P211-Äquivalent) |
| U11 | **Puffermaß** | Gemessene Umschalt- und Startzeit bis Ton stabil |
| U12 | **Scope-Schnitt** | Reicht flache Radiolsiste als MVP, oder nur volles Menü? |

---

## 7. Vorgeschlagene Untersuchungsreihenfolge

Nicht implementieren, bis Gates grün sind.

1. **Stick-Spike (Variante D):** Ordner `Stations/`, `Settings/Scan.mp3`-Analogon, echte kurze MP3s → Fotos, Scan-Dauer, Next/Prev, Dateinamenlimits.  
   → Gate für P-V1–P-V5.
2. **Optional Variante F:** Dension am eigenen Auto — Referenz für Buffer/UX (kein Muss).
3. **Entscheidung Scope:** MVP = flache Sender/Favoriten (dension-ähnlich) **oder** Abbruch zugunsten 3-Zeilen/WebUI.
4. **Gadget-Spike:** TinyUSB MSC, statisches Image, eine Endlos-MP3 aus Datei (noch kein Live-Encode).
5. **Live-Encode-Spike:** PCM→MP3 + Vorbuffer; 3 min Dauerbetrieb am BMW.
6. **Auswahl-Heuristik + Action-MP3s.**
7. **Anbindung PiDrive-UID-API** (Export-Renderer), erst dann tiefer Baum.

Ergebnis: `docs/fahrzeug/BMW-USB-MSC-PROBE.md` (anzulegen nach Messung).

---

## 8. Weitere Alternativen

| Alternative | Kurz |
|-------------|------|
| 3-Zeilen + Favoriten-first | Bestehender BT-Pfad |
| WebUI / Handy | Echte Liste, nicht iDrive |
| Kleines Zusatzdisplay | Eigene Liste |
| MTP statt MSC | Nur wenn Spike MSC scheitert und MTP am NBT besser ist |
| iPod-/AOA-Profile | Dension nutzt teils „Gerätesteuerung“-FW — eigener großer Ast |
| Dension nur für DAB, PiDrive weiter BT | Produktspaltung, kein einheitliches Menü |

---

## 9. Entscheidungsstatus

| Datum | Stand |
|-------|--------|
| 2026-09-17 | Idee dokumentiert |
| 2026-09-17 | Ausarbeitung: Dension-Analyse, Voraussetzungskatalog P/W/O, Variante B als Zielbild, Stick-Spike als Gate |
| — | Nächste Aktion: Stick-Spike am Fahrzeug **oder** bewusste Zurückstellung |

**Arbeitshypothese:** Gelingen ist möglich, *wenn* wir denselben Vertrag wie Dension eingehen — **USB = Ton + UI**, Puffer und HU-Tuning ernst nehmen, Scope zuerst klein (Sender/Favoriten) halten. Scheitert der Stick-Spike an P-V1–P-V3, ist die Idee für dieses Fahrzeug tot; Scheitert nur der tiefe Menübaum, bleibt ein dension-artiger Radio-MVP denkbar.

Wer verwirft oder festzieht: Status hier und im [Dokumentationsindex](../README.md) nachziehen.
