# Kritik GPT-5.4-Gesamtbericht · 2026-10-05

**Quelle:** GPT-5.4 Zusammenfassung (Feld + Lab + Multi-Review)  
**Normativ bleibt:** [`MSC-AKTUELL.md`](../MSC-AKTUELL.md)

## Gesamturteil zum Bericht

**Weitgehend treffend und brauchbar.** Präzise Trennung Lab vs. HU-Ohr, Fenster vs. MPEG-Fingerprint, Meta vs. Sender.  
**Zu weich / zu weit:** „Lock-Logik vollständig aufklären“ und „Lock robust machen“ klingen nach Softwaresprint — das ist **vor dem Abend-AV-PASS** nicht der Auftrag (Freeze hält).

## Was wir übernehmen

| GPT-These | Bewertung gegen Artefakte | Maßnahme |
|-----------|---------------------------|----------|
| C′ grün, nicht neu aufmachen | **Stimmt** (0744 PASS) | Abend: **kein C′** |
| Meta = kein Producer; Sender = `active`+live | **Stimmt** (0816 + 0855) | Abend: GO nur bei Rock/Bayern/BOB in **slotMap** |
| MPEG-Sync allein ≠ Live-Serve | **Stimmt** (window/burst Labs) | Correlate: `hostAbs∈[absBase,absEnd)`, `liveBytes↑`, `underruns`, Ohr |
| `absEnd` exklusiv | **Stimmt** (Burst-Sim) | Correlate hard: `hostAbs < absEnd` |
| Fenster/Cursor = führende Rest-Hypothese **nach** Sender-Seite | **Stimmt als Reihenfolge** | Erst Sender-GO, dann Fenster-Beweis |
| Lock nach ESP-Reset / erstes Siegel | **Stimmt und feldbelegt** | siehe § Lock |

## Was wir abschwächen

1. **„Zwei gleichwertige Restblöcke“** — operativ heute Abend **ungleich**: ohne Sender-Seite gibt es keinen Fenster-Test. Lock/Seite ist **Gate**, Fenster ist **Inhalt des AV-PASS**.
2. **Sender-Correlate-Underruns** (0855) — Lab-Host-dd kann Underruns erzeugen; **nicht** als Feld-Pacing-Beweis lesen.
3. **„Konkreter Blocker aller Hör-Fails“** — Meta erklärt **05.10. Morgen-AV**; 04.10. Sender-nahe Runs bleiben eigene Restfrage (Claude/GPT korrekt).
4. **„Lock ist Produktproblem → Softwarenacht“** — Risiko anerkannt; **Code-Änderung erst nach Abend-Messung**, außer Operator-Gate reicht nicht.

## Lock: was die Rohdaten wirklich sagen

Feld AV nach RST (`feld-av-0750/status-00-post-rst.json`):

- `slotMap` = **Favoriten / Quellen / Stop / Mehr…**
- Menü `fromNvs=true`, `rev=4244`
- Correlate: `stream.active=false`

Das ist **stärker** als „HU zeigt Meta während Lock Rock hält“: nach RST liegt die **ESP-MSC-Seite selbst** auf Meta (NVS), bevor AV überhaupt startet. Bridge-`frozen_reject` gegen gewünschte Rock-Updates kann diesen Zustand **einfrieren**.

Lab-Gegensatz mit frühem Seal Rock: Meta-`menu_set` wird abgewiesen, Slots bleiben Sender — Lock tut dann, was er soll.

**Abend-Risiko:** RST/Reconnect → NVS-Meta → Lock hält falsches oder altes Siegel → kein Sender → kein AV.

## Maßnahmen (verbindlich für Abend)

### Gate (vor jedem AV-Versuch)
1. Nach RST/Reconnect **sofort** `/api/status` → `msc.slotMap` Namen = Rock / Bayern / BOB.
2. Bridge-Log: `MSC_MAP_FROZEN` mit denselben Namen (nicht Favoriten/…, nicht Zurueck/…).
3. Seed **aus** (`body_seed` off). C′ nicht anfassen.
4. Erst dann Operator: Sender wählen + Correlate + Ohr.

### Wenn Gate FAIL (Meta / falsches Siegel)
1. **Nicht** AV interpretieren.
2. Operator: `Mehr…` / Seite 1 / Remount nur nach Lab-EAR (`lab88-menu-page-0816`).
3. Notfalls: Bridge-Restart **nach** Plug/Reset, damit Seal = Root-Presets (Rock…).
4. Artefakt: Status+Menü+Bridge-Tail sichern, dann neu gate.

### AV-PASS (nur nach Gate)
Mitschneiden: `active`, `streamBytes`, `underruns`, `liveBytes`, `absBase`/`absEnd`, `hostAbs` (mit `hostAbs < absEnd`), Zeitmarke Ohr.  
PASS nur wenn: Sender-Slots **und** `active` **und** `liveBytes` steigt **und** Hörprobe.

### Explizit nicht heute
- Detect / Sequenz-GO / Ring-PSRAM-Pacing-Umbau  
- Lock-Refactor in der Bridge  
- C′ wiederholen  

## Lab-Nachzug (optional, nur wenn Zeit vor Feld)

ESP-RST bei laufender Bridge: beobachten, ob Seal wieder Meta aus NVS wird und Bridge Rock nicht mehr durchlässt — dokumentieren unter `artifacts-2026-10-05-lab/`. Kein Fix vor Abend-Feld, außer Gate-Prozedur versagt.

## Ein-Satz-Antwort an GPT

Zustimmung: Architektur trägt; Rest = **Sender-State-Gate** dann **Live-Fenster/Ohr**. Ablehnung: Lock „vollständig aufklären/robust machen“ **vor** dem nächsten Feld-AV — zuerst Gate+Messung, Softwarenacht danach.
