# Auto-M3 Readiness — 2026-10-03

**Zweck:** Vorbereitung des nächsten BMW-Feldtests als **statischer, kontrollierter Hostvergleich** Lab-Host ↔ NBT Evo.  
**Basis-Übergabe:** Chat-Übergabebericht „MSC-Strategie und M3-Feldtest“ (2026-10-03).  
**Normativ:** [`AUFTRAG-MSC-HOST-READ-NACHWEIS.md`](../auftraege/AUFTRAG-MSC-HOST-READ-NACHWEIS.md) Rev.4 · [`SESSION-LAB-2026-10-03.md`](artifacts-2026-10-03-m3/SESSION-LAB-2026-10-03.md)

**Regel:** Abweichungen zwischen Übergabebericht und Repo/Artefaktstand werden hier **explizit** gemeldet — nicht stillschweigend angeglichen.

---

## 0. Abgleich Übergabebericht ↔ Repo (D)

| Behauptung Übergabe | Repo/Live-Stand | Abweichung? |
|---------------------|-----------------|-------------|
| `pidrive` HEAD `5055c61` | `5055c61` (`Reconfirm M0…`) | nein |
| `esp32.pidrive` HEAD `eaa65f7` | `eaa65f7` (`Add L3 lab geometry…`) | nein |
| Lab `.88` = `0.4.42-dev` L3 | bestätigt; `sectorCount=32768`, fav0=8 MiB, stream=off, tcp=up | nein |
| Host meldet FAT16 | `file -s` + **`fsck.fat -vn`** + BPB-Parser | nein; Nachweis jetzt vertieft |
| M0 L3 PASS×2 Δrc=457 | `lab88-l3-m0-1542/` | nein |
| Langpace 12 Kreuzungen ~29,979 s | `lab88-l3-langpace-1535/` | nein |
| Feld `.89` führt vorgesehenen Build | **`.89` derzeit nicht erreichbar** (Timeout) | **ja — offen** |
| Letzter dokumentierter Auto-Stand | Feldtest-Doc: **`0.4.39-dev` FAT12 L0** (nicht L3) | **ja — OTA auf L3 ausstehend** |
| Statusfeld `readyDetail` | `/api/status` hat **kein** `readyDetail`; Geometrie-String nur in Event-/Capture (`ready_events`) | **geringfügig** (Doc-Sprache) |
| FAT16 „endgültig freigegeben“ | Übergabe bewusst offen; Lab-Verify jetzt **PASS_GEOMETRY_LAB** | siehe §1 |

Eingefrorene Architekturthemen (Ring/PSRAM/Remount/BT/Live-Overlay/Pacing im Baseline) — unverändert beachtet; **keine FW-Geometrieänderung** vor M3 (Typ nicht mehrdeutig).

---

## 1. L3 FAT16-Geometrie — Pflichtnachweis (geschlossen im Lab)

**Artefakt:** [`artifacts-2026-10-03-m3/lab88-l3-fat-verify-1615/`](artifacts-2026-10-03-m3/lab88-l3-fat-verify-1615/)

| Quelle | Ergebnis |
|--------|----------|
| Rohes Boot-Sector | `pidrive-l3-boot.bin` (512 B) |
| Head 96 Sektoren | `pidrive-l3-head96.bin` |
| Unabhängiger BPB-Parser | `bpb-parse.json` |
| `fsck.fat -vn` | `fsck.fat-vn.txt` |

### BPB (gemessen)

| Feld | Wert |
|------|------|
| Bytes/Sektor | 512 |
| Sektoren/Cluster | 8 → **4096 B Cluster** |
| Reservierte Sektoren | **1** (Annahme bestätigt) |
| FATs | 2 |
| Sektoren/FAT | 16 |
| Root-Einträge | 512 → 32 Root-Sektoren |
| Gesamtsektoren | 32768 (16 MiB) |
| Data-Start LBA | **65** |
| Datensektoren | 32703 |
| **Datencluster** | **4087** |

### FAT-Typ

Microsoft-Regel: `<4085` → FAT12, `4085…65524` → FAT16.  
→ **4087 = FAT16**, Margin nur **+2** Cluster („knapp“), aber **nicht mehrdeutig**.

`fsck.fat`: „2 FATs, 16 bit entries“, „4087 data clusters“.  
`file -s`: `FAT (16 bit)` — allein unzureichend, hier nur Zusatz.

Code `MscGeometry` L3 (`kVirtSectorCount/kSpc/kFatSpf/kRootSectors/kDataStartLba`) **stimmt** mit BPB überein.

### Quirks (nicht blockierend)

- Volume-Label Boot `PIDRIVE` vs. Root = USB-Serial (`PD00xx`) — `fsck` meldet Differenz.
- `msc.readyDetail` fehlt in Status-JSON; String `FAT16 L3 16MiB fav0=8M` kommt aus Ready-Events.

### Freigabe-Urteil Geometrie

**PASS_GEOMETRY_LAB** — Feldlauf mit dieser L3-Geometrie ist aus FAT-Sicht erlaubt.  
Keine Vorab-Änderung auf 2‑KiB-Cluster / größere Disk vor dem ersten Auto-M3 (Typ eindeutig).  
Nach OTA auf `.89`: **BPB/`fsck` am Feld-Host erneut sichern** (gleiche Checkliste, neues Artefaktverzeichnis).

---

## 2. Testdatei-Identität (statisches Silence+PDMK)

Algorithmische Payload (kein Flash-Blob). Identität = Host-`dd` von fav0:

| Größe | 8 MiB (16384×512), LBA 81…16464 |
|-------|----------------------------------|
| **SHA-256 fav0 ganz** | `6b8826621f0829fe940f5b42be355edd452d0c49bae6a665c32dd063f56e2ed3` |
| SHA-256 Sektor LBA81 (Head) | `2b96e820f2983b5bdeff733061bf43c80a4a439696b8536b81c0d928654c5a24` |
| PDMK idx0 @ file_off 256 | `PDMK\x00\x00` verifiziert |
| Marker-Intervall | 180000 B ≈ 30 s @ 6 KiB/s |

**Einschränkung (Übergabe §5.2):** Stamp in Frame-Bytes 4..9 — Decoder-Robustheit nicht vollständig validiert; M3-statisch misst Host-Reads, keine Hör-/Bitgenau-Aussage.

Nach Feld-OTA: fav0-Hash erneut; bei Abweichung Pass ungültig oder Hash dokumentieren.

---

## 3. Firmware / OTA / Rollback

| Rolle | Gerät | Soll vor M3-statisch | Ist (jetzt) |
|-------|-------|----------------------|-------------|
| Lab-Referenz | `.88` | `0.4.42-dev` env `pidrive-s3-l3` | **ist** |
| Feld | `.89` | **dieselbe** L3-Build-Linie `0.4.42-dev` | **unbekannt / offline**; Doku zuletzt **0.4.39** L0 |

### Binaries (lokal + auf Pi gestaged)

| Datei | SHA-256 | Zweck |
|-------|---------|-------|
| `dist/pidrive.0.4.42-dev.ota.esp32s3.bin` | `2471626fe2d23479ca76772a5b8d5fa17eb232b0e3c3cc26612c6cbd1b3521c7` | Feld-OTA Ziel (auf Pi gestaged) |
| `dist/pidrive.0.4.39-dev.ota.esp32s3.bin` | `5a1e069781c5d496b0298adf9efd5163aa92d2245a502d24c090a91565787982` | **Rollback** → letzter dok. Auto-Stand (FAT12 L0) |
| `dist/pidrive.0.4.36-dev.ota.esp32s3.bin` | `8447179c197a099f02ca8d4791cdfd9ce8c9ecab8c644c5f2eed7a8d32138235` | optional älterer Rollback |

Pi `.105`: `/home/pidrive/dist/` enthält `0.4.39` und (gestaged) `0.4.42`.

### Rollback-Pfad (verbindlich)

1. Vor OTA `.89`: `GET /api/status` → Version, Serial, `sectorCount`, Slot-Bytes sichern.  
2. OTA `0.4.42` → Reboot → Status erneut; Host-Größe + BPB/`fsck` Artefakt.  
3. Bei Problemen: OTA zurück auf **`0.4.39-dev`** (dokumentierter Auto-Stand) oder `0.4.36-dev`.  
4. Nach Rollback: Bridge ggf. neu; USB-Replug; **kein** M3-Befund aus Misch-Sessions.

---

## 4. Readiness-Gate (vor jedem Pass)

Kopieren in Session-EAR; alle Punkte müssen erfüllt sein:

- [ ] ESP-FW/Commit dokumentiert (`.89` Status = `0.4.42-dev`, Commit-Anker `eaa65f7` bzw. Build-ID).  
- [ ] L3-Geometrie: BPB + Clusterzahl + `fsck.fat` Artefakt **dieses** Builds.  
- [ ] fav0 = 8 MiB; Hash ≈ Lab-Referenz (oder Abweichung begründet).  
- [ ] Session-ID / Serial / remountGen / uptime eindeutig; frischer Trace-Start.  
- [ ] USB-Plug-Zustand klar; **kein** ungeplanter Replug im Messfenster.  
- [ ] Bridge → `.89:9090` up; JSONL wird geschrieben (Größe >0 nach Stimulus).  
- [ ] Vorlauf-Poll + Trace-Start zeitlich zuordenbar.  
- [ ] **`POST /api/lab/stop`** — kein Live-Overlay.  
- [ ] Auswahl **nur über HU**; keine Bridge-Senderwahl.  
- [ ] Play/Pause + HU-Anzeige mit Zeitstempeln protokolliert.  
- [ ] Kein Pacing / keine künstliche MSC-Verzögerung.  
- [ ] Neues Artefaktverzeichnis (`artifacts-YYYY-MM-DD-m3/auto89-…`); nichts überschreiben.

Gate nicht erfüllt → **kein** M3-Befund starten.

---

## 5. M3-statisch — Ablauf (Feld)

1. Bridge auf `.89`, Trace-Sink leer/neu.  
2. Soft-Remount nur vor Start (nicht während Fenster), außer separat markiert.  
3. HU: Stick/USB wählen → fav0 (Rock Antenne) → Play.  
4. Beobachtungsfenster: **5–10 min** mit nachgewiesenem Play; länger nur wenn Status klar.  
5. Marker-Erwartung im Fenster notieren (z. B. bei 6 KiB/s-Cursor wären m0…mN ~30 s — **NBT-Cursor unbekannt**; Soll nur Lab-Referenz).  
6. Sofort nach Pass: Status before/after, Trace-Größen, M0-Bilanz `ΔreadCount = Σ(burst.n) + drops`.  
7. Ungültig bei leerem Export, Session-Bruch, Bilanz-Fail, unklarer Geometrie.

**Armed/Live:** eigener Pass, eigene Session, **nach** statischem M3 — nicht mischen.

---

## 6. Ergebnisblock-Schema (kurz)

Identität · Integrität (Bilanz) · Wiedergabezustand · Transport (Sweep / post-Sweep / LBA) · A–E + Evidenzebene · Gültigkeit.  
Keine Aussage „NBT liest live“ aus `readCount` allein.  
`playOffset` / `readAheadDistance` nur bei belegter Position, sonst `unknown`.

---

## 7. Offene Punkte — Stand nach Feld

1. ~~`.89` OTA 0.4.42~~ → **done** 2026-10-03.  
2. ~~Auto-M3-statisch~~ → **A_then_E** ([`artifacts-2026-10-03-m3/AUTO-M3-FELD-2026-10-03.md`](artifacts-2026-10-03-m3/AUTO-M3-FELD-2026-10-03.md)).  
3. **Als Nächstes:** M3seq — [`PLAN-NACH-M3-AE-2026-10-03.md`](PLAN-NACH-M3-AE-2026-10-03.md).  
4. Optional: Decoder-Test PDMK; Feld-BPB-Reverify.

---

## 8. Gesamturteil (nach Feld)

Lab-Methodik hat gehalten. Auto-M3-statisch zeigt: **Sweep, dann Cache-Play ohne MSC-Nachlesen** (A_then_E).  
Nächster Architekturhebel ist **nicht** Ring/Live, sondern ob **Titelwechsel/Remount** Bytes erzwingt.
