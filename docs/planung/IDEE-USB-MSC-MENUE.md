# Idee: USB-MSC-Menü (ESP32-S3 / virtuelle MP3)

**Status:** Idee / Untersuchung — **kein** Arbeitsauftrag, **keine** Implementierung  
**Erfasst:** 2026-09-17  
**Anlass:** Nach negativer AVRCP-Browsing-Probe (G1) fehlt ein Weg zu einem echten Listenmenü am NBT Evo.  
**Bezug:**
- [../fahrzeug/BMW-AVRCP-PROBE.md](../fahrzeug/BMW-AVRCP-PROBE.md) — PSM `0x001B` wird nicht geöffnet → S3/Browsing gestrichen
- [../auftraege/AUFTRAG-MENUE-UND-GATEWAY.md](../auftraege/AUFTRAG-MENUE-UND-GATEWAY.md) — 3-Zeilen-Pfad bleibt BT-Zielbild
- [../menue/MENU-ERGONOMIE.md](../menue/MENU-ERGONOMIE.md) — Skip-only-Kosten des heutigen Menüs
- Schwesterprojekt `esp32.bt-gateway` — Classic-ESP32 für A2DP/AVRCP; **bewusst kein** ESP32-S3

---

## 1. Kerngedanke

Statt Menü und Metadaten über Bluetooth (AVRCP 3 Zeilen / gescheitertes Browsing) könnte ein Gerät am **USB-Anschluss des BMW** als Massenspeicher erscheinen. Der NBT Evo rendert dann seine **eigene USB-Medienliste** (Ordner, Dateien, Dreh-Drück) — genau die UI, die AVRCP-Browsing liefern sollte.

| Schicht | Vorschlag |
|---------|-----------|
| Hardware | ESP32-S3 mit nativem **USB-OTG** (Device-Mode), oder alternativ Pi als USB-Gadget |
| USB-Klasse | Mass Storage (MSC) — „virtueller Stick“ |
| Dateisystem | Virtuelles FAT; Ordner = Menüebenen, Dateinamen = Einträge |
| Aktivierung | BMW startet Wiedergabe einer Datei → Gerät erkennt, welche Sektoren/Datei gelesen werden → Trigger an PiDrive |
| Audio (Variante A) | Nur Navigation über USB; Ton weiter BT/Klinke |
| Audio (Variante B) | **On-the-fly-MP3**: beim Sektorlesen wird PCM live als MP3 geliefert |

Das ist eine **Alternative** zum BT-Gateway-Listenmenü, kein Ersatz für den bestehenden A2DP-Pfad und kein Auftrag an `esp32.bt-gateway` (dort bleibt Classic-ESP32 + WLAN/PDAP).

---

## 2. Warum die Idee jetzt auf dem Tisch liegt

1. **G1 negativ:** NBT Evo öffnet keinen AVRCP-Browsing-Kanal → kein Listenmenü über BT.
2. **3-Zeilen-Ergonomie:** Skip = Cursor, Play = Enter, oft kein Back — teure Navigation ([MENU-ERGONOMIE.md](../menue/MENU-ERGONOMIE.md)).
3. **USB-Medien-UI im Auto existiert bereits** (Radio/USB-Quellen am Fahrzeug) — ungenutzt für PiDrive-Steuerung.
4. **ESP32-S3** hat USB-OTG (TinyUSB MSC-Gadget machbar); der Classic-ESP32 des BT-Gateways hat das nicht. Chip-Rollen wären getrennt.

---

## 3. Varianten (zum späteren Entscheiden)

### Variante A — Menü-only (virtuelle Stub-MP3s)

- Pro Eintrag eine winzige stille/kurze MP3 (oder leerer Platzhalter mit gültigem Header).
- Auswahl = „diese Datei wird gestreamt“ → UID/Pfad → `pidrive` Trigger.
- Ton bleibt A2DP oder Klinke.

**Risiken:** BMW schaltet Quelle auf USB; Konflikte mit BT-Audio; Read-ahead kann falsche „Auswahl“ triggern.

### Variante B — On-the-fly-MP3 (Ton + Menü über USB)

- Virtuelles FAT; Dateiinhalt wird beim Lesen aus Live-PCM encodiert (MP3/CBR).
- Ein Pfad für Navigation und Audio.

**Risiken:** Seeking, Read-ahead, Bitrate, Puffer, CPU/Heap auf S3, Latenz; Live-Quellen (DAB, Spotify) sind kein statisches File — Forschungsaufwand.

### Variante C — Hybrid

- Statische/favorisierte Einträge als echte kurze Dateien.
- Live-Quellen nur als „Start …“-Stubs, die BT/Klinke anstoßen (wie A), oder nur Favoriten on-the-fly (wie B).

### Variante D — Ohne ESP: Spike mit echtem Stick

- Ordnerbaum + Stub-MP3s auf einem normalen USB-Stick in die BMW-Buchse.
- Misst Listenqualität, Scan-Zeit, Dateinamen, Play-Verhalten — **ohne** Firmware.
- Empfohlener **erster** Untersuchungsschritt (siehe §6).

### Variante E — Gadget am Raspberry Pi

- Pi als USB Device (soweit Port/Power das hergeben) statt ESP32-S3.
- Ein Rechner weniger; Konflikt mit Pi-USB-Host-Rollen (RTL-SDR, BT-Dongle, Strom).

---

## 4. Technische Baustellen (Checkliste für die Untersuchung)

| ID | Thema | Offene Frage |
|----|--------|--------------|
| U1 | NBT Evo USB-Medien | MSC und/oder MTP? FAT32-Limits? Max. Dateien/Ordnertiefe? |
| U2 | Bibliotheks-Scan | Indexiert das Auto beim Einstecken die ganze „Platte“? Dynamischer Menü-Rebuild → erneuter Scan? |
| U3 | Auswahl-Erkennung | Nur Block-Reads — wie unterscheidet man Directory-Scan / Prefetch von echtem Play? |
| U4 | Quellumschaltung | Kann USB-Navigation parallel zu BT-Audio laufen, oder erzwingt Play immer USB-Ton? |
| U5 | On-the-fly-Encoder | CBR-MP3 aus PCM in Echtzeit auf S3 (oder Pi) — CPU, Latenz, Seek-Stubs |
| U6 | Kabel / Buchse | Armlehnen-USB vs. OTG-Kabel; Stromversorgung ESP vs. Bus-Power |
| U7 | Rollentrennung | S3 = USB-UI (± Audio); Classic-ESP = BT-Gateway; Pi = Gehirn — oder alles am Pi? |
| U8 | Menüvertrag | Weiterhin kopflose UID-API ([AUFTRAG-MENUE-UND-GATEWAY.md](../auftraege/AUFTRAG-MENUE-UND-GATEWAY.md) Regel 3) — USB nur Renderer |
| U9 | Alternativen | Eigenes kleines Display; nur WebUI/Favoriten; 3-Zeilen weiter optimieren |

---

## 5. Abgrenzung — was diese Idee **nicht** ist

- **Kein** Wiedereinstieg in AVRCP-Browsing (S3 im Gateway-Sinne bleibt gestrichen, solange G1 gilt).
- **Kein** Auftrag, den BT-Gateway auf ESP32-S3 umzustellen (kein Classic BT auf S3).
- **Kein** Ersatz für M0/M1 Menü-API-Arbeit — der Baum bleibt die Quelle der Wahrheit.
- **Keine** Zusage, Variante B (on-the-fly) sei machbar; sie ist die ambitionierte Option zum Prüfen oder Verwerfen.

---

## 6. Vorgeschlagene Untersuchungsreihenfolge

Nicht implementieren, bis die Messungen eine Variante tragen.

1. **Stick-Spike (U1–U4):** vorbereiteter USB-Stick mit Ordnern/`Favoriten/`, `DAB/A-M/`, … und Stub-MP3s → Foto/Notizen: Listen-UI, Scan-Dauer, was bei Play passiert, paralleles BT?
2. **Entscheidung A vs. B vs. verwerfen:** wenn USB-UI schlecht oder Quelle immer USB-only ohne brauchbaren Hybrid → Idee schließen.
3. **Gadget-Spike:** TinyUSB MSC auf ESP32-S3 **oder** Pi-Gadget mit statischem Image (noch ohne Live-Encode).
4. **Auswahl-Heuristik:** welche Read-Muster = Aktivierung (Log am Gadget).
5. **Nur bei Bedarf:** On-the-fly-MP3-Machbarkeitsprobe (kurzer PCM→MP3-Stream, Seek-Verhalten am BMW).
6. **Alternativen parallel sammeln** in §7 / Folgecommits — z. B. lokales Display, reine Favoriten-3-Zeilen.

Ergebnis jeweils kurz hier oder unter `docs/fahrzeug/BMW-USB-MSC-PROBE.md` (anzulegen, sobald gemessen).

---

## 7. Weitere Alternativen (Platzhalter)

Zum Mitdenken, sobald USB-MSC bewertet ist:

| Alternative | Kurz |
|-------------|------|
| 3-Zeilen + Favoriten-first | Bestehender Pfad; Ergonomie statt neuer Hardware |
| WebUI / Handy im Auto | Echte Liste, aber nicht Lenkrad/iDrive |
| Kleines Zusatzdisplay am Pi/ESP | Eigene Liste; BMW-CID unberührt |
| MTP statt MSC | Falls NBT Evo MTP besser browse’t als Stick |
| iPod-Protokoll / andere Car-USB-Profile | Nur wenn Fahrzeug und Aufwand es hergeben — hier nicht vertieft |

---

## 8. Entscheidungsstatus

| Datum | Stand |
|-------|--------|
| 2026-09-17 | Idee dokumentiert; Untersuchung offen; **kein** Code, **kein** Hardware-Kaufzwang |
| — | Nächste Aktion: Stick-Spike am Fahrzeug (Variante D) oder bewusste Zurückstellung |

Wer diese Idee verwirft oder eine Variante festzieht: Statuszeile hier aktualisieren und im [Dokumentationsindex](../README.md) den Stand nachziehen.
