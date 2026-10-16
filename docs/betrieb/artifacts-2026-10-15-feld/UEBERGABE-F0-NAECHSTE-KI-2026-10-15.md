# Übergabe — F0 Identity/Cache/Play-Intent · nächste KI · 2026-10-15

**Entscheidung:** **Ja — PiDrive-Hauptpfad = F0.** Stall-Feld-Go und D1–D3 bleiben **danach**.  
hu-probe parallel nur unterstützend (P1c → P0b), nicht als Hauptprojekt.

**HEAD (pidrive):** `8b980d3` (HU-Facts: Q10 CBW 8/240, ms6/cap=2)  
**Bezug Lab:** [`../artifacts-2026-10-13-lab/UEBERGABE-LAB-D-NAECHSTE-KI-2026-10-13.md`](../artifacts-2026-10-13-lab/UEBERGABE-LAB-D-NAECHSTE-KI-2026-10-13.md) (D-Startgate GREEN)  
**Bezug Analyse:** [`../artifacts-2026-10-13-analyse/ANALYSE-D-RESUME-IDENTITY-2026-10-13.md`](../artifacts-2026-10-13-analyse/ANALYSE-D-RESUME-IDENTITY-2026-10-13.md)  
**Feld-Prep:** [`feld-f0-prep/`](feld-f0-prep/)  
**Audit-Transport (nicht F0-Ersatz):** [`hu-probe-bmw-s0s2-field-2026`](../../../../technology-audit/audits/hu-probe-bmw-s0s2-field-2026/)

---

## 0. Warum F0 jetzt (und nicht Stall / Audit / Sniffer)

| Bereits belegt | Offen (Produkt) |
|----------------|-----------------|
| E7-C Busy-Pacing (~65 s vs ~6 s) | Warum kommt die HU nach Reconnect in den alten Kontext? |
| S7-B: Stall erst nach Head-Play | Identity vs Prefetch-Cache vs Play-Intent/Resume-P |
| Lab HU-A1 / Identity-Instrument GREEN | Welche **eine** Dimension bricht Cache/P? |
| CBW oft blocks=8 **und** 240 (Q10) | Ob Stall das Produktproblem löst |

Weitere USB-Messungen allein liefern kaum Produktwert. F0 liefert eine **diskriminierende** Antwort, keine neue Geschichte.

**Absagen bis F0-Ende:** kein Stall-Tuning · kein D1–D3 · kein A10/Wire-Sniffer · kein neues Desk-Audit · kein Scheduler aus gap/4096 · Burst-39 und ms6-STALL nicht als HU-Recovery.

---

## 1. Zielkette (drei Schritte)

```text
„Reconnect-Verhalten ist wiederholbar“
        → F0: welcher Mechanismus?
        → gezielter Folgetest (nur der erfolgreiche Ast)
        → PiDrive nutzt den Mechanismus reproduzierbar
        → erst dann Stall-Feld-Go (CBW-aware)
```

---

## 2. Freeze / Pre-Gates (verbindlich)

| Gate | Wert | Warum |
|------|------|-------|
| FW Feld `.89` | **`0.4.51-dev`** (OTA) | fatVolumeId + Remount-Phase + S7-B |
| `stallEnable` | **`false`** | Stall nicht mit Identity vermischen |
| Lab `.88` | `0.4.51-dev`, Stall off | Referenz; nicht erneut debattieren |
| Episodenklasse | nur **A** (kein ESP-Reboot / weiße LED) | sonst Episode verwerfen |
| Identity | **eine** Dimension pro Lauf | nie mit Head-Force kombinieren |

Kurz-Smoke nach OTA (ohne Matrix): Mount → Menü → eine Head-Station hörbar.

---

## 3. Identity — operational (vor Auswertung fest)

„Identity“ ist **kein** Sammelbegriff. Pro Lauf gilt genau eine Zelle:

| ID | Dimension | API / Remount | Erwartete Status-Diffs **nur** |
|----|-----------|---------------|--------------------------------|
| B0 | Kontrolle (keine Änderung) | nur OTG Replug | keine |
| B1 | **serial** (+Rev) | `keepIdentity=false` Remount | `usbSerial`, `productRevision` |
| B2 | **label** (BPB+Root) | Config + Remount `keepIdentity=true` | `bpbLabel`, `rootLabel` |
| B3 | **volume-id** | Config + Remount `keepIdentity=true` | `bpbVolumeId` |

**Noch nicht in F0** (eigene Builds / spätere Matrix): Dateigröße, Pfad/Directory, Startcluster, Dateiname allein (S4 K3 hat Name schon negativ).

**PASS Isolation:** `changed_fields == expected` (wie Lab `lab_d_campaign.py identity`). Drift → Lauf ungültig.

---

## 4. F0-Protokoll (Kerntest, ~15–25 min)

**Eine Frage:** Beeinflusst eine isolierte Identity-Dimension den NBT-Cache/Resume so, dass der nächste Start **LIVE/hörbar** statt Silence/Mid/Cache ist?

Vorbedingung je Episode: Slot mit **P≫0** (länger gespielt), dann Replug/Remount; B0 zuerst.

| Lauf | Identity | Wenn Rotate wirkt | Wenn nur Prefetch-Cache |
|------|----------|-------------------|-------------------------|
| B0 | keine | weiter Stille / Mid / Cache | Stille / Cache |
| B1 | nur serial | Head → LIVE / hörbar | unverändert |
| B2 | nur label | wie B1 | wie B0 |
| B3 | nur volume-id | wie B1 | wie B0 |

**Nicht** primär „Ton ja/nein“ allein — immer die Kombination:

- Identity-Felder vor/nach  
- READ-Muster (keine / Mid / Head / Full-Re-Read)  
- `play.guess` / `playingUid` Timing  
- erste LIVE-Bytes / Ohr  
- ob Position/Inhalt zum alten Kontext passen  

Pocket: [`feld-f0-prep/GO.md`](feld-f0-prep/GO.md) · Auswertung: [`PROTOKOLL.md`](feld-f0-prep/PROTOKOLL.md).

---

## 5. Entscheidungstabelle (nach F0)

| Beobachtung | Ast | Nächster Schritt |
|-------------|-----|------------------|
| Identity-Änderung zerstört Cache/P → LIVE | **Identity** | Designparameter: Session-Rotation der wirksamen Dimension |
| Identity ändert nichts; Wiedergabe ohne relevante READs | **Cache** | Prefill/LBA/Eviction; Head-Force / Remount-ohne-keepIdentity Lab-Gate |
| Wiedergabe erst nach bestimmten READs | **Datenversorgung** | Prefetch/Head-Force spezifizieren |
| Position bleibt trotz geändertem Inhalt | **Play-Intent/Resume** | Intent-Erhaltung als Produktfrage |
| Alter Inhalt trotz neuem Inhalt | **Cache⊕Identity** | Kopplung; Komponenten nacheinander |
| Keine Dimension hilft | Fallback | Option B Slot-Kette und/oder Head-Force (s6-Übergabe) |

**Phase 2 nicht vorab festnageln** — nur den erfolgreichen Ast verfolgen.

---

## 6. Stall erst nach F0 (Phase 3/4)

Bekannt: Stall funktioniert als Transport. Unbekannt: ob Stall das Produktproblem löst.

Feld-Stall-Go nur nach F0, dann **CBW-aware** (blocks 8 und 240), nicht „alle 4 KiB X ms“. S7-B (Stall erst nach Head) in die F0-Interpretation einbeziehen: Stall wirkt im Play-Zustand — passt zu Play-Intent als Hypothese.

---

## 7. Parallel hu-probe (nicht Hauptpfad)

1. **P1c** `bmw_nbt_evo.json`: nur `origin: hu_probe_field` — Gap Messgröße, blocks [8,240], ms6/cap=2; Prefetch/Eager/Cache/**Burst-39** nicht hochstufen. Skizze: technology-audit Evidence § Profil-P1c.  
2. **P0b** LBA+Marker Formal → hilft F0 deuten.  
3. Erst danach S3 Cache-Hit → S1 Eager ≥4 MiB.

---

## 8. Arbeitsanweisung

1. Lab-Mechanik nicht erneut debattieren.  
2. Operator-Go → OTA **0.4.51** auf `.89` → Smoke → **F0 B0…B3**.  
3. Ergebnis in `feld-f0-prep/ERGEBNIS.md` nach Vorlage; Ast wählen.  
4. Stall eingefroren bis neues Go.

**Meilenstein:** Mindestens eine isolierte Dimension erzeugt nach Replug bei P≫0 hörbaren Head/LIVE statt Silence-Cache **oder** widerlegt Rotate klar zugunsten Prefetch-Cache/Head-Force — mit dokumentierter Isolation.

---

## 9. Lab-Gate (2026-10-16, vor Feld)

Identity-Tooling auf `.88` overnight + Fix verifiziert — **kein** NBT-Cache-Beweis:

| Artefakt | Status |
|----------|--------|
| `lab-f0-rehearsal/run-20261016-000641` | serial+vid 8/8; label 3/8 (11-Zeichen-Stall) |
| Fix `next_volume_label` + `ensure_stream_quiet` | in `lab_d_campaign.py` / `f0-identity.sh` |
| Verify `run-20261016-062936` | **18/18 PASS** |
| OTA-Watcher `.89` | Retry-Loop (HTTP-200 → oft Minuten offline) |

Feld bleibt: Auto an → OTA-Gate → Smoke → B0…B3.

---

## 10. Feld 2026-10-16 AM — Ergebnis (kurz)

**Vollbericht:** [`feld-f0-prep/ERGEBNIS.md`](feld-f0-prep/ERGEBNIS.md)

| | |
|--|--|
| FW / Stall | `0.4.51-dev` · `stallEnable=false` |
| F0 B0…B3 | **nicht gültig** (Smoke/Klasse-B-Lotterie) |
| Ast | **X** · Produkt-Lesart **P⊕C** |
| Positiv | Klasse A → selten ~**6 s Ton+Bild** Bayern; Play/Stream kann armieren |
| Negativ | Panic/weiße LED bei Replug; Mid-Cache ohne Guess; Soft-Remount keepIdentity ändert Ton nicht; Stream≠Ohr |

**Nächster Auftrag:** Panic-OTG fixen → LIVE>6 s reproduzierbar → erst dann F0-Matrix. Stall weiter eingefroren.
