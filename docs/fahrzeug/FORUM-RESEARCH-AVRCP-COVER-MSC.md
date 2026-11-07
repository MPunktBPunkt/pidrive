# Foren-/Quellen-Auswertung — AVRCP, Cover Art, USB-MSC (NBT Evo)

**Stand:** 2026-11-06  
**Fahrzeugbezug:** BMW NBT Evo (PiDrive: F20 LCI 2017)  
**Scope:** Öffentliche Foren + angrenzende Open-Source-/Fachquellen zu Lücken, die PiDrive messtechnisch bearbeitet (AVRCP/MPRIS-Metadaten, Cover, USB-MSC-Host).  
**Ergebnis in einem Satz:** Nutzbare Signale liegen fast nur im **AVRCP-/Cover-/Metadaten**-Bereich; zum **USB-MSC-Host-Timing** der NBT Evo gibt es öffentlich praktisch nichts Vergleichbares zu den PiDrive-/hu-probe-Messungen.

Verwandt: [`iDriveBt.md`](iDriveBt.md) · [`BMW-AVRCP-PROBE.md`](../archiv/fahrzeug/BMW-AVRCP-PROBE.md) · [`HU-Technical-Facts.md`](HU-Technical-Facts.md) · [`ABNAHMEN.md`](../ABNAHMEN.md) · **Pfad C:** [`CONNECTED-AAIDRIVE-STACK.md`](CONNECTED-AAIDRIVE-STACK.md)

---

## 1. Urteil

| Thema | Öffentliche Lage | Nutzen für PiDrive |
|-------|------------------|--------------------|
| BT Cover Art / AVRCP-Version | Foren + BlueKitchen: Cover über **iAP/Connected/USB**, nicht zuverlässig über AVRCP-BIP | **Hoch** — BT-Cover als Produktziel streichen; Cover über USB-MSC/ID3 |
| Metadaten-Freeze / sticky Tags | Wiederkehrende Nutzerberichte + SW-Release-Notes | **Mittel** — Hypothesen für Dauerlauf / TrackChanged |
| Coding-Bits `ENT_BTAS_*` | Viele Coding-Threads | **Niedrig–mittel** — nur Fahrzeugkonfiguration prüfen |
| Pi + BMW Media-Bridges (BMWpyPod) | Ein Repo, andere Architektur (6FL/iPod-Serial) | **Gering** — kein NBT-Evo-AVRCP-Target-Pfad |
| USB-MSC Host (READ10, Bursts, Timeouts) | Keine vergleichbaren Threads | **Keiner** — PiDrive bleibt Quelle der Wahrheit |
| Connected Apps / AAIdrive (Pfad C) | hufman + AAIdrive-Repos: BCL→Etch→RHMI | **Hoch für Connected-Forschung** — siehe [`CONNECTED-AAIDRIVE-STACK.md`](CONNECTED-AAIDRIVE-STACK.md) |
| Android-Auto / SSH auf HU | Vorhanden, angrenzend | **Irrelevant** für aktuelle MSC/AVRCP-Lücken |

---

## 2. Extrahierte Befunde (mit Quellen)

### 2.1 Cover Art über Bluetooth ≠ AVRCP Cover Art (BIP)

**Befund**

- Coding-Parameter heißt `ENT_BTAS_IAP_COVERART` — Name verweist auf **iAP**, nicht auf AVRCP 1.6 / BIP.
- Nutzer am NBT Evo: mit Android **AVRCP 1.6** oft **kein** Playback / keine Track-Info; Rückkehr auf **AVRCP ≤ 1.5** nötig. Cover nur über Connected App (dort Timeline ungenau; Updates stoppen nach ~30 min).
- BlueKitchen: Historisch zeigten Autos Covers trotz fehlendem AVRCP-Cover-Art oft über **iAP2 (Apple)** oder **Metadaten-Lookup** (lokale DB / Online). Echtes AVRCP Cover Art nutzt **BIP** und verlangt ein Thumbnail (**200×200 JPEG**); OS-Support kam spät (Android 12+ / iOS 13+, oft default 1.5).
- BlueZ: Cover-Art-Unterstützung ist vor allem **client-seitig** (Cover vom Remote pullen); als A2DP/AVRCP-**Source** Cover zur HU pushen ist kein fertiger Produktpfad.

**Folge für PiDrive**

- `mpris:artUrl` / AVRCP-1.6-BIP für NBT Evo **nicht** verfolgen.
- Abnahme „Cover = BMW-Bluetooth-Icon“ ([`ABNAHMEN.md`](../ABNAHMEN.md)) bleibt erwartet.
- Cover-Anzeige = **USB-MSC + ID3 APIC** (bereits belegt in [`HU-Technical-Facts.md`](HU-Technical-Facts.md) M1–M3).
- Falls BlueZ jemals Cover-Art-Feature-Bits als Target/Source setzt: für BMW **≤ AVRCP 1.5 / ohne BIP** belassen.

**Quellen**

| ID | Quelle | Typ | Abruf |
|----|--------|-----|-------|
| Q1 | [Bimmerfest — i001 Bluetooth Album art coding](https://www.bimmerfest.com/threads/i001-bmw-i3-bluetooth-album-art-coding.1290111/) | Forum | 2026-11-06 (Inhalt über Such-Snippets; Direktabruf 402 Paywall) |
| Q2 | [BlueKitchen — AVRCP Cover Art in iOS / Android](https://bluekitchen-gmbh.com/avrcp-cover-art-in-ios-android/) | Fachartikel | 2026-11-06 |
| Q3 | [BlueZ issue #1804 — Cover art via AVRCP 1.6](https://github.com/bluez/bluez/issues/1804) | Upstream | 2026-11-06 |
| Q4 | [Bimmerfest — Coding Enhanced Bluetooth](https://www.bimmerfest.com/threads/coding-enhanced-bluetooth.762586/) (`ENT_BTAS_IAP_COVERART`, Browsing) | Forum | 2026-11-06 (Snippets) |
| Q5 | [f30.bimmerpost — Coding Album Art Cover With BT Streaming](https://f30.bimmerpost.com/forums/showthread.php?t=2061225) | Forum | 2026-11-06 (Snippets; Direktabruf 403) |

### 2.2 Metadaten bleiben hängen / frieren ein

**Befund**

- Connected-App-Pfad: Track-Info und Cover stoppen Updates nach **~30 Minuten** (Q1).
- Wiederholt: Quelle umschalten (Radio → BT) bringt Metadaten zurück.
- BMW Software-Update-Notes (Nutzerzitiert): *„Clears the display of old metadata after a change of track.“*

**Folge für PiDrive**

- Passt zu bestehendem Rate-Limit / `TrackChanged`-Hygiene in [`iDriveBt.md`](iDriveBt.md).
- Offene Hypothese **[H]:** HU-seitiger Session-/Notification-Timeout ~30 min auch am reinen A2DP/AVRCP-Pfad — mit **≥45 min Dauerlauf** + TrackChanged-Zähler prüfbar (noch nicht gemessen).

**Quellen**

| ID | Quelle | Typ | Abruf |
|----|--------|-----|-------|
| Q1 | s. oben (30-min Freeze Connected App) | Forum | 2026-11-06 |
| Q6 | [f80.bimmerpost — Unable to show metadata when connected via Bluetooth](https://f80.bimmerpost.com/forums/showthread.php?t=1459444) | Forum | 2026-11-06 (Snippets; Direktabruf 403) |
| Q7 | [f30.bimmerpost — Album Art and BT Streaming](https://f30.bimmerpost.com/forums/showthread.php?t=1237213) | Forum | 2026-11-06 (Snippets) |

### 2.3 Coding-Parameter (Fahrzeug, nicht PiDrive-Code)

Häufig genannte Bits (NBT / HU_NBT), die Cover/Metadaten/Browsing betreffen:

| Parameter | Kontext in Foren |
|-----------|------------------|
| `ENT_BTAS_IAP_COVERART` | BT/iAP Cover |
| `ENT_BTAS_METADATA` | BT-Metadaten |
| `ENT_BTAS_BROWSING` | „Browse via BT“ (ab älteren FW-Claims, z. B. ≥50.4) |
| `ENT_MC_COVER`, `CDMM_GLOBAL_COVER`, `CDMM_USB_COVER_ART` | eher USB/Media-Cover |

**Abgleich mit PiDrive-Messung:** AVRCP-Browsing-PSM `0x001B` wurde am F20 **nicht** geöffnet ([`BMW-AVRCP-PROBE.md`](../archiv/fahrzeug/BMW-AVRCP-PROBE.md)). Foren-Claims zu „Browsing“ decken sich damit **nicht** automatisch — entweder anderes Coding/SW, oder BMW meint einen anderen Browse-Pfad als AVRCP Browsing Channel.

**Quellen:** Q1, Q4; zusätzlich Coding-Listen z. B. [bimmerscene — NBT Enhanced Bluetooth Coding](https://www.bimmerscene.com/showthread.php?tid=163) (Q8), [xbimmers Coding thread](https://x3.xbimmers.com/forums/showthread/715297/coding-made-easy-a-step-by-step-procedure/page/85) (Q9).

### 2.4 Raspberry-Pi-Bridges — Architektur-Vergleich

#### BMWpyPod ([00b/BMWpyPod](https://github.com/00b/BMWpyPod)) — Q10

- Ziel: Phone → Pi (**A2DP Sink + AVRCP Controller** auf BlueZ `MediaPlayer1`) → Metadaten/Tasten über **BMW 6FL / iPod Accessory Serial** (30-pin Y-Kabel), nicht NBT-Evo als AVRCP Controller gegen einen Pi-Target.
- Attribute: Title / Artist / Album (kein Cover-Pfad zur HU über AVRCP).
- Bekannte Issues im README: Display updated manchmal nicht; Apostroph → `?`; BT muss vor iPod-Mode stehen.
- **Für NBT Evo / PiDrive-AVRCP-Target: kein direkter Transfer.** Bestätigt nur, dass drei Textzeilen der praktikable Common Denominator sind.

#### nicokaiser/rpi-audio-receiver — Q11

- Generischer A2DP-Sink + AirPlay/Spotify-Connect-Stack. Kein BMW-spezifisches Host-Verhalten. PiDrive-PipeWire-Stack ist weiter; kein Handlungsbedarf.

### 2.5 USB / MSC / Host-Verhalten

**Befund**

- Öffentliche Threads behandeln Stick-Format (FAT32 empfohlen; ExFAT/NTFS → unvollständiger Index), embedded Artwork auf USB, Maps/Updates, SSD/HDD im NBT — **nicht** READ10-Burstlängen, Eager-EOF, TUR-Idle, Prefetch-Atome.
- FAT32-/Artwork-Hinweise stützen den bestehenden USB-MSC-Ansatz, liefern aber **keine** neuen Host-Grammatik-Parameter.

**Quellen**

| ID | Quelle | Typ | Abruf |
|----|--------|-----|-------|
| Q12 | [Bimmerfest — iDrive USB Music Issues](https://www.bimmerfest.com/threads/idrive-usb-music-issues.840738/) | Forum | 2026-11-06 (Snippets) |
| Q13 | [f30.bimmerpost — Supported HDD and USB audio formats](https://f30.bimmerpost.com/forums/showthread.php?t=1364130) | Forum | 2026-11-06 (Snippets) |

**Fazit MSC:** [`HU-Technical-Facts.md`](HU-Technical-Facts.md) / hu-probe bleiben die Referenz; Foren schließen diese Lücke nicht.

### 2.6 Angrenzend, bewusst ausgespart

| Quelle | Warum nur Randnotiz |
|--------|---------------------|
| Q14 [Bimmerfest — SSH on NBT Evo](https://www.bimmerfest.com/threads/enabling-ssh-access-to-nbt-evo.1467262/) | HU-Root/Debug, kein Media-Sink-/MSC-Protokoll |
| Q15 [Sq00ky/Supra-iDrive6-Android-Auto](https://github.com/Sq00ky/Supra-iDrive6-Android-Auto) (+ Issues zu Audio/Latenz) | AA-Video/Audio-Routing; A2DP als Notlösung ≠ PiDrive-MSC |

---

## 3. Abgeleitete Maßnahmen (Priorität)

| Prio | Maßnahme | Status |
|------|----------|--------|
| P0 | BT-Cover für NBT Evo als Feature **nicht** planen; Cover = USB-MSC/ID3 | Doku (dieser Bericht + `iDriveBt.md`) |
| P0 | AVRCP-Kompatibilität **≤ 1.5** / kein BIP-Cover-Art gegenüber BMW | bereits Praxis; explizit festhalten |
| P1 | Optional: Coding-Bits `ENT_BTAS_*` am F20 einmal auslesen/vergleichen | offen |
| P2 | Dauerlauf ≥45 min gegen 30-min Metadata-Freeze-Hypothese | offen **[H]** |
| — | MSC-Host weiter nur aus eigenen Messungen | unverändert |

---

## 4. Abrufhinweise / Limitierungen

- Bimmerfest-Direktabruf am 2026-11-06: **HTTP 402** (Paywall). Inhalt zu Q1/Q4 aus öffentlichen Such-Snippets rekonstruiert; Formulierungen können gekürzt sein.
- Bimmerpost-Direktabruf teils **HTTP 403**; ebenfalls Snippets.
- GitHub-READMEs/Quellen Q2, Q3, Q10, Q11, Q15 vollständig lesbar.
- Keine Aussage über andere HU-Generationen (CIC/ID8/…) ohne eigene Messung.

---

## 5. Quellenverzeichnis (kurz)

1. Q1 Bimmerfest i001 Album art — https://www.bimmerfest.com/threads/i001-bmw-i3-bluetooth-album-art-coding.1290111/
2. Q2 BlueKitchen AVRCP Cover Art — https://bluekitchen-gmbh.com/avrcp-cover-art-in-ios-android/
3. Q3 BlueZ #1804 — https://github.com/bluez/bluez/issues/1804
4. Q4 Bimmerfest Enhanced Bluetooth Coding — https://www.bimmerfest.com/threads/coding-enhanced-bluetooth.762586/
5. Q5 f30 Album Art BT Coding — https://f30.bimmerpost.com/forums/showthread.php?t=2061225
6. Q6 f80 BT Metadata — https://f80.bimmerpost.com/forums/showthread.php?t=1459444
7. Q7 f30 Album Art and BT Streaming — https://f30.bimmerpost.com/forums/showthread.php?t=1237213
8. Q8 bimmerscene NBT EBT Coding — https://www.bimmerscene.com/showthread.php?tid=163
9. Q9 xbimmers Coding (ENT_BTAS_*) — https://x3.xbimmers.com/forums/showthread/715297/coding-made-easy-a-step-by-step-procedure/page/85
10. Q10 BMWpyPod — https://github.com/00b/BMWpyPod
11. Q11 rpi-audio-receiver — https://github.com/nicokaiser/rpi-audio-receiver
12. Q12 Bimmerfest USB Music Issues — https://www.bimmerfest.com/threads/idrive-usb-music-issues.840738/
13. Q13 f30 USB audio formats — https://f30.bimmerpost.com/forums/showthread.php?t=1364130
14. Q14 Bimmerfest SSH NBT Evo — https://www.bimmerfest.com/threads/enabling-ssh-access-to-nbt-evo.1467262/
15. Q15 Supra iDrive6 Android Auto — https://github.com/Sq00ky/Supra-iDrive6-Android-Auto
