# Gesamtbericht: MSC-Strategie nach Trace-Korrektur — Review Mistral / Claude / GPT

**Stand:** 2026-10-04  
**Normative Basis:** `pidrive` @ `d97fe89` · Plan Rev.4 → dieser Bericht schärft zu **Rev.5**  
**Trace:** [`../artifacts-2026-10-03-m3/auto89-m3seq-2042/`](../artifacts-2026-10-03-m3/auto89-m3seq-2042/) (4218 JSONL)  
**Gegenindiz:** [`../artifacts-2026-10-03-b7/replug-1231-noselect/`](../artifacts-2026-10-03-b7/replug-1231-noselect/)  
**Normativer Vorbericht:** [`../artifacts-2026-10-03-m3/GESAMTBERICHT-AUTO-M3SEQ-TRACE-KORREKTUR-2026-10-04.md`](../artifacts-2026-10-03-m3/GESAMTBERICHT-AUTO-M3SEQ-TRACE-KORREKTUR-2026-10-04.md)  
**Lab-Live (diese Session):** ESP `.88` FW `0.4.42-dev` · Host CT `DebianCursor` `.187` · Baseline [`lab88-baseline-0818/`](lab88-baseline-0818/)

**Evidenz:** **D** = Messdaten · **I** = Interpretation · **(V)** = in dieser Review unabhängig nachgerechnet

---

## 0. Kurzurteil

Die Trace-Korrektur hält: Q2 war gültig gemessen, aber **warm-konfundiert**. MSC als Sequenz kurzlebiger Dateien ist wieder first-class — abhängig vom kalten Auto-Next.

Dieser Bericht konsolidiert **vier Stimmen** (normativer Trace-Bericht, Mistral, Claude, GPT) zu einer verbindlichen Entscheidungsgrundlage. Neu verbindlich gegenüber Plan Rev.4:

1. **P0** braucht Provokationstest (nicht nur „Lock eingebaut“).  
2. **Warmheits-Preflight** muss **maschinenlesbar pro Datei** in die EAR.  
3. **P1 grün** = Body-Reads der kalten Zieldatei innerhalb **±1,5 s** ab Nominalende (vorläufig), **×2** reproduziert.  
4. **Q3a** (ESP liefert B) ≠ **Q3b** (HU spielt B) — Lab allein entscheidet nicht über Hörwiedergabe.  
5. **Scan-Einfrieren** kleiner Dateien ist ein Design-Constraint (D, V): 512 KiB-Slots können beim Scan voll gelesen werden.  
6. **L4** (große Datei / Dension-Diagnose) als **P2c**, ohne P1 zu blockieren.  
7. Entscheidungsregel mit **Q3a-Zwischenknoten** und optionalem **Dension-Modus** nach positivem L4.

**Freeze bleibt:** kein Ring, kein PSRAM, kein Remount-Karussell, kein AAIdrive-Sprint vor grünem P1.

---

## 1. Lab-Live-Stand (D, 2026-10-04)

| Punkt | Befund |
|-------|--------|
| ESP `.88` | erreichbar, `0.4.42-dev`, `labMode=true`, `otgUp`, `mscReady`, Serial `PD0035`, `remountGen=35` |
| USB am CT `.187` | ESP32-S3 `303a:1001` als `usb-storage` → Kernel-`sda`/`sg0` vorhanden |
| Node-Lücke | `/dev/sda` und `/dev/sg0` **fehlen** im Container (kein Device-Node) → Host-Reads/Q3 blockiert bis `mknod` |
| Bridge `.105` / Host `.108` | SSH-Port offen, Login ohne Key; HTTP nicht genutzt |
| Pump-TCP `:9090` | Port offen, `pumpTcpUp=false` (kein Peer) |
| Menü (Live) | `Zurueck` / `Ausgang klinke` / `Auto` / `Mehr...` — **P0-Bug sichtbar** (Pi-UI-Namen auf MSC-Slots) |
| Warmheit Baseline | nach `POST /api/lab/stop`: slot0 `bytes=323584`, slot1/2 `bytes=0` — Fav1/2 derzeit kalt bzgl. Body-Counter |

Artefakte: `lab88-baseline-0818/status-after-lab-stop.json`, `menu.json`.

---

## 2. Unabhängige Nachrechnung der Kernclaims (V)

### 2.1 Trace-Cluster (gap > 2 s) — bestätigt

| Cluster | Σn | Kernslots | Deutung |
|---------|-----|-----------|---------|
| C0 Mount | 167 | fav2:128, meta:31, fav0:8 | Mount: **fav2 voll**, nicht reines Meta-Idle |
| C1 Select Rock | 1987 | fav0 | Select-Vollread ~8 s |
| C2 Bayern | 128 | fav1 | 512 KiB voll |
| C3–C4 Remount | … | fav0 Resume | Resume ohne Select |
| C5 Re-Scan | 381 | **fav1:128**, fav2:85, fav0:105 | PD0047-Scan: **fav1 eingefroren** |
| C6 Select nach Scan | 1076 | fav0 | Arm3b „Δrc=0 immer“ widerlegt |
| C8 später | 2345 | fav1:138 u. a. | erneuter Scan-Anteil auf fav1 |

**(V)** Claudes „kleine Dateien können beim Scan einfrieren“ ist messdatenfest. Chunks ≤ ~512 KiB sind für ein Sequenz-Modell riskant, sofern der Scan sie vollständig liest.

### 2.2 Morgenpass `replug-1231` — Counter-Indiz, kein LBA-Beweis

Aus `EAR.txt` (FW `0.4.36-dev`):

| t | rc | play |
|---|-----|------|
| 6,6 s | →165 | Scan quiet |
| 21,6 s | 165→293 (+128) | `fav1` Autoplay |
| 108,7 s | 293→390 | `fav0` |
| 110,3 s | 390→421 (+128 gesamt ab 293) | `fav0` |

21,6 + ≈87,4 ≈ 109,0 s Nominalende; Reads bei **108,7 s** → Übergang ± ~1 s.  
**Korrektur an früherer Formulierung:** Das ist ein **starkes Counter-/Detektor-Indiz**, **kein** LBA-Beweis. Claude hat recht; Mistral/Plan-Wortlaut „LBA-Beweis“ war zu hart.

**Vorläufige P1-Schwelle (I, gestützt auf D):** erster Body-Read der kalten Zieldatei innerhalb **±1,5 s** ab Nominalende.

---

## 3. Bewertung der Berichte

| Thema | Mistral | Claude | GPT (Konsolidierung) | Diese Entscheidung |
|-------|---------|--------|----------------------|--------------------|
| Trace-Korrektur / Warm-Confound | richtig | richtig | richtig | **normativ übernehmen** |
| Menü-Lock | Provokationstest + messbar | Feldtest | Session-Zustandsmodell | **P0 verbindlich mit Provokation** |
| Preflight | maschinenlesbar in EAR | pro Datei `slotMap.bytes` | beides | **EAR-Zeile + pro Datei** |
| P1-Zeitfenster | fordert Definition | ±1,5 s aus Morgenpass | übernimmt | **±1,5 s vorläufig** |
| Morgenpass | „LBA-Beweis“ zu hart | kein LBA, Timing stark | korrigiert | **Counter-Indiz** |
| Scan-Freeze kleiner Dateien | untergewichtet | zentral (D) | übernimmt | **Design-Constraint** |
| Q3 | Lab A/B | Lab ≠ HU-Hörbeweis | Q3a/Q3b-Trennung | **Q3a Lab, Q3b Auto** |
| L4 große Datei | nicht priorisiert | öffnen | P2c parallel | **P2c, kein P1-Blocker** |
| Dension | Randnotiz | Katalog/Puffer | Hypothese, Original prüfen | **P4 Diagnose** |
| BT-Hybrid | parallel | parallel | UX-Abnahme scharf | **P2b parallel** |
| AAIdrive / Connected Apps | Langfrist | Langfrist | nur wenn B scheitert + 6NR | **P4, kein Sprint** |
| Ring/PSRAM | Freeze | Freeze | Freeze | **halten bis P1×2 grün** |

### 3.1 Was von Mistral bleibt

- Warm vs. ungültig sauber trennen.  
- P0 ohne Nachweis ist nur Behauptung (I).  
- Preflight muss exportiert werden, sonst droht die nächste Nachanalyse-Korrektur.  
- „P1 grün“ ohne Zeitfenster ist nachträglich dehnbar — inakzeptabel.

### 3.2 Was von Claude bleibt / korrigiert

- **Bleibt:** Scan-Freeze, Morgenpass-Timing, Q3 Lab allein unzureichend für HU-Wiedergabe, L4 als fehlender Zweig, Dension als Vergleichshypothese.  
- **Einschränkung:** „Q3 im Lab nicht beantwortbar“ ist zu absolut → nur **Q3b**. **Q3a** (ESP liefert B-Bytes) ist Lab-pflichtig.  
- Dension-Katalogwerte (K61, 5 s) = Händlerangaben → vor Designentscheidung Originalunterlagen.

### 3.3 Was von GPT bleibt

- Session-Zustandsmodell für MSC-Map-Freeze.  
- Entscheidungslogik mit Q3a-Zwischenknoten („Q3a rot → Payload fixen, nicht Architektur aufgeben“).  
- P1-Klasse B mindestens **×2** reproduzieren.  
- L4 als P2c ohne P1-Verzögerung.  
- BT-UX-Abnahme (Verbindung, AVRCP, Metadaten, Quellwechsel-Schritte).

---

## 4. Arbeitsmodell (I, gestützt auf D)

> Pro Mount und Datei: **ein großer Body-Read** beim ersten Start (Select / Autoplay / Resume). Danach Cache → null Reads, auch bei Trackende auf **warmes** Ziel.

Zusatzregeln nach dieser Review:

1. **Scan kann kleine Dateien voll lesen** → „kalt“ nur per Trace/`slotMap.bytes` nach Scan belegen, nicht annehmen.  
2. **Burst ≫ Live-Rate** (~1 MiB/s vs. ~6 KiB/s @48 kbit/s) → Inhalt muss **vor** Start im Slot liegen.  
3. **Kopf-Stale / Scan-Stale** und **Body-Frische beim Erstabspiel** sind getrennte Fragen (Q3a/Q3b).  
4. **Große Datei > HU-Cache** (L4) ist ein dritter Betriebsmodus-Kandidat („Dension-Modus“), bisher ungetestet.

---

## 5. Produktpfade und Entscheidungsregel

### Pfade

| Pfad | Kern | Entscheidet |
|------|------|-------------|
| **A** Sequenz | N Chunk-Dateien, Start-Burst = frische Bytes | P1 + Q3a (+ später Q3b) |
| **B** BT-Hybrid | USB=Menü, Ton=A2DP | P2b UX |
| **A′** Dension-Modus | eine/große Datei, fortlaufende Reads | L4 positiv |
| **C** Connected Apps | AAIdrive-Linie, Audio weiter A2DP | nur wenn B-UX scheitert und 6NR |

### Entscheidungsregel (verbindlich)

```
P0 Menü-Lock (Provokation PASS)
        │
        ▼
P1 kalter Auto-Next (±1,5 s, Ziel kalt, ×2)
        │
   ┌────┴────┐
 GRÜN      NICHT GRÜN
   │           │
   ▼           ▼
 Q3a Lab     BT-Hybrid (B)
  frisch         │
   │             ▼
 ┌─┴─┐       UX-Abnahme P2b
GRÜN ROT
 │    │
 ▼    ▼
Sequenz  Payload-Veröffentlichung
 (A)     korrigieren (kein Architektur-Abbruch)
 │
 ▼
BT als Fallback

L4 positiv (fortlaufende Reads) → A′ parallel bewerten,
  bevor B final als einziges Hauptprodukt festgeschrieben wird.

Pfad C: nur bei unzureichender BT-UX und nachgewiesenem 6NR.
```

---

## 6. Verbindliche Abnahmen

### 6.1 P0 — MSC-Session-Lock

**Zustandsmaschine:**

```
USB_DISCONNECTED → USB_SESSION_START → MSC_MAP_FROZEN
  → Pi-UI intern dynamisch erlaubt
  → publizierte MSC-Namen + Slot-LBA unveränderlich
→ USB_SESSION_END → MSC_MAP_RELEASED
```

**Provokationstest (Abnahme):**

| Schritt | Aktion | Erwartung |
|---------|--------|-----------|
| 1 | ESP an Host/HU | Session start |
| 2 | slotMap erfassen | Baseline Name/UID/LBA |
| 3 | Scan abwarten | Dateien erkannt |
| 4 | Pi-UI bewusst anderen Sender wählen | interne Auswahl ändert sich |
| 5 | slotMap erneut | **Namen + LBA identisch** |
| 6 | USB trennen | Lock frei |
| 7 | neu verbinden | neue Zuordnung erlaubt |
| 8 | Regression | `menu_set` während Freeze → reject/defer, geloggt |

Live-Beleg des Bugs (D): Lab `.88` zeigt jetzt `Zurueck/Ausgang/Auto` auf den MSC-Slots.

### 6.2 P1 — Kalter Auto-Next

**Setup:** FW `0.4.42-dev`, Menü-Lock an, Bridge vor Plug, neue Serial, LBA-Trace vollständig, **kein** manueller Next-Select.

**Ablauf:** Mount → Scan → Preflight (kalt pro Datei) → nur kurze Datei starten → Trackende → Auto-Next → Timing + LBA + Payload-Frische getrennt → A–E.

**Zwei Durchläufe** (A passiv, B Wiederholung). Ein einzelner positiver Übergang reicht nicht.

**Erfolg (vorläufig):** Body-Reads kaltes Ziel, Umfang ≈ Dateigröße, Start innerhalb **±1,5 s** Nominalende, Preflight-Zeile in EAR vorhanden, `ov`/TCP gültig.

**EAR-Pflichtfelder (maschinenlesbar):**

```
preflight.warmth.<slot> = {bytes_after_scan, cold: bool, lba0, lba1, name, uid}
p1.nominal_end_s
p1.first_body_read_s
p1.delta_s
p1.class = A|B|C|D|E
```

### 6.3 P2a — Q3a Lab

Payload A → nach Scan, vor Erstabspiel → Payload B. Erfolg = Host/Hash zeigt **B-Bytes** (nicht nur Δrc). Marker/Hash-Kette.

### 6.4 P2b — BT-Abnahme

Verbindung nach Zündung · AVRCP · Metadaten/Cover · **Quellwechsel-Schritte** USB-Menü→BT.

### 6.5 P2c — L4 Diagnose (64 MiB, gültiges Audio, Marker M0…M5)

| Ergebnis | Bedeutung |
|----------|-----------|
| Ein Voll-Burst dann Stop | Cache-Limit |
| Mehrere Bursts / Reads während Play | Nachforder-Verhalten |
| Fortlaufend über Wiedergabe | Kandidat A′ |
| Keine frischen Reads nach Start | dynamisches Überschreiben ungestützt |

Positives L4 ≠ Beweis für Mid-File-Rewrite; dafür separater Re-Read-Nachweis nötig.

### 6.6 Sequenz-Geometrie (Constraint aus Scan-Freeze)

Bis P1+Scan-Verhalten geklärt:

- Chunks **≥ ~768 KiB** **oder**  
- bewusster **statischer Kopf-Vorlauf** (~0,5 MiB), der Scan-Stale absorbieren darf, Body danach frisch (Q3a).

„Nur ~32 KiB Kopf-Stale“ ist für 512 KiB-Slots **zu optimistisch** (D).

---

## 7. Arbeitsplan (Rev.5)

| Prio | Arbeit | Done wenn |
|------|--------|-----------|
| **P0** | MSC-Session-Lock + Provokation + Regression | Namen/LBA stabil; Reject geloggt |
| **P1** | Kalter Auto-Next Feld ×2 | ±1,5 s, kalt belegt, EAR-Preflight, LBA |
| **P2a** | Q3a Lab A/B | Hash/Marker B-Bytes |
| **P2b** | BT-UX Abnahme | Checkliste 4 Punkte |
| **P2c** | L4 große Datei | Read-Muster klassifiziert |
| **P3** | Sequenz-Prototyp | nur nach P1×2 + Q3a grün; dann Ring ≥ Chunk |
| **P4** | Dension-Abgleich, 6NR, AAIdrive-Notiz | kein Coding-Sprint |

### Explizit nicht tun

- Ring/PSRAM/Pacing vor P1×2 grün  
- Remount-Karussell als Streaming  
- Warme Auto-Next-Fenster als Architekturbeweis  
- Hörbarkeit aus `phase=play` ableiten  
- Q3b als „im Lab erledigt“ verkaufen  
- AAIdrive-Port als nächsten Sprint

---

## 8. Lab-Fortsetzung — Blocker und nächste Schritte

**Jetzt möglich ohne sudo:** Status/Menu/Lab-API (`/api/lab/stop|remount|play`), Pump-TCP-Connect-Test, Doku/Tools.

**Blocker Host-Reads/Q3:** Im LXC fehlen Device-Nodes:

```bash
sudo mknod -m 660 /dev/sda b 8 0
sudo mknod -m 660 /dev/sg0 c 21 0
sudo chgrp disk /dev/sda /dev/sg0   # oder passende Gruppe
```

Major:Minor verifiziert: `sda` = `8:0`, `sg0` = `21:0` (Kernel sieht das Gerät).

**Nächste Lab-Schritte sobald Nodes da:**

1. Frischer Remount (`POST /api/lab/remount`) + Favoriten-Menü (nicht Pi-UI-Actions).  
2. Preflight-Export-Prototype (JSON-Zeile pro Slot).  
3. Q3a A/B auf fav1 (kalt, 512 KiB) mit Hash vor/nach.  
4. Optional L4-Asset vorbereiten (gültige MP3-Kette, Marker), Lauf später.

**P0-Implementierung** sitzt primär in `esp32.pidrive/tools/pump_bridge.py` (`menu_set`-Pfad, ~Z.1789ff) und ggf. ESP-seitig Remount-bei-`menu_set` — getrennt vom Host-Read-Blocker, kann parallel gebaut werden.

---

## 9. Grenzen dieser Review

- Trace-Aussagen beruhen auf JSONL-Auswertung, nicht HU-Dokumentation.  
- Dension-Betriebsmodell = Hypothese.  
- Mount-Session-Variation (wann fav1 beim Scan voll gelesen wird) ist nicht erklärt.  
- Morgenpass andere FW/Geometrie — ersetzt P1 nicht.  
- Lab-Host ≠ NBT; Q3b und P1 bleiben Auto-exklusiv.

---

## 10. Fazit

Die MSC-Strategie ist **nicht gescheitert**. Sie steht an einem präzise definierten Entscheidungspunkt:

> Liest die NBT beim Übergang auf eine **nachweislich kalte** Datei rechtzeitig Body-LBAs — und sind diese Bytes frisch?

Alles andere (Ring, Pacing, AAIdrive, Remount-Tricks) ist vor dieser Antwort Spekulation mit Kosten.  
**Nächster produktiver Schritt:** P0 absichern → P1×2 im Auto → parallel Q3a im Lab und BT-UX. L4 öffnen, aber nicht den kritischen Pfad aufblasen.

---

## 11. Übergabe an die nächste Sitzung

1. `sudo mknod` für `/dev/sda` + `/dev/sg0` auf `.187`.  
2. P0 in `pump_bridge` (Freeze bei `msc.plugged`) + Provokationstest-Skript.  
3. EAR-Preflight-Felder in Feld-Tools.  
4. Q3a Lab-Lauf auf kaltem fav1.  
5. P1-Checkliste für Auto-Termin (kein FW-Wechsel, Lock an, ×2).  
6. Plan-Datei auf Rev.5 zeigen; Ring Freeze halten.

Quellen: dieser Bericht · Trace-Korrektur `d97fe89` · `auto89-m3seq-2042/` · `replug-1231-noselect/` · Chat-Reviews Mistral/Claude/GPT 2026-10-04.
