# Connected Apps / AAIdrive — Stack-Abgleich (Pfad C)

**Stand:** 2026-11-06 (Abend²: technology-audit PR #34 — CarAPI-Proxy, Cleartext, AIDL/MainService)  
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
| Tunnel | Connected/MyBMW stellt BCL-Tunnel + localhost-TCP; AAIdrive = Etch-Client. BclCarLink ersetzt nur den Link, **nicht** Security. |
| SecurityService | Classic Connected **≤5.1** exportierte `.SECURITY_SERVICE` Binder. **≥5.1 / MyBMW:** Export **weg** — moderne Signierung **UNKNOWN**. „MyBMW liefert signChallenge“ als Default **REJECTED**. |
| CarAPI vs AAIdrive | **Zwei Phone-Pfade:** AAIdrive/Kit = eigener Etch-Client; CarAPI (Spotify u. a.) → Connected führt `sas_*` **stellvertretend** (ContentProvider-Cert). |
| Cleartext | Analysis: Connected-Apps-Pfad „Nothing is encrypted.“ → SAS/Etch in BCL DATA im Klartext dissectierbar, sobald Tunnel sichtbar (FX-G3-01). |
| Voraussetzung Auto | Apps-Unterstützung: **6NR** und/oder ConnectedDrive-Apps / Apps-Checkbox (ID5+); Mini: SA6NM. Ohne das kein Pfad C. |
| Audio | Connected steuert Fokus/UI; Ton oft weiter über **BT A2DP** (bes. ab Android Oreo: USB-AOA-Audio für ältere MY eingeschränkt). |
| Zukunft | Connected-Apps-Protokoll auf **Live Cockpit / ID7+** deprecatet (Android Auto statt Remote-Apps). Für NBT Evo relevant, für neue HUs nicht. |
| Quellenlage | Wenig klassische Foren; belastbar sind **hufman-Writeup**, **BMWConnectedAnalysis**, **AAIdrive / IDriveConnectKit / BclCarLink / Addons**. |

---

## 2. Architektur (verifiziert)

```
Phone: BMW Connected / MyBMW
        │  USB-AOA und/oder BT-SPP
        │  BCL knock + handshake  →  Multiplex zur HU
        │  broadcast ACTION_CAR_ACCESSORY_ATTACHED
        │       extras: EXTRA_HOST=127.0.0.1, EXTRA_PORT, instance_id, …
        ▼
Phone: AAIdrive / Spotify / CarAPI-App
        │  Registration: CONNECTED_APP_INSTALLED ↔ ACTION_CAR_APPLICATION_REGISTERING
        │  TCP localhost → Etch über Connected-Tunnel
        ▼
HU: Etch / BMWRemoting
        ├── SAS   Auth (P7B → Challenge → Signatur → sas_login)
        ├── AM    Application Manager (Icon/Placeholder ≠ volle RHMI-Init)
        ├── RHMI  Layout/Resources (SHA256-Whitelist aus Cert)
        ├── AV    Audio-Kontext / Entertainment-Quelle
        └── CDS   Car Data Service
```

**Nicht** Teil dieses Stacks: AVRCP Cover Art (BIP), generisches A2DP-Metadaten-Push als Cover-Pfad, USB-MSC.

**Rolle ESP/hu-probe vs. Phone:** Ein Direct-`18D1:2D00`-DUT emuliert nur USB-Accessory-Identity — **nicht** den Connected-Peer (BCL-Knock, TCP-Tunnel, Etch, SAS). Das sind unterschiedliche Rollen.

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
- **Cleartext [D]:** Analysis `analysis-approach.md` — „Nothing is encrypted.“ SAS/Etch/RHMI in BCL-DATA sind bei sichtbarem Tunnel **nicht** TLS-geschützt (Desk). Erhöht Wert von Feld **FX-G3-01**; ersetzt keine Sichtbarkeit, wenn Bulk/BCL absent bleibt. Audit: [`bmw-connected-sas-auth-2026-11-06`](../../../technology-audit/audits/bmw-connected-sas-auth-2026-11-06/) (`EVID-SAS-025`).

### 3.3 Apache Etch (BMWRemoting)

- RPC mit Magic `0xDEADBEEF`.
- IDL rekonstruiert in **IDriveConnectKit** (Proxy-Objekte für Apps).
- Dienste u. a.: `sas_*`, `rhmi_*`, AV, CDS, Version/Info.

### 3.4 SAS (Auth) — Authentication ≠ Authorization

Quelle: [Authentication](https://bimmergestalt.github.io/BMWConnectedAnalysis/authentication/) **[D]**.

1. `sas_certificate(P7B)` → HU liefert Challenge `byte[16]`
2. Client signiert → `sas_login(byte[512])`

**Challenge-Formel** (Android / Cert mit `SAS.CertificateType`):

```
response = RSA-MD5-Signatur( challenge XOR MD5(LE uint32(2)) )
         = RSA-MD5-Signatur( challenge XOR MD5("\x02\x00\x00\x00") )
```

Ältere iOS-Certs ohne `SAS.CertificateType`: kein XOR; Challenge direkt signieren.

**Zwei Certs im P7B:** `APP_AUTH` (Signatur-Pubkey) + `APP` (Permissions `AVS`/`CDS`/`RHMI`/`Make`, `SAS.Digests.*` SHA256-Whitelist). HU: `CRHMIAuthPermHandler::verifyResource` in `libhmiremoting.so`. `Make`-Check ggf. via Coding `ENTWICKLER_MENUE=aktiv` abschaltbar.

**Signing-Backend**

| Stand | Status |
|-------|--------|
| Connected ≤5.1: exportierter Binder `.SECURITY_SERVICE` / `CarSecurityService.signChallenge` | **[D]** |
| Connected ≥5.1 / MyBMW: Service **nicht** mehr exportiert | **[D]** |
| Interner Signierweg modernes MyBMW | **[?]** |

**REJECTED (aktueller Default):** „MyBMW exportiert SECURITY_SERVICE und liefert signChallenge.“

**AIDL vs. Mermaid-Namen [D]** (`EVID-SAS-029`): Analysis-Mermaid nennt `initSecurityContext` / `loadApplicationCert`; rekonstruiertes AIDL + Kit nutzen `createSecurityContext` / `loadAppCert`. **Binder-Wahrheit = AIDL/Code.**

**Zwei Phone-Pfade für SAS auf dem Wire** (technology-audit PR #34 / `EVID-SAS-026`–`028`):

| Pfad | Wer spricht Etch / `sas_*`? | Phone-Korrelation |
|------|----------------------------|-------------------|
| **AAIdrive / Kit** | App = Etch-Client; ruft Security, dann `sas_*` selbst | AAIdrive Logcat + Security |
| **CarAPI** (Spotify u. a.) | App liefert Cert via **ContentProvider** (CN=App-ID); **Connected** merged Certs und führt `sas_certificate`/`sas_login` **stellvertretend**; App **kein** direkter Etch-Proxy-Client (Intent-RPC) | Connected-Prozess, nicht App-Etch |
| Radio/Multimedia-CarAPI | Connected startet laut Doc nur bei **Bluetooth**-Verbindung | USB-only ggf. kein Start |

Wire-Tunnel (BCL/Etch) kann in beiden Fällen dieselben `sas_*` zeigen; Logcat-Strategie muss den Pfad kennen.

**AAIdrive MainService-Gate [D]** (`EVID-SAS-030`): Apps starten Etch-Auth erst wenn iDrive+Security connected (`securityAccess.isConnected()` / `MainService` combinedCallback). Fehlendes Security → kein Login-Versuch.

### 3.5 App-Registration / Connection Intent

Quelle: [app-behavior](https://bimmergestalt.github.io/BMWConnectedAnalysis/app-behavior/) · [carapi](https://bimmergestalt.github.io/BMWConnectedAnalysis/carapi/) **[D]**.

- `CONNECTED_APP_INSTALLED` → App antwortet `ACTION_CAR_APPLICATION_REGISTERING` (ID, Titel, Icon, Connect/Disconnect-Actions).
- Nach BCL: `ACTION_CAR_ACCESSORY_ATTACHED` (`EXTRA_HOST=127.0.0.1`, `EXTRA_PORT`, `instance_id`, …).
- CarAPI-Connect kann `security_service` mitliefern — bei modernem MyBMW oft **nicht** mehr als Binder nutzbar (3.4); SAS läuft dann ohnehin in Connected (Proxy-Pfad).

### 3.6 RHMI

- App sendet u. a. `rhmi_setResource` (XML-Widget-Layout + Zip: Grafik/Texte), dann `rhmi_setData` / `rhmi_setProperty`, Events über `rhmi_addActionEventHandler` → `rhmi_onActionEvent`.
- HU rendert **native** iDrive-Widgets; Controller-Events gehen zurück an die Phone-App.
- **Whitelist:** geänderte Layouts/Assets werden abgelehnt, wenn SHA256 nicht zum Cert passt → AAIdrive „leiht“ typischerweise **offizielle Layout-/Icon-Slots** (z. B. Audioplayer/Spotify/News-ähnlich) und füllt Models.
- **REJECTED:** „AAIdrive kann beliebige eigene XML-Menüs laden.“

### 3.7 AV + Cover

- MusicAppMode: Audio-Kontext anfordern, Hardware-Buttons, Resume.
- ID5+: „global coverart“ im Homescreen / Multimedia-Panel — über **RHMI/Connected**, nicht AVRCP-BIP.
- Praktischer Nutzerpfad: Quelle **App** (Spotify/Audioplayer) wählen, nicht „Bluetooth“.

### 3.8 CDS

- Live-Daten für Anzeigen/Addons (Geschwindigkeit, Multimedia-Status, …).
- IDriveConnectAddons: z. B. Scrobbler liest Multimedia-Metadaten (BT/USB; Radio oft nicht).

### 3.9 Application Manager (AM)

- `am_registerApp()` kann ein **Icon/Placeholder** in der HU zeigen, bevor die volle RHMI-App initialisiert ist.
- Nutzerwahl → `am_onAppEvent()` → RHMI-Init.
- **REJECTED:** „Icon sichtbar ⇒ RHMI vollständig initialisiert.“

---

## 4. Gate-Referenz (Desk) vs. hu-probe-Messfläche

Feinere Lesart der Connected-Kette (BimmerGestalt Lifecycle). hu-probe C1 Identity misst nur den USB-/AOA-Einstieg:

| Gate | Inhalt | hu-probe / Analyzer |
|------|--------|---------------------|
| **G1** | USB Identity / Enumeration | **ja** (I-303A, MSC vs Vendor-only) |
| **G2** | Transport: AOA/BT + **BCL knock/handshake** | AOA-Callback teilweise; BCL-Wire **nein** |
| **G3** | App-Tunnel: localhost TCP → BCL→Etch | **nein** (Phone-Seite) |
| **G4** | SAS Authentication (Cert + Challenge) | **nein** (Keys) |
| **G5** | Authorization/Use: AM / RHMI / AV / CDS | **nein** |

**INFERENCE (nicht FACT am F20):** Reconnect-Loop bei Direct-`18D1:2D00` (Zubehör-UI, kein Bulk/BCL auf Messschicht) *kann* fehlenden Connected-Peer (G2 BCL+) bedeuten.  
**UNKNOWN:** ob genau das der F20-Grund ist. Cross-Ref: hu-probe [GATES-Connected](../../../hu-probe/docs/GATES-Connected.md).

---

## 5. AAIdrive vs. Connected — Rollen

| Komponente | Rolle |
|------------|--------|
| **Connected Classic (≤5.1)** | Tunnel + **exportierter** `SECURITY_SERVICE` Binder |
| **Connected ≥5.1 / MyBMW** | Tunnel-Provider; Security-Export **weg** — Signierweg **[?]** |
| **AAIdrive** | Eigener Etch-Client: Registration → localhost Etch → `sas_*` selbst → RHMI/… |
| **CarAPI-Apps** (Spotify…) | ContentProvider-Cert; Connected führt `sas_*` stellvertretend (kein direkter Etch-Client) |
| **IDriveConnectKit** | Etch-IDL + RHMI-Helper-Library |
| **IDriveConnectAddons** | Extra-RHMI-Apps / CDS-Consumer |
| **BclCarLink** | Optionaler BCL-Link; ersetzt Security **nicht** |

AAIdrive-README (Kernaussage): *„without any modifications or hacks“* am Auto — Nutzung der **offiziellen Connected-Apps-Technologie** mit extrahierten Certs/Ressourcen. Das ist **kein HU-Root**, aber auch **kein** BMW-SDK-Lizenzprodukt.

Projektstatus AAIdrive (Stand Quellen 2026-11): feature-complete / Maintenance; Autor ohne eigenes Compatible-Auto — externe Beiträge nötig.

---

## 6. Einordnung für PiDrive (A / B / C)

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

## 7. Offene Punkte für die Connected-Forschung

| ID | Frage | Hinweis |
|----|-------|---------|
| C1 | Hat der F20 Apps (6NR / Checkbox)? | Ohne das kein Feldtest Pfad C |
| C2 | MyBMW vs. Connected Classic vs. BclCarLink am Fahrzeug | Tunnel-Stabilität |
| C2b | Wie signiert **aktuelles** MyBMW Challenges ohne exportierten SECURITY_SERVICE? | Analysis: alternative method UNKNOWN |
| C3 | Welches Cert/Layout nutzt AAIdrive MusicAppMode (ID5)? | Cover-Fähigkeit |
| C4 | Audio-Fokus AV vs. paralleler Pi-A2DP | Konflikt / Ducking |
| C5 | 30-min Metadata-Freeze: nur Connected-UI oder auch AVRCP? | Getrennt messen |
| C6 | Lohnt Pi-seitige Etch-Emulation vs. Phone+AAIdrive belassen? | Produktentscheid |
| C7 | FIELD-CONNECTED-REAL-01: Phone+MyBMW+AAIdrive parallel Analyzer USB-Capture | Divergenzpunkt vs. Direct-ESP AOA |
| C8 | **FX-G3-01:** eine F20-Session mit sichtbarer `sas_certificate`/Challenge/`sas_login` (Etch-Trace **oder** korrelierte Logs+Tunnel) | Cleartext-Claim macht Decode möglich; Bulk/BCL muss sichtbar sein |
| C9 | Optional parallel CarAPI-App (Spotify): SAS in Connected, anderer Phone-Call-Graph | gleicher Wire-Tunnel, andere Logcat-Korrelation |

---

## 8. Quellen

| ID | Quelle | Rolle |
|----|--------|-------|
| S1 | [hufman — BMW Connected Apps Protocol](https://hufman.github.io/stories/bmwconnectedapps) | Primär: BCL, Etch, SAS, RHMI-Whitelist, Fake Car |
| S2 | [BMWConnectedAnalysis](https://bimmergestalt.github.io/BMWConnectedAnalysis/) | Themenseiten (BCL, Etch, RHMI, CDS, Auth, …) |
| S2a | [Authentication](https://bimmergestalt.github.io/BMWConnectedAnalysis/authentication/) | SAS-Formel, APP_AUTH/APP, SECURITY_SERVICE bis 5.1 |
| S2b | [app-behavior](https://bimmergestalt.github.io/BMWConnectedAnalysis/app-behavior/) | Registration, ACCESSORY_ATTACHED |
| S2c | [carapi](https://bimmergestalt.github.io/BMWConnectedAnalysis/carapi/) | Proxy-`sas_*`, ContentProvider-Cert |
| S3 | [BimmerGestalt/AAIdrive](https://github.com/BimmerGestalt/AAIdrive) | Produkt/Features, MainService-Gate, 6NR |
| S4 | [IDriveConnectKit](https://github.com/BimmerGestalt/IDriveConnectKit) | Etch-IDL + RHMI-Parsing + AIDL |
| S5 | [IDriveConnectAddons](https://github.com/BimmerGestalt/IDriveConnectAddons) | Beispiel-RHMI-Apps / CDS |
| S6 | [BclCarLink](https://github.com/BimmerGestalt/BclCarLink) | Experimenteller BCL-Link; Security-Abhängigkeit bleibt |
| S8 | technology-audit [`bmw-connected-sas-auth-2026-11-06`](../../../technology-audit/audits/bmw-connected-sas-auth-2026-11-06/) (PR [#34](https://github.com/MPunktBPunkt/technology-audit/pull/34)) | Desk-Audit + Follow-up CarAPI/Cleartext/AIDL |
| S7 | [Bimmer Gestalt Übersicht](https://bimmergestalt.github.io/) | Projektlandkarte |

Abruf: 2026-11-06. Foren (Bimmerfest etc.) liefern Nutzer-Anekdoten zu Cover/Connected; der **Protokoll-Stack** kommt aus S1–S6.
