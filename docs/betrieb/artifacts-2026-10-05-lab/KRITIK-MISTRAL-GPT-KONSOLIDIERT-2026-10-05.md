# Kritik konsolidierter Standbericht Mistral+GPT · 2026-10-05

**Quelle:** verdichteter Mistral+GPT-Stand nach Lab Lock-nach-RST  
**Normativ:** [`MSC-AKTUELL.md`](../MSC-AKTUELL.md) · Abend: [`FELD-ABEND-EAR-2026-10-05.md`](../artifacts-2026-10-05-feld/FELD-ABEND-EAR-2026-10-05.md)

## Urteil

**Übernehmen.** Der Bericht korrigiert unsere Sprache sinnvoll und überschätzt den Lab-Befund nicht. Keine Architektur-Maßnahmen vor dem Abend.

## Was stimmt (bereits Lab/Code)

| Aussage | Unsere Belege |
|---------|----------------|
| Sender-first-Seal überlebt Soft-RST | 1022 Variante A |
| Meta-first-Seal + `frozen_reject` + Soft-RST → Meta bleibt | 1022 Variante D |
| Soft-RST ≠ Kernfehler; falsches Erstsiegel ist der Kern | 1022 EAR |
| Fresh Bridge + Root-Presets = Recovery | Abend-EAR Recovery |
| Gate vorgeschaltet; Hörnachweis offen | MSC-AKTUELL |
| Nicht alle Stillläufe = Lock | GPT-Kritik 0k (04.10 Sender-nahe Runs) |

## Präzisierungen (übernehmen)

1. **„Feld-Falle bestätigt“** nur als: *Mechanismus belegt + Feldmorgen stark erklärt* — **nicht** als direkter Feld-Kausalnachweis des ersten `MSC_MAP_FROZEN` (fehlt in `feld-av-0750`).
2. **Same-process-Reconnect ≠ Recovery** — code-seitig gestützt (`last_menu_snapshot` Resend in `try_reconnect`); Lab 1022 hat das nicht als eigenen Lauf gemessen → Abend: Recovery nur **neuer Bridge-Prozess** oder Unplug, nicht „Reconnect abwarten“.
3. **Hauptblocker Gesamtprojekt** bleibt End-to-End-Ohr; Lock ist **Gate-Blocker**, nicht Projektabschluss.

## Was wir nicht übernehmen

- Kein Lock-Refactor / kein Softwarenacht vor Feld-AV (Freeze).
- Kein neues Lab nur für „viele Soft-RSTs“ (Mistral zu weit).
- Keine Behauptung „Reconnect bewiesen heilungsunfähig“ ohne dedizierten Lab-Lauf — operativ trotzdem: **Reconnect nicht als Recovery nutzen**.

## Maßnahmen

1. Abend-EAR: **erstes** `MSC_MAP_FROZEN` der Session in Artefakt sichern (schließt Feld-Beweislücke).  
2. Abend-EAR: Recovery explizit = **frischer Bridge-Prozess** (+ Root) oder Unplug; Reconnect derselben Instanz **kein** Heilversuch.  
3. MSC-Wortlaut Lock-Zeile / 0L-Index: „Mechanismus belegt“, nicht „Feld kausal bewiesen“.  
4. Nach Gate PASS: AV wie geplant (Fenster/Ohr) — Baustelle B separat.
