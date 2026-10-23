# Maßnahmen aus hu-probe Feld 23.10. → PiDrive

**Quellen (hu-probe main @ ~34b1e64, FW 0.3.19):**  
- [`2026-10-23-gesamtbericht-identity-remount-multireview.md`](../../../hu-probe/docs/feld/2026-10-23-gesamtbericht-identity-remount-multireview.md)  
- [`2026-10-23-wire-nachtrag-074319-074455.md`](../../../hu-probe/docs/feld/2026-10-23-wire-nachtrag-074319-074455.md)  
- [`2026-10-23-wire-nachtrag-detach-browse.md`](../../../hu-probe/docs/feld/2026-10-23-wire-nachtrag-detach-browse.md)  
- Reviews GPT / Grok / Mistral (Konsens 23.10.)  
- Vortag: [`MASSNAHMEN-HU-PROBE-2026-10-22.md`](MASSNAHMEN-HU-PROBE-2026-10-22.md)

**Umsetzung hier:** Docs (`HU-Technical-Facts` Stand 23.10.). Firmware-Schnitt nur indirekt (Vertrag/Architektur), kein neuer `esp32.pidrive`-Code in diesem Paket.

---

## 1. Kurzfazit

| Bereich | Maßnahme | Status |
|---------|----------|--------|
| Identity | Serial / Label / Vol (einzeln+kombi) als Resume-Key **REJECTED** — Dimension geschlossen | Docs R34/Q3 |
| Soft-Remount | NOT READY ≠ HU-Reset; nur echter USB-Cycle | Docs R37 |
| Zwei Pfade | Fresh = `32+128+6` EOF; Cycle+bekannt = FS-Enum, keine EOF-6, oft `tail70→head240` | Docs R38–R41 |
| Drei Schichten | Navigator ≠ Browse-Cache ≠ Audio-Body — „Remount→Cache weg→Resume weg“ verwerfen | Docs R45 §1 |
| Fresh ≠ Zeit | Detach ≤30 s, ESP-RST, OTG~99 s → Resume | Docs R42–R44 |
| P0 Feld | **Größenleiter** 158 KiB→16 MiB (nicht weitere Identity) | Q16 / Auftrag unten |
| P1 Feld | Fresh gezielt (Kaltstart / ≫99 s), Auswertung M18 | Q14 |
| Infra hu-probe | B59 Upload-Stall, B56 Replay-OOR vor neuen Kampagnen | hu-probe |
| B70 | Rohsessions nachgeliefert; folders_30 Wire → R45 **[B]** (Cycle→Dir+Vollatom, Resume-Track zuerst) | erledigt |

**Nicht tun:** weitere Serial/Label/Vol-Serien · Soft-Remount als Reset-Tool · „Navigator überlebt“ als pro-Pfad-[B] ohne Isolation · body_rest-Lead als absolute Zeit ohne audible · Read-FACTs ohne ~158‑KiB-Gültigkeit übernehmen.

---

## 2. Übernommenes Modell (PiDrive-relevant)

```text
USB-Cycle
  ├── FS/FAT/Root neu enumeriert          [B]
  ├── Browse-/Titel-Cache oft geflusht    [S] Operator folders_30
  └── Navigator/Playlist/Position bleibt  [S] ≤99 s / RST / Cycle
            └── Audio-Body oft neu als Atom [B]
```

**Fresh-Diskriminator (M18):** EOF-6-Probes nur bei Fresh-Scan → maschinell Fresh vs. Cycle+Resume.

**PiDrive-Vertrag (Erweiterung zu 22.10.):**

```text
Directory/FAT     → stabil
File head         → ~80 KiB (32+128); Fresh zusätzlich 6-Block-EOF-Probe erwarten
Size/FAT/EOF      → konsistent (EOF-Probe liest Dateiende)
Body              → dynamisch OK; bei großen Dateien Verhalten UNBEKANNT → Größenleiter
Resume-Position   → überlebt kurzen Cycle; nicht an Serial/Label/Vol koppeln
Browse vs Play    → getrennte Caches; Browse-Miss nach Cycle möglich bei erhaltener Position
```

---

## 3. Docs (dieses Repo)

| Datei | Änderung |
|-------|----------|
| [`fahrzeug/HU-Technical-Facts.md`](../fahrzeug/HU-Technical-Facts.md) | Stand 23.10.; §1 Drei-Schichten; E8; R13/R34 geschärft; **R37–R45**; Q3/Q14; **Q16/Q17** |
| dieses Dokument | Maßnahmen + Prioritäten |

Optional nachziehen (nicht blockierend): Parameter-Matrix / MSC-AKTUELL Kurzverweis auf 23.10.

---

## 4. Auftrag nächste Feldkampagne (hu-probe)

### P0 — Größenleiter (PiDrive-Architektur)

| Größe | Stimulus | Messgrößen |
|-------|----------|------------|
| ~158 KiB (Kontrolle) | Fresh + Cycle+Resume (+ ggf. 2. Cycle) | READ10-Offsets, Burst, EOF, body_rest, Cache-Hit/Miss |
| 1 MiB | ditto | ditto + Nachladen mitten in der Datei |
| 4 MiB | ditto | ditto |
| 16 MiB | ditto | ditto + Zeit bis hörbarem Start |

CBR 128 kbit/s; Capture 180–300 s. Klärt B69 / Q16: Readahead-Plateau, ob PiDrive lange/wachsende Dateien liefern kann.

### P1 — Fresh gezielt erzeugen

Nicht über Identity. Stimuli: HU-Kaltstart / Media-Abwesenheit gestaffelt ≫99 s / Schlaf-Zündung. Marker: erster READ10, FS-Enum, Head, body_rest, **EOF-6 ja/nein (M18)**, Resume-Position, möglichst audible.

### P2 — folders_30 Wire — erledigt

`165220`: nach Cycle FS-Enum + Dir-Reads; erster Datei-Atom = ALBUM3/T08 (Resume); Browse = Vollatome, kein Fresh-Scan. → Facts R45.

### P3 — GATE-01 audible (Beifang)

`READ10 → audible_change`; Prefetch-Lead sonst nur relativ.

### Infra vor Kampagne

- **B59** seq_ident-Upload-Stall  
- **B56** Replay-OOR (12 Reads gleiches `t_us` in 074319)  

---

## 5. Ampel (Konsens Reviews)

| Thema | Status |
|-------|--------|
| Identity Serial/Label/Vol als Resume-Key | 🔴 REJECTED |
| Soft-Remount als Reset | 🔴 wirkungslos |
| Fresh = Zeit-Timeout ≤99 s | 🔴 widerlegt |
| Fresh-Scan 32+128+6 / Cycle ohne EOF-6 | 🟢 FACT Wire |
| Resume-Atom tail70→head240 | 🟢 FACT Wire |
| Detach/RST/OTG → Resume | 🟢 Operator / STRONG |
| Drei Schichten / folders_30 Wire | 🟢 FACT (R45) |
| Echter Fresh-Trigger | ⚪ offen |
| Größenleiter ≫158 KiB | ⚪ offen — **P0** |
| GATE-01 audible | 🟡 Beifang |

---

## 6. Schlussfolgerung für PiDrive

Die Identitätsfrage (sichtbare USB-/FAT-IDs) ist für Resume praktisch geschlossen. Architekturentscheidungen hängen jetzt an **Body-Verhalten großer Dateien** und daran, **was Fresh wirklich auslöst** — nicht an weiteren Serial/Label/Vol-Experimenten.
