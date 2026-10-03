# Gesamtbericht: Auto-M3seq Trace-Korrektur und Lösungspfad

**Stand:** 2026-10-04  
**Repo:** `pidrive` @ `9b57704` (+ dieser Doc-Push) · FW Feld `0.4.42-dev` L3  
**Artefakt:** [`auto89-m3seq-2042/`](auto89-m3seq-2042/) (20:42–21:02)  
**Gegenindiz:** [`../artifacts-2026-10-03-b7/replug-1231-noselect/`](../artifacts-2026-10-03-b7/replug-1231-noselect/) (Morgenpass, FW `0.4.36-dev`)  
**Eingearbeitet:** Feld-REPORT/EAR · Mistral-Übergabe · GPT-Gesamtbericht · Trace-Zeitreihen-Korrektur · AAIdrive/Pfad-C-Skizze · **eigene Vollauswertung aller 4218 JSONL-Bursts**

**Evidenz:** **D** = Messdaten · **I** = Interpretation · **(V)** = in dieser Review unabhängig nachgerechnet

---

## 0. Kurzurteil

Die Messkette des Abends war gut (M0/TCP/`ov=0` im Q2-Fenster). Die **Architektur-Schlussfolgerung „Q2 negativ ⇒ MSC-Live tot“ war falsch**, weil die Messfrage im Q2-Fenster nicht existierte: alle drei Dateien waren bereits warm.

Neu belastbares Arbeitsmodell **(D, V)**:

> Die NBT liest jede Datei **einmal weitgehend vollständig** beim ersten Abspielen (Select, Autoplay oder Resume nach Replug), typisch ~0,5–8 s bei ~1 MB/s. Der Mount-Scan liest Köpfe (+ ggf. eine alphabetisch frühe Datei vollständig). Danach: **null Reads** für diese Datei, egal ob UI-Play, Trackende oder Auto-Next auf ein **warmes** Ziel.

Daraus folgt **kein** sofortiger Freeze von MSC als Produktpfad und **kein** sofortiger BT-Hybrid-Zwang. Es folgt ein **Zwei-Test-Sprint**, der die Entscheidung datengestützt macht:

1. **Kalter Auto-Next** (15 min Auto, kein FW-Wechsel) — entscheidet Sequenz-Modell.  
2. **BT-Quellwechsel-UX** (parallel) — entscheidet Hybrid-Fallback.  
3. **Menü-Lock** vorher — blockierend für jede weitere Feldauswertung.

Connected-Apps (AAIdrive) bleibt **Pfad C / Langhorizont**, kein Quartalsziel.

---

## 1. Unabhängige Trace-Verifikation (V)

Quelle: `auto89-m3seq-2042/pidrive_msc_reads.jsonl` · 4218 Zeilen · `2026-10-03 20:42:32`–`21:01:53` (Pi-Zeit, CEST).  
Slot-LBA aus `status-02-after-rock-select.json` (vor Menü-Überschreibung):

| Slot | Name (früh) | LBA | Größe |
|------|-------------|-----|-------|
| fav0 | Rock Antenne | 81–16464 | 8 MiB |
| fav1 | Rock Antenne Bayern | 16465–17488 | 512 KiB |
| fav2 | Radio BOB! | 17489–18512 | 512 KiB |

### 1.1 Zeitfenster (gap > 2 s)

| Zeit | Σn | Bytes | Zuordnung | Deutung |
|------|-----|-------|-----------|---------|
| 20:42:32–33 | 167 | 656 KiB | **fav2:128** + meta:31 + fav0:8 | Mount: Meta + **komplette fav2** (512 KiB), nicht „Idle-Meta“ |
| 20:43:09–17 | 1987 | 7948 KiB | **fav0:1987** (~1,03 MB/s) | Select Rock, ~35,7 s nach Scan-Ende → **eigenständiger Select-Trigger** |
| 20:44:56 | 128 | 512 KiB | **fav1:128** | Select/Start Bayern = **Voll-Read** |
| 20:44:56–20:53:36 | **0** | 0 | — | Q2-Fenster: ~8,7 min Stille |
| 20:53:36–37 | 42 | 168 KiB | meta+fav0-Kopf | Replug/Scan-Anfang |
| 20:53:52–59 | 1963 | 7852 KiB | **fav0:1963** | **Resume-Vollread ohne Select** (~15 s nach Scan-Kopf) |
| 20:54:05 | 42 | 168 KiB | meta+Kopf | kurzer Nach-Scan |
| 20:56:07–09 | 339 | 1342 KiB | fav1:128, fav0:93, fav2:85, meta | PD0047 Scan (Köpfe + fav1 voll) |
| 20:56:43–47 | 1076 | 4304 KiB | **fav0:1076** | Select nach Scan (~33,5 s Ruhe) — **Arm3b Δrc=0 gilt hier nicht** |
| 20:56:51–54 | 930 | 3720 KiB | fav0:864 + fav2:37 | Fortsetzung / weiterer Zugriff |
| 20:59:34–43 | 2006 | 8024 KiB | fav0:1963 + fav2 | PD0048 Resume (Export `ov=144` beim Stecken) |
| 21:01:47–53 | 382 | ~1,5 MiB | Köpfe/Teile | PD0049 / Radio aus |

### 1.2 Was damit feststeht (D, V)

1. **„quiet rc=167“ war kein reines Meta-Idle:** fav2 wurde beim Mount vollständig gelesen (vermutlich Autoplay/Prefetch der alphabetisch frühen Datei „Radio BOB!“).  
2. **Q1 Select-Trigger ist mehrfach und klar:** Rock 35,7 s nach Scan; Bayern 99 s nach Rock-Burst; PD0047 Select ~33 s nach Scan — alles File-Body, nicht nur DIR/FAT.  
3. **Q2 Δrc=0 war messtechnisch gültig** (TCP up, `ov=0`) **und inhaltlich konfundiert:** ab 20:44:56 waren fav2, fav0 und fav1 bereits (nahezu) vollständig gelesen. Auto-Next auf warmes Rock **muss** null Reads liefern.  
4. **Remount-Resume ohne Select** ist belegt (20:53:52 fav0).  
5. **Arm3b „Selects nach Scan immer Δrc=0“ ist falsch** als allgemeine Regel: PD0047 erzeugte große fav0-Reads. Flat-rc-Beobachtungen danach betrafen bereits warme Ziele.  
6. **Scan ≠ Vollscan aller Dateien:** typisch Köpfe (≈85–128 Reads) plus gelegentlich eine volle kleine Datei.

### 1.3 Morgenpass `replug-1231-noselect` — Gegenindiz für kaltes Auto-Next

EAR/Polls (FW `0.4.36-dev`, andere Geometrie, `ov=72`):

| t | Ereignis | rc |
|---|----------|-----|
| 6,6–8,2 s | Scan → quiet | 165 |
| 21,6 s | Autoplay `play=fav1` (ohne Select) | 165→293 (+128) |
| 108,7–110,3 s | Operator: Bayern ende → Autoplay Rock | 293→421 (+128), `play=fav0` |

Δt 21,6→108,7 ≈ **87 s** ≈ damalige Bayern-Länge. Das ist ein **starkes Indiz**, dass **kaltes** Auto-Next liest — aber: andere FW/Geometrie, Overflow, keine vollständige LBA-JSONL für den Übergang. Es stützt das Modell, **ersetzt** den gezielten L3-Kalt-Test nicht.

---

## 2. Bewertung der Berichte

| Quelle | Bleibend richtig | Korrigiert |
|--------|------------------|------------|
| Feld-REPORT | Struktur, Session-Disziplin, PD0048-Integrität, Menü-Bug | „Idle=Meta“; Arm3b pauschal Δrc=0; Q2 als Architektur-Negativ |
| Mistral | Messqualität, Menü-Lock, Q3-Protokoll, Freeze Ring ohne Konsum | „genau einmal pro Titelidentität“ zu absolut; „NBT kein Streaming-Client“ zu hart; Q1 „einmalig“ falsch; Fill-the-Burst als Live-Pfad übergewichtet |
| GPT (vor Trace) | Burst≠Live-Rate; BT parallel; Menü-Lock; relative Formulierung | „Q2 gültig negativ ⇒ MSC-Live pausieren“ verfrüht; Q1-Auslöser inzwischen klar |
| Trace-Korrektur | Warmheits-Confound; Modell „ein Start = ein Voll-Read“; kalter Auto-Next als P1 | „Q3 weitgehend beantwortet“ zu früh; Sequenz-Modell als Produkt noch bedingt |
| AAIdrive-Skizze | Pfad C existiert; BMW nutzt A2DP für App-Audio; 6NR-Voraussetzung | Nicht als nächster Sprint — Reverse-Engineering + MyBMW-Handshake |

**Lernpunkt für Testdesign:** M0 prüft Export-Integrität. Neu Pflicht: **Pre-Flight-Warmheits-Check** — vor jedem Trigger-Fenster per `slotMap.bytes` / Trace dokumentieren, welche Dateien noch kalt sind. Ein Null-Befund ohne kaltes Ziel ist wertlos.

---

## 3. Arbeitsmodell (I, gestützt auf D)

**Regel:** Pro Mount und Datei genau ein großer Body-Read beim ersten Start (Select / Autoplay / Resume). Danach Cache.

**Einschränkungen:**

1. **Kopf-Stale:** Scan liest Köpfe (ID3/Xing, bis ~512 KiB bei kleinen Dateien). Body beim Erstabspiel kann frisch sein — **muss** Q3 noch messen.  
2. **Burst-Rate ≫ Live-Rate:** ~1 MB/s vs. ~6 KiB/s @48 kbit/s → Inhalt muss **vor** dem Start im Slot liegen (Chunk-Vorlauf). Das widerlegt unendliche Overlay-Dateien, **nicht** ein Sequenz-Modell.  
3. **Statisches Verzeichnis:** Nur vorab veröffentlichte Dateien; jede Datei einmal kalt. Danach Remount (Resume-Read belegt).  
4. **Kalter Auto-Next:** offen für L3-Abendgeometrie; Morgenpass-Indiz positiv.  
5. **Hörbarkeit:** dieser Lauf `--no-audio` + Silence — Ebene‑4-Ton nicht belegt.

---

## 4. Drei Produktpfade

### A — MSC-Sequenz-Modell (Chunk-Dateien)

N vorab sichtbare Chunk-Dateien (30–60 s). Pi füllt Chunk k+1, bevor die HU Chunk k beendet. Start von k+1 (Auto-Next oder Select) = Voll-Burst über frische Bytes. Nach N Chunks: Serial-Bump/Remount.

- **Pro:** eine USB-Quelle (Dension-nah); Trigger Select/Resume feldbelegt; Morgenpass-Indiz für Auto-Next.  
- **Contra:** kaltes Auto-Next Timing unbewiesen; Remount-Pausen; Ring ≥ 1 Chunk (~192–256 KiB) erst nach P1-Grün; Kopf-Stale.  
- **Erfolg:** ≥20 min Hörzeit, max. 1–2 kurze Remount-Pausen, Cover/Namen stabil.

### B — BT-Hybrid (USB=Menü, Ton=A2DP)

- **Pro:** Audiotransport bewährt; unabhängig vom MSC-Cache; alle Quellen über einen Encoder-Pfad.  
- **Contra:** zwei NBT-Quellen / Quellwechsel-UX ungemessen; AVRCP-Metadaten begrenzt; löst den ursprünglichen „drei Zeilen MPRIS“-Schmerz nur teilweise.  
- **Erfolg:** Senderwahl → Ton ohne zweiten Bedienschritt (oder akzeptabler ein Schritt); Reconnect nach Zündung.

### C — Connected-Apps (AAIdrive-Linie)

Remote-HMI über BMW Apps-Protokoll, Audio weiter A2DP. Beste UX-Obergrenze, aber: 6NR, MyBMW-Handshake, RE-Aufwand, Projekt archiviert. **Jahresziel**, nur prüfen wenn A fällt **und** Fahrzeug 6NR aktiv hat.

---

## 5. Meine Lösung und Priorität

**Entscheidung jetzt nicht endgültig fällen.** Das Fundament „kalibriert negatives Q2“ ist als Architekturargument zurückgezogen. Beide Kurzpfade (A und B) haben je **eine** große Unbekannte, beide in einem Auto-Termin messbar.

### Verbindliche Reihenfolge

| Prio | Maßnahme | Warum |
|------|----------|-------|
| **P0** | **Menü-Lock / MSC-Session-Lock** | Ohne stabile Slotnamen ist jeder Feldtest und jedes Produkt kaputt (Abend: Zurueck/Ausgang/Auto). Pi-UI darf publizierte MSC-Namen während USB-Session nicht still überschreiben. |
| **P1** | **Kalter-Auto-Next-Feldtest** (≈15 min, kein FW-Wechsel) | Frischer Mount → Pre-Flight: welche Datei kalt? → kurze Datei bis Ende → Auto-Next auf **nachweislich kalte** Datei → LBA-Trace + Timing relativ zum Übergang. Menü-Lock aktiv. |
| **P2a** | **Q3 minimal im Lab** | Payload A→B zwischen Scan und Erstabspiel; Hash + hörbarer Marker; Erfolg = B-Bytes geliefert (nicht nur Δrc). |
| **P2b** | **BT-Abnahme parallel** | A2DP/AVRCP/Reconnect **und** Quellwechsel-UX USB↔BT als eigene Messfrage. |
| **P3** | Sequenz-Prototyp **nur wenn P1 grün** | Dann punktuell Ring ≥ 1 Chunk (datenbegründet). Freeze sonst halten. |
| **P4** | Pfad C nur explorativ | 6NR-Check im Fahrzeug; kein Sprint ohne positives A-Aus und 6NR. |

### Entscheidungsregel

```
P1 kalter Auto-Next liest rechtzeitig + P2a Frische OK
    → Hauptpfad A (Sequenz), B als Fallback/Übergang
sonst
    → Hauptpfad B (BT-Hybrid), A nur noch Clip/Diagnose
Pfad C
    → nur wenn B-UX inakzeptabel und 6NR vorhanden
```

### Explizit nicht tun

- Ring/PSRAM/Pacing **vor** P1-Grün wieder öffnen.  
- Remount-Karussell als Streaming „implementieren“.  
- Weitere **warme** Auto-Next-Fenster als Architekturbeweis.  
- „Hörbare Wiedergabe“ aus `phase=play` / UI-Balken ableiten.  
- Q3 als erledigt verkaufen ohne A/B-Payload-Nachweis.  
- AAIdrive-Port als nächsten Coding-Sprint starten.

---

## 6. Protokoll-Skizze: Kalter Auto-Next (P1)

1. Bridge up **vor** Plug; Menü-Lock an; `--no-audio` ok für Read-only, optional später mit Ton.  
2. Neue Serial; Scan abwarten; Status: `slotMap.bytes` / Trace → **kalt**-Liste festhalten.  
3. Bewusst **nur eine kurze** Datei starten (512 KiB), andere unberührt lassen.  
4. Trackende abwarten; **kein** manueller Select auf Ziel.  
5. Messen: Zeitpunkt erster Body-Reads der kalten Datei relativ zu UI-Ende/Auto-Next; `Δrc`, LBA, `ov`, TCP.  
6. Erfolg: Body-Reads der kalten Datei **vor oder unmittelbar beim** Übergang, Umfang ≈ Dateigröße.  
7. Misserfolg: Δrc=0 trotz kaltem Ziel → Sequenz-Modell für nahtloses Radio schwach; Timeshift/Remount oder Pfad B.

---

## 7. Projektstand (nach Korrektur)

| Baustein | Status |
|----------|--------|
| M0 Messintegrität | ✅ Lab + Feld |
| M3 statisch A_then_E | ✅ im Fenster |
| M3seq Q1 Select | ✅ mehrfach, Trigger klar (V) |
| M3seq Q2 warmes Auto-Next | ✅ Δrc=0 gültig, **Architektur-Negativ zurückgezogen** |
| M3seq Q2 kaltes Auto-Next | 🔜 P1 (Morgenpass nur Indiz) |
| Arm3 Remount | ✅ Scan + Resume-Vollread; Select nach Scan nur wenn kalt |
| Q3 Frische | 🔜 Lab P2a |
| Menü-Stabilität | ❌ Feldfehler → P0 |
| Sequenz-Modell | bedingt, wartet auf P1 |
| BT-Hybrid | parallel P2b |
| Connected-Apps | Langhorizont C |
| Ring/PSRAM/Pacing | Freeze bis P1-Grün |

---

## 8. Fazit

Der Abend hat die Messqualität geliefert, aber die **falsche Frage** als Architektururteil verkauft. Die Rohtrace korrigiert das: MSC-Live als **eine unendliche, nachgefüllte Datei** bleibt ungestützt; MSC als **Sequenz kurzlebiger Dateien mit Start-Burst** ist wieder first-class — abhängig vom kalten Auto-Next.

**Weg zum Erfolg:** Menü-Lock bauen → kalten Auto-Next messen → parallel BT-UX abnehmen → dann wählen. Nicht umgekehrt aus dem warmen Q2-Null eine Produktentscheidung ableiten.

---

## 9. Übergabe an die nächste KI (1 Absatz)

Zuerst `pidrive_menu.json`-Überschreibung während aktiver USB-Session sperren (MSC-Session-Lock + Regression). Dann Auftrag/Checkliste für **kalten Auto-Next** mit Pre-Flight-Warmheits-Check schreiben und im BMW ausführen (Artefakt analog `auto89-m3seq-2042/`). Parallel Q3-A/B im Lab und BT-Quellwechsel-Checkliste. Ring Freeze halten. Sequenz-Prototyp und Ring-Resize **nur** nach grünem P1. AAIdrive/6NR nur notieren, nicht bauen. Quellen: dieser Bericht, `auto89-m3seq-2042/`, `replug-1231-noselect/`, ältere GPT/Mistral-Texte nur noch historisch.
