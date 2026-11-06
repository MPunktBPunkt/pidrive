# Connected Apps / AAIdrive — Stack-Abgleich (Pfad C)

**Stand:** 2026-11-06  
**Scope:** Primärquellen zu BMW Connected Apps und AAIdrive gegen die Arbeitsannahme „AAIdrive = offizieller Connected-Kanal (Pfad C), nicht AVRCP/A2DP“.  
**Fahrzeugbezug:** NBT / NBT Evo (PiDrive: F20 LCI 2017 = potenziell tauglich, sofern Apps/6NR bzw. ConnectedDrive-Apps aktiv).  
**Verwandt:** [`FORUM-RESEARCH-AVRCP-COVER-MSC-2026-11-06.md`](FORUM-RESEARCH-AVRCP-COVER-MSC-2026-11-06.md) · [`iDriveBt.md`](iDriveBt.md) · [`BMW-AVRCP-PROBE.md`](BMW-AVRCP-PROBE.md)

---

## 1. Urteil

Die Zusammenfassung **stimmt im Kern**. AAIdrive spricht die HU über denselben Stack wie offizielle Connected-Apps (BCL → Apache Etch / BMWRemoting → RHMI/AV/CDS/SAS). Das ist **Pfad C** — parallel zu PiDrive-Pfad A (A2DP+AVRCP) und Pfad B (USB-MSC).

Wichtige Nuancen aus den Primärquellen (nicht in jeder Kurzfassung enthalten):

| Punkt | Korrektur / Schärfung |
|-------|------------------------|
| „Eigene XML-Menüs“ | Layouts sind an das **Auth-Zertifikat gehasht (SHA256-Whitelist)**. Freie Widget-XML scheitert; Flexibilität über `rhmi_setProperty` + Datenmodels auf **freigegebenen** Layouts. |
| Tunnel | Connected/MyBMW stellt den BCL-Tunnel + Security-Modul; AAIdrive hängt als Etch-Client am **localhost-TCP-Proxy**. BclCarLink ersetzt nur den Link-Aufbau, **nicht** die Security-Abhängigkeit. |
| Voraussetzung Auto | Apps-Unterstützung: **6NR** und/oder ConnectedDrive-Apps / Apps-Checkbox (ID5+); Mini: SA6NM. Ohne das kein Pfad C. |
| Audio | Connected steuert Fokus/UI; Ton oft weiter über **BT A2DP** (bes. ab Android Oreo: USB-AOA-Audio für ältere MY eingeschränkt). |
| Zukunft | Connected-Apps-Protokoll auf **Live Cockpit / ID7+** deprecatet (Android Auto statt Remote-Apps). Für NBT Evo relevant, für neue HUs nicht. |
| Quellenlage | Wenig klassische Foren; belastbar sind **hufman-Writeup**, **BMWConnectedAnalysis**, **AAIdrive / IDriveConnectKit / BclCarLink / Addons**. |

---

## 2. Architektur (verifiziert)

```
Phone-App (AAIdrive / Spotify / …)
        │  TCP localhost (Intent + fester Port)
        ▼
BMW Connected / MyBMW  ── SecurityService (Challenge/Nonce, JNI)
        │
        │  BCL Multiplex (USB AOA und/oder BT-SPP; BT-Apps ab ~2017)
        ▼
HU NBT / NBT Evo
        │
        └── pro BCL-Stream: Apache Etch RPC (Magic 0xDEADBEEF)
                 ├── SAS   Auth (BMW-CA-Zertifikat + Nonce-Signatur)
                 ├── RHMI  Remote-HMI (Layout/Resources, Models, Events)
                 ├── AV    Audio-Kontext / Entertainment-Quelle
                 └── CDS   Car Data Service (Live-Fahrzeugdaten)
```

**Nicht** Teil dieses Stacks: AVRCP Cover Art (BIP), generisches A2DP-Metadaten-Push als Cover-Pfad, USB-MSC.

---

## 3. Schichten — Abgleich

### 3.1 Transport

- USB (Android Open Accessory) und/oder Bluetooth SPP.
- Ab Modelljahr ~2017: Connected Apps auch über reines Bluetooth („Bluetooth Apps“).
- Connected/MyBMW baut den Kanal und exponiert einen **TCP-Proxy auf dem Phone**; Apps verbinden sich lokal, nicht direkt auf den SPP-Socket.
- **BclCarLink:** experimenteller Ersatz für den BCL-Link (Debug/Stabilität); Security-Modul bleibt bei MyBMW/Mini/SupraConnect.

### 3.2 BCL

- Multiplex mehrerer logischer Verbindungen über einen seriellen/USB-Kanal (Connection-IDs).
- Darauf sitzen u. a. Etch-Streams; Handshake/Watchdog laut Analyse vorhanden.
- Wireshark-Lua / Etch-Debug-Hashes: aus dem hufman-Writeup.

### 3.3 Apache Etch (BMWRemoting)

- RPC mit Magic `0xDEADBEEF`.
- IDL rekonstruiert in **IDriveConnectKit** (Proxy-Objekte für Apps).
- Dienste u. a.: `sas_*`, `rhmi_*`, AV, CDS, Version/Info.

### 3.4 SAS (Auth)

- PKCS7-Zertifikat, von BMW-CA signiert; Nonce-Challenge, Signaturantwort.
- Zertifikate aus offiziellen APKs / ContentProvidern extrahierbar; Permissions/Asset-Whitelist im Zertifikat.
- Ohne gültiges Cert + Challenge-Antwort: kein RHMI-App-Slot.

### 3.5 RHMI

- App sendet u. a. `rhmi_setResource` (XML-Widget-Layout + Zip: Grafik/Texte), dann `rhmi_setData` / `rhmi_setProperty`, Events über `rhmi_addActionEventHandler` → `rhmi_onActionEvent`.
- HU rendert **native** iDrive-Widgets; Controller-Events gehen zurück an die Phone-App.
- **Whitelist:** geänderte Layouts/Assets werden abgelehnt, wenn SHA256 nicht zum Cert passt → AAIdrive „leiht“ typischerweise **offizielle Layout-/Icon-Slots** (z. B. Audioplayer/Spotify/News-ähnlich) und füllt Models.

### 3.6 AV + Cover

- MusicAppMode: Audio-Kontext anfordern, Hardware-Buttons, Resume.
- ID5+: „global coverart“ im Homescreen / Multimedia-Panel — über **RHMI/Connected**, nicht AVRCP-BIP.
- Praktischer Nutzerpfad: Quelle **App** (Spotify/Audioplayer) wählen, nicht „Bluetooth“.

### 3.7 CDS

- Live-Daten für Anzeigen/Addons (Geschwindigkeit, Multimedia-Status, …).
- IDriveConnectAddons: z. B. Scrobbler liest Multimedia-Metadaten (BT/USB; Radio oft nicht).

---

## 4. AAIdrive vs. Connected — Rollen

| Komponente | Rolle |
|------------|--------|
| **MyBMW / Connected** | Tunnel-Provider + Security-Modul; Apps-Checkbox / Connection Assistant |
| **AAIdrive** | Unoffizielle Connected App(s): Notifications, Music-Browser, Nav-Hooks, optional Maps/Mirror (Addons) |
| **IDriveConnectKit** | Etch-IDL + RHMI-Helper-Library |
| **IDriveConnectAddons** | Extra-RHMI-Apps / CDS-Consumer |
| **BclCarLink** | Optionaler BCL-Link; ersetzt MyBMW-Security **nicht** |

AAIdrive-README (Kernaussage): *„without any modifications or hacks“* am Auto — Nutzung der **offiziellen Connected-Apps-Technologie** mit extrahierten Certs/Ressourcen. Das ist **kein HU-Root**, aber auch **kein** BMW-SDK-Lizenzprodukt.

Projektstatus AAIdrive (Stand Quellen 2026-11): feature-complete / Maintenance; Autor ohne eigenes Compatible-Auto — externe Beiträge nötig.

---

## 5. Einordnung für PiDrive (A / B / C)

| Pfad | Mechanismus | Menü / Cover | PiDrive |
|------|-------------|--------------|---------|
| **A** | A2DP Source + AVRCP Target + MPRIS | 3 Textzeilen; Cover nein | aktiv |
| **B** | USB-MSC + ID3/APIC | HU-USB-UI + Cover | aktiv / Messung |
| **C** | Connected BCL→Etch→RHMI (+ AV) | Native Connected-Menüs + Cover | Forschung / optional |

**Implikationen**

1. AAIdrive/Connected lösen **nicht** eure MSC-Host-Fragen und ersetzen **nicht** den Pi als A2DP-Source.
2. Reiche BT-UI + Cover = Pfad C → Phone-seitig (oder Pi emuliert Connected-Client + braucht Tunnel/Certs/6NR).
3. Hybrid denkbar: Pi liefert Ton (A oder B), Phone/AAIdrive liefert RHMI-Steuerung (C) — zwei Geräte, ein UX; Architekturaufwand hoch.
4. Pi als vollständiger Connected-Peer (ohne Phone): BclCarLink-Idee + SAS/Certs + Etch — **eigenes Teilprojekt**, Scope weit über AVRCP/MSC.
5. F20-Voraussetzung klären: Apps/6NR bzw. ConnectedDrive-Apps aktiv? Sonst ist Pfad C am Fahrzeug tot.

---

## 6. Offene Punkte für die Connected-Forschung

| ID | Frage | Hinweis |
|----|-------|---------|
| C1 | Hat der F20 Apps (6NR / Checkbox)? | Ohne das kein Feldtest Pfad C |
| C2 | MyBMW vs. Connected Classic vs. BclCarLink am Fahrzeug | Tunnel-Stabilität |
| C3 | Welches Cert/Layout nutzt AAIdrive MusicAppMode (ID5)? | Cover-Fähigkeit |
| C4 | Audio-Fokus AV vs. paralleler Pi-A2DP | Konflikt / Ducking |
| C5 | 30-min Metadata-Freeze: nur Connected-UI oder auch AVRCP? | Getrennt messen |
| C6 | Lohnt Pi-seitige Etch-Emulation vs. Phone+AAIdrive belassen? | Produktentscheid |

---

## 7. Quellen

| ID | Quelle | Rolle |
|----|--------|-------|
| S1 | [hufman — BMW Connected Apps Protocol](https://hufman.github.io/stories/bmwconnectedapps) | Primär: BCL, Etch, SAS, RHMI-Whitelist, Fake Car |
| S2 | [BMWConnectedAnalysis](https://bimmergestalt.github.io/BMWConnectedAnalysis/) | Themenseiten (BCL, Etch, RHMI, CDS, Auth, …) |
| S3 | [BimmerGestalt/AAIdrive](https://github.com/BimmerGestalt/AAIdrive) | Produkt/Features, Voraussetzungen 6NR, ID5 Cover, BT-Apps |
| S4 | [IDriveConnectKit](https://github.com/BimmerGestalt/IDriveConnectKit) | Etch-IDL + RHMI-Parsing |
| S5 | [IDriveConnectAddons](https://github.com/BimmerGestalt/IDriveConnectAddons) | Beispiel-RHMI-Apps / CDS |
| S6 | [BclCarLink](https://github.com/BimmerGestalt/BclCarLink) | Experimenteller BCL-Link; Security bleibt bei MyBMW |
| S7 | [Bimmer Gestalt Übersicht](https://bimmergestalt.github.io/) | Projektlandkarte |

Abruf: 2026-11-06. Foren (Bimmerfest etc.) liefern Nutzer-Anekdoten zu Cover/Connected; der **Protokoll-Stack** kommt aus S1–S6.
