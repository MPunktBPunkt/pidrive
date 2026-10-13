# Analyse D — Resume-P, Mid-File, Cache und Identity

**Stand:** 2026-10-13  
**Ziel:** Blocker vor D1–D3 bestimmen, ohne „Rock stumm“ vorschnell einer einzigen Ursache zuzuordnen.

## Kurzurteil

E7/Busy-Pacing ist nicht mehr der Blocker. Der S6-Lauf beweist aber auch **nicht**, dass Resume-P die Ursache des stummen 8-MiB-Slots war.

Die Rohdaten zeigen zwei konkurrierende Mechanismen:

1. **Vorab gecachte Stille:** `fav0` wurde in S6 zu 98,88 % gelesen, während ein anderer Slot live war. Der ESP liefert für einen nicht aktiven Stationsslot ausschließlich `Mp3Silence`. Die HU konnte Rock daher später aus einem bereits mit Stille gefüllten Cache abspielen.
2. **Mid-File ohne Play-Arm:** Ein Read außerhalb des Head-Fensters wird als `NotFromHead` abgelehnt. Ohne `play.guess` wird S7-B nicht `stallArmed`; es entsteht kein Dauer-Pacing.

Resume-P bleibt plausibel, ist aber nur eine mögliche Ursache für einen Mid-File-Read. Außerdem sind **Decoderposition P, physischer MSC-Read-Offset und Cache-Inhalt drei verschiedene Zustände**.

## Belegbasis

- S3: `artifacts-2026-10-08-feld/feld-s3-prep/s3-20261008-074403/`
- S4: `artifacts-2026-10-08-feld/feld-s4-prep/s4-20261008-165212/`
- S6: `artifacts-2026-10-12-feld/feld-s6-prep/s6-20261012-feld-e7/`
- S7 Lab: `artifacts-2026-10-12-lab/lab-s7-startup/` und `lab-s7-stream-before-guess/`
- D0 Lab: `artifacts-2026-10-12-lab/lab-d0-regression/`
- Firmware: `UsbMscGadget.cpp`, `StreamBuffer.h`, `MscGeometry.h`

## 1. Drei getrennte Zustände

### 1.1 Decoder-/Wiedergabeposition P

Die HU merkt eine Position und kann nach Medienwechsel dort weiterspielen. Das ist eine HU-Eigenschaft und nicht direkt im MSC-Protokoll enthalten.

### 1.2 Physischer MSC-Read-Offset

R24 belegt: Nach einem Replug kann die HU den aktuellen 512-KiB-Titel vollständig ab Offset 0 lesen und trotzdem an P weiterspielen. Ein Head-Read beweist daher **keinen P-Reset**.

Ein UI-Tap kann dagegen R16-artig um P lesen. `fromHead`/`midFile` ist die ESP-Klassifikation gegen `headLbaSlop`, nicht die Decoderposition.

### 1.3 Cache-Inhalt

Wenn die HU eine Datei schon gelesen hat, kann die spätere Auswahl ohne neuen USB-Read erfolgen. Dann kann keine Device-seitige Head-Force reagieren. Entscheidend ist, welche Bytes beim früheren Scan geliefert wurden.

## 2. S6: Muster im 8-MiB-Slot

### 2.1 Long-Audio-Snapshot

Während `streamSlot=1` (`fav1`) aktiv war:

| Feld | `fav0` |
|---|---:|
| `bytes` | 4.018.176 B |
| Anteil am 8-MiB-Slot | 47,90 % |
| `fromHead` | 2 |
| `midFile` | 979 |
| `maxSeq` | 2.826.240 B |
| Trace-LBA | 7089…7849 |
| Trace-Dateioffset | 3.588.096…3.977.216 B |

Gleichzeitig waren `playingUid=""`, `playGuessCount=0` und `stream.uid=fav1`. Die Trace-LBAs gehören eindeutig zu `fav0`; der verkürzte Tag `Rock Antenn` reicht zur Slotzuordnung nicht aus.

### 2.2 Session-Ende

| Feld | Wert |
|---|---:|
| `fav0.bytes` | 8.294.400 B |
| Slot-Abdeckung | **98,88 %** |
| 4-KiB-Callbacks | 2025 von 2048 |
| `fromHead` | 2 |
| `midFile` | 2023 |
| `maxSeq` | 7.102.464 B |

Firmware-FACT: Nur der aktuelle `streamSlot_` bekommt Live-Overlay. Jeder andere Stationsslot wird durch `Mp3Silence::fill()` beantwortet.

Damit ist direkt belegt:

> Die HU las fast den ganzen Rock-Slot, während Rock nicht der Live-Slot war; der ESP lieferte für diese Reads Stille.

Starke Inferenz, noch kein direkter Decoderbeweis:

> Das spätere stumme Autoplay von Rock kam aus diesem vorab gefüllten HU-Cache.

### 2.3 Gegenbelege gegen eine monokausale Resume-Erklärung

- Rock lieferte um 17:02 Bild plus ungefähr 8 s Ton; der Slot ist nicht grundsätzlich unspielbar.
- `fav0` wurde fast vollständig gelesen; „stumm“ bedeutet nicht „keine USB-Reads“.
- Der Long-Audio-Trace liegt bei etwa 3,4 MiB, kann aber Scan/Prefetch sein und muss kein Nutzer-Resume sein.
- Der S6-Lauf hat am stummen Moment keinen vollständigen per-Episode-Read-Trace.

## 3. Identity: Was wirklich verändert wurde

### Bereits negativ

- **USB-Serial allein ist kein ausreichender P-Schlüssel:** S3 überlebte mehrere `PDnnnn`-Wechsel.
- **Dateiname allein ist kein ausreichender Brecher:** S4 K3 blieb Resume-/Mid-File-artig.
- S4 K3 war praktisch sogar eine kombinierte Änderung aus Dateiname, USB-Serial und dem an `remountGen` gekoppelten Root-Label. Auch diese sichtbare Kombination genügte nicht.

### Bisher konstant oder nicht sauber getestet

- FAT12/16 BPB Volume-ID
- BPB-Volume-Label im Bootsektor
- Pfad und Directory-Position
- 8.3-Name/LFN-Kombination als kompletter Directory-Eintrag
- Startcluster
- Dateigröße

`patchBoot()` übernimmt Volume-ID und Boot-Label aus dem statischen Demo-Image. `formatVolumeLabel()` patcht nur den Root-Directory-Volume-Eintrag. Das bisherige Label-Werkzeug prüft somit keine vollständige Volume-Identity.

## 4. S7-B und Head-Force

S7-B ist im Lab belegt:

- nicht armed: Mid-File schnell, p50 etwa 5,5 ms
- nach echtem Head-`play.guess`: armed, p50 etwa 1021 ms

Folge:

- **Kein Read bei Auswahl:** Head-Force kann nicht greifen; es braucht einen echten Cache-/Identity-Brecher oder einen session-neuen Dateipfad.
- **Mid-File-Read:** Ein expliziter Station-Play-Intent könnte diesen einen nächsten Read als Play autorisieren und BUSY armen. Das ist kein erzwungener Head-Read und muss getrennt getestet werden.
- **Head-Read:** Dann liegt der Fehler im Play-Detect-/S7-Gate, nicht in Identity.

`msc.remount_skip` verhindert Remount während aktivem Stream. Identity-Rotation braucht deshalb einen definierten Stop → Remount → Start-Ablauf.

## 5. Prüfung der Berichte

### Bestätigt

- E7-C am NBT: Busy-Pacing verlängert das Ringfenster kausal bis EOF.
- S7-B und D0 sind im Lab grün.
- Fixed Huge File bleibt ein sinnvoller Hauptpfad.
- „BUSY bremst FAT/Directory“ ist als Code-Claim verworfen.
- Resume-/Startzustand muss vor D1–D3 geklärt werden.

### Zu korrigieren

- „fav0 war stumm, weil Resume-P mid-file startete“ ist **keine FACT-Aussage**.
- `first_file_body_offset` allein beweist keinen P-Reset.
- „Volume-Label isoliert testen“ muss BPB-ID, BPB-Label und Root-Label unterscheiden.
- Die Identity-Matrix darf den bereits negativen Serial+Root-Label+Name-Fall nicht bloß wiederholen.

## 6. Entscheidungsreihenfolge

1. S6-Prefetch/Silence-Cache im Lab-Replay reproduzieren.
2. Im NBT bei Permanent-OTG messen, ob die Live-Auswahl keinen, einen Mid- oder einen Head-Read erzeugt.
3. Nur bei Cache-/Resume-Befund Identity testen: zuerst vollständige FAT-Volume-Identity, dann Größe, Pfad/Directory-Position und Startcluster.
4. Head-Force/Mid-Play-Arming und Identity-Rotation nie im selben Lauf.
5. Erst nach einem grünen Startmechanismus D1 → D2 → D3.
6. Offset→Audio-Timeline und `maxMs` erst danach.

## Epistemisches Endurteil

| Claim | Status |
|---|---|
| E7-C funktioniert am NBT | FACT |
| S7-B/D0 funktionieren im Lab | FACT |
| Rock 8 MiB war in S6 oft stumm | FACT |
| Rock wurde als non-live fast vollständig mit Stille beantwortet | FACT |
| Dieser Cache verursachte das spätere stumme Autoplay | starke Inferenz |
| Resume-P verursachte Rock-stumm | Hypothese |
| Serial/Root-Label/Name genügen als Brecher | REJECTED für den beobachteten K3-Pfad |
| BPB Volume-ID, BPB-Label, Größe oder Pfad brechen P | UNKNOWN |
