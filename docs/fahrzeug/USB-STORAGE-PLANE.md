# Technische USB-Beschreibung — BMW F20 LCI NBT Evo Storage Plane

**Stand:** 2026-11-20  
**Fahrzeug:** BMW F20 118d MY2017 NBT Evo  
**Normativ ergänzend:** [`HU-Technical-Facts.md`](HU-Technical-Facts.md) · [`HU-BESCHREIBUNG.md`](HU-BESCHREIBUNG.md) · Cross-Plane: C-D33 · SAS-Crypto: [`bt-analyzer SAS_STATUS`](../../../bt-analyzer/docs/analysis/SAS_STATUS_CRYPTO_CLOSED_20261120.md)

Beweisstatus: FIELD FACT / LAB FACT / DESK FACT / INFERENCE / OPEN.

---

## 1. Architektur

```text
USB-Stick / PiDrive / hu-probe
        │
        ▼
┌─────────────────────┐
│ USB Host (NBT Evo)  │
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│ USB MSC / BOT       │
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│ SCSI (READ/TUR/…)   │
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│ FAT12/16 + LFN      │
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│ Media Scan / ID3    │
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│ HU Cache            │
│ Browse + Body       │
└──────────┬──────────┘
           ▼
┌─────────────────────┐
│ Decoder / Playback  │
└─────────────────────┘
```

**FIELD FACT:** NBT Evo = USB-MSC-Host (SCSI über BOT).  
**FIELD FACT:** Kein einfaches „Audio-Streamer liest nur aktuelle Decoder-Position“-Modell.

Zwei Ebenen **nicht** vermischen:

```text
STORAGE PLANE (USB)          CONTROL PLANE (BT/AOA)
MSC → SCSI → FAT → Media     BCL → Etch → SAS → AM/RHMI/CDS
```

Bluetooth erklärt **nicht** MSC. CDS kann aber den **semantischen** HU-Zustand für GATE-01 liefern (C-D33).

---

## 2. Geschlossen / stark belegt

| Bereich | Status |
|---------|--------|
| MSC/BOT, SCSI, 512-B-Blöcke, READ10 | FIELD FACT |
| FAT12/16 + LFN, kein USB-Write | FIELD FACT |
| Fresh-Scan ≈160 Blöcke / ≈80 KiB je Datei | FIELD FACT |
| READ10 oft 8 bzw. 240 Blöcke | FIELD FACT |
| Full-file Read bis ≈7,2 MiB | FIELD FACT |
| Multi-file Prefetch / Neighbor | FIELD FACT / STRONG |
| Next-title Prefetch situativ ≈7,5–8 s (keine 15-s-Regel) | FIELD FACT (Lead VARIABLE) |
| Body- / Browse- / Position-Trennung | FIELD FACT |
| BUSY-Pacing, ≈65 s bis EOF (512-KiB-Slot) | FIELD FACT |
| Eager Read ≠ hörbares Play | STRONG / Audible offen |

---

## 3. Zentraler Blocker: GATE-01

```text
READ10 ≠ Play Intent
```

Ein READ10 kann Filesystem, Metadata, Browse, Prefetch, Resume oder Playback sein.  
Nächster Experimentpfad (ohne BUSY zuerst):

```text
U1  USB ↔ CDS Semantik     ← P0 Cross-Plane
 ↓
U2  Cache-Hit
 ↓
U3  Prefetch
 ↓
U4  4-/8-MiB BUSY-Pacing
 ↓
U5  AOA separat (nicht nötig für GATE-01)
```

**U1:** eindeutiger Testtrack + gemeinsame Zeitbasis + USB READ10/LBA + CDS `source` / `statusPlayback` / metadata (Properties `54`, `636–642` Desk; F20-Zuordnung noch absichern).

---

## 4. Offen

- GATE-01 Play-Intent-Korrelation  
- BUSY über ganze Datei / 240-Block unter langem BUSY / ≥8 MiB  
- exakte Prefetch-/Eviction-Policy  
- USB-AOA→BCL an dieser Buchse  
- Identity-Semantik (VID/PID/Serial/…)  

---

## 5. PiDrive-Contract (kurz)

Die HU ist ein **file-orientierter MSC-Host** mit eigener Cache-/Prefetch-Logik.  
PiDrive muss MSC/SCSI/FAT/LBA/BUSY korrekt bedienen — inkl. Reads außerhalb des „aktuell hörbaren“ Titels. Kein künstlicher Audio-Streaming-Modus.

Recovery-Hinweis: nach `ENODEV` Soft-RST + ≥20 s settle.

---

## 6. Querverweise Projekte

| Repo | Nutzen |
|------|--------|
| **hu-probe** | MSC-Instrument + paralleles CDS-Orakel (GATE-01) |
| **bt-analyzer** | BT Control Plane / SAS CLOSED / B3 Gate B |
| **idrivesim** | Lab-HU-Stub (SAS accept ohne Crypto); CDS-Events für Korrelations-Übungen |
| **pidrive** | Live-Producer unter MSC-Contract + BUSY-Pacing |
