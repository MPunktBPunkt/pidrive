# Gesamtbericht Feld s3 — P-Quelle / Resume-Muster · 2026-10-08

**Lauf:** [`feld-s3-prep/s3-20261008-074403/`](feld-s3-prep/s3-20261008-074403/) · **HEAD:** `0e58ca4`+  
**FW:** 0.4.46-dev Freeze · ESP `.89` · Capture `--no-audio`  
**Serial-Kette:** PD0096 → PD0097 → … → **PD0106** (jeder OTG-Remount neue Serial)

## Das Muster (endlich hörbar)

```
HU speichert P (Byte-Position im Track)
        │
        ▼
 Remount / neuer Serial / Tap „gleicher“ Track
        │
        ├─ Resume bei P ≠ 0 ──► liest um P (R16) ──► Ring dort oft leer
        │                                              │
        │                                              ▼
        │                                         STILLE (+ oft Cover/ID3)
        │
        └─ „von vorn“ / Kopf-Start ──► liest ab Offset 0 ──► Ringkopf hat Polster
                                                              │
                                                              ▼
                                                         TON (wenige Sekunden)
                                                         dann wieder Stille
                                                         (kein Live-Producer)
```

**Ein Satz:** Wir hatten oft „keinen Ton“, weil die HU **mitten im File weiterspielt** — nicht weil der Pump-Pfad tot war. „Von vorn“ holt den Kopf mit Ringpolster → kurz Ton. Das ist **P/Resume**, nicht ein kaputter Stream an sich.

## Operator-Belege (mehrfach repro)

| Situation | Ohr/Auge |
|-----------|----------|
| Replug, Autoplay/Tap BOB mit Resume | Bild da, **kein Ton** (Cursor Mitte/hinten) |
| BOB explizit **von vorn** | **wenige Sekunden Ton**, dann Stille |
| Bayern → zurück BOB | **gleiches Bild + gleicher Tonabschnitt** |
| C7 / C9 | bewusst reproduziert |

Capture ohne Live-Audio erklärt die kurze Tonfenster-Länge (nur Ring), nicht das Resume-Muster.

## Was P **nicht** ist

| Hypothese | s3-Evidenz |
|-----------|------------|
| P nur in der USB-Session / Serial | **widerlegt** — Resume trotz PD0096→PD0106 |
| P nur „letzter Autoplay-Titel“ | Autoplay nach Replug wechselte (BOB / Rock / Bayern) |
| Kein Ton = Bridge/ESP tot | widerlegt — Kopf-Start liefert Ton; Lab-Lieferkette war grün |

**Offen:** exakter Schlüssel (Track-ID, Name, Größe, Pfad, Kombi). s3 zeigt: **nicht nur Serial**.

## Q8 (Trace; `msc_reads` leer)

| Episode | Verdict | Muster |
|---------|---------|--------|
| **ep3** | **`r16_resume_like`** | `F8 B120 B120 F360 B360 F3624` |
| ep15 | unclear (nahe) | `F16 B120 B120…` |
| Rest | Index / unclear / no_slot | Remount-Fenster |

Kein `head_like` in den bewerteten Episoden — passt zu Resume≠0.

## Folgen für Stall / Stufe 3

1. Stall **muss P≠0** bedienen (R23 [S]→ stärker; s3 bestätigt Remount+Serial).  
2. Stall-Start „immer bei 0 nach Replug“ ist **falsch** als Annahme.  
3. Kurzton nach „von vorn“ ≠ Dauer-Live — ohne Producer endet der Ring.  
4. Freeze bleibt: kein Stall-OTA heute; nächster Schritt = P-Identität eingrenzen (Name/Größe) + Stall-Go-Kriterien unverändert (T3, F1-Formal).

## Artefakte

- Ergebnis kurz: [`feld-s3-prep/s3-20261008-074403/ERGEBNIS.md`](feld-s3-prep/s3-20261008-074403/ERGEBNIS.md)  
- Marken / Poll / Trace / `q8/` im Laufordner  
- Lab-Vorarbeit: [`../artifacts-2026-10-08-lab/`](../artifacts-2026-10-08-lab/) (Pump/Bridge grün bis SoftAP)
