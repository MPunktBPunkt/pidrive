# Feld F0 — Ergebnis · 2026-10-16 (Morgen, Auto)

**Lauf:** `f0-feld-2026-10-16-am` · FW **0.4.51-dev** · ESP `.89` · Serials `PD0237` → … → `PD0251` (Remount/Panic-Kette)  
**stallEnable:** false (bestätigt: ☑) · OTA 0.4.51: ☑ (bereits on-device; Watcher-Verify-Loop noisy, kein Reflash nötig)

**Operator:** Martin · Desktop-Beobachtung parallel · ~07:26–07:47

---

## Kurzfassung

| | |
|--|--|
| **Ast** | **X** (F0-Matrix nicht gültig) — Produkt-Lesart **P⊕C** (Play-Intent / Prefetch-Cache), Identity **nicht** getestet |
| **Wirksame Dimension(en)** | n/a — B0…B3 nicht gefahren |
| **Nächster Schritt** | (1) Panic bei OTG-Replug beseitigen → stabile Klasse A · (2) kurzes LIVE-Fenster (~6 s Ton+Bild) reproduzierbar machen / Underrun · (3) erst dann F0 B0…B3 |

**Ein Satz:** Smoke/LIVE ist unter Klasse A selten möglich (~6 s Bayern), aber Panic-Replug und Mid-Cache ohne Play-Arm blockieren die F0-Diskriminierung; Soft-Remount `keepIdentity` ändert den HU-Ton nicht.

---

## Pre-Gates

| Gate | OK? | Wert |
|------|-----|------|
| version 0.4.51 | ☑ | `0.4.51-dev` |
| stall_enable=false | ☑ | durchgängig |
| Smoke Head hörbar | △ | erst nach 6–7 Replug-Versuchen ~6 s Ton+Bild Bayern; davor oft Stille trotz Menü |

---

## Was gelaufen ist (Chronik, gekürzt)

| Zeit (ca.) | Ereignis | Klasse / Serial | Ohr / Status |
|------------|----------|-----------------|--------------|
| 07:26 | OTG an; FW bereits 0.4.51, stall off | A · PD0237 | Mount ok, kein Ton beim Tippen |
| 07:29 | OTG raus/rein, oft weiße LED | **B** · → PD0241/PD0242 | Abort-Episoden; `resetReason=panic` |
| 07:30–31 | Stabil PD0242; Bayern/BOB getippt | A | **Stream/Play bei uns an** (`fav1`/`fav2`), trotzdem **kein Ton/Bild** am HU; `bufferMs=0`, Host-Cursor oft fest, Underruns |
| 07:32 | OTG raus/rein | **B** weiß→gelb · PD0243 | verwerfen |
| 07:33–34 | Bayern tip / Replug ohne Weiß | A-ähnlich · PD0244 | Display Bayern weiter, **kein Ton**; Full+Mid auf fav1, `guess=0` |
| 07:38 | Nach 6–7 Versuchen | A · PD0250 | **~6 s Ton+Bild Bayern** — dann weg (Underrun/Cursor) |
| 07:41–43 | SW-Remount `keepIdentity=true` (2×) | A · PD0250 | API ok; **Ton bleibt gleich** (kein Cache-Bruch) |
| 07:44–47 | Weitere physische Replugs | gemischt | ohne Weiß ≠ Ton; zuletzt kein LIVE mehr → Abbruch Feld |

**F0 B0…B3:** nicht gestartet (Smoke/Klasse-A-Lotterie).

---

## Läufe (Matrix)

| ID | Klasse | Isolation | READs | playingUid | Ohr | Claim gültig? |
|----|--------|-----------|-------|------------|-----|---------------|
| B0 | — | — | — | — | — | **nein** (nicht gefahren) |
| B1 serial | — | — | — | — | — | **nein** |
| B2 label | — | — | — | — | — | **nein** |
| B3 volume-id | — | — | — | — | — | **nein** |

---

## Entscheidung (Beobachtungen außerhalb Matrix)

| Beobachtung | ja/nein | Beleg |
|-------------|---------|-------|
| Identity bricht Cache/P | **ungetestet** | keine isolierte B1–B3 |
| Wiedergabe ohne relevante READs / ohne unser Play | **ja** | HU zeigt Station weiter; `playingUid` leer, `streamBytes=0`, trotzdem UI |
| Wiedergabe erst nach Head/Body + unserem Stream | **teilweise** | Tippen kann `playGuess` + Stream armieren; Ohr nur selten |
| Position/Kontext trotz Soft-Remount | **ja** | SW-Remount keepIdentity → „Ton bleibt der gleiche“ |
| Alter Inhalt / Mid-Full ohne LIVE | **ja** | fav0/fav1 oft `midFile` hoch, Full-File-Bytes, `playReject` hoch, `guess=0` |
| LIVE-Pfad existiert | **ja (kurz)** | ~6 s Ton+Bild Bayern nach vielen Klasse-A-Replugs |
| Weiße LED / Panic blockiert | **ja** | `resetReason=panic`; Serial/RemountGen springt; Episode verwerfen |

**Gewählter Ast:** **X** (kein Identity-Claim)  
**Produkt-Hypothese fürs nächste Design:** **P⊕C** — HU hält Play-Intent/Cache; physisches Replug ohne Panic öffnet selten ein kurzes LIVE-Fenster; Soft-Remount keepIdentity reicht nicht.

**Konsequenz:** Stall und D1 bleiben eingefroren. Zuerst Transport-Stabilität (kein Panic bei OTG) und reproduzierbares LIVE>6 s; dann F0-Matrix wiederholen.

---

## Auswertung (Detail)

### 1. Klasse A vs B ist die operative Gate-Regel

Operator-Regel bestätigt: **ohne weiße LED kann Ton entstehen; mit Weiß Episode tot.**  
6–7 Versuche waren vor allem Replug-Lotterie bis stabiles A, nicht „falscher Sender“.

### 2. Unser Play ≠ hörbarer Ton

Mehrfach: `phase=play`, `playingUid=fav1|fav2`, `stream.active=true`, `absEnd` wachsend — HU-Ohr trotzdem Stille, Cover oft leer, `bufferMs=0`.  
→ Pump/Guess greifen; Host konsumiert den Live-Ring nicht zuverlässig (Cursor stuck / Underrun).

### 3. Cache / Mid-Resume

Typisch vor Stille: Slot voll gelesen (`bytes≈fileBytes`, viel `midFile`), `playGuessCount=0`, hohe `playRejectCount`.  
Display „Bayern läuft weiter“ ohne unseren Stream = starkes **P/C**-Signal.

### 4. Soft-Remount ≠ physisches OTG

`POST /api/lab/remount` `keepIdentity=true`: ok, kein Panic, Serial gleich — **Ton unverändert**.  
Für Cache-Eviction / B0-Äquivalent im Feld: physisches OTG (oder Remount ohne keepIdentity / stärkere Media-Hide) nötig.

### 5. Serial-Kette

Beobachtet u.a. `PD0237` → `0241` → `0242` → `0243` → `0244` → … → `0250`/`0251` mit `remountGen` im Gleichschritt.  
Viele Sprünge = Panic/Remount, **nicht** gezielte F0-Identity-Läufe.

---

## Artefakte

| Pfad | Inhalt |
|------|--------|
| dieses `ERGEBNIS.md` | Auswertung |
| `ota-f0-051.sh` / `ota-f0-051.log` | OTA-Watcher (Retry; Gate-Python zeitweise rc=5 trotz korrekter FW) |
| `ota-20261015-235816/` · `ota-20261016-065615/` | frühe OTA-Runden |
| `OPERATOR-LIVE.txt` · `GO.md` · `ANKUNFT.md` | Operator-Prep |
| `f0-identity.sh` · `f0-check.sh` · `run-f0.sh` | Feld-Tooling (Lab-Fixes gespiegelt) |
| `../UEBERGABE-F0-NAECHSTE-KI-2026-10-15.md` | kanonische Übergabe (+ Feld-Nachtrag) |
| Lab: `../../artifacts-2026-10-15-lab/lab-f0-rehearsal/` | Identity 18/18 vor Feld |

Status-Snapshots: Desktop-Live während Lauf (nicht als `status-poll.jsonl` persistiert) — Kernzahlen oben.

**OTA-Spam:** viele `ota-20261016-072*` Retry-Ordner vom Watcher-Loop — absichtlich **nicht** versioniert (Rauschen).

---

## Nicht getan (Freeze)

☑ Stall an · ☑ D1 · ☑ Dimensionen gemischt · ☑ Head-Force im selben Lauf  
☑ F0 B0…B3 Claims

---

## Nächste KI — Auftrag

1. **Panic bei OTG-Replug** auf `.89` / 0.4.51 eingrenzen (UART/Reset-Grund, USB-Hub) — ohne das kein sauberes F0.  
2. **LIVE-Fenster:** warum ~6 s Ton+Bild dann Underrun (`hostAbsCursor` fest, `bufferMs=0`) trotz `stream.active`.  
3. Remount-Semantik: `keepIdentity` vs Media-Hide vs physisches Unplug dokumentieren/härten.  
4. Danach erneut: Smoke hörbar stabil → **B0…B3** nach `PROTOKOLL.md`.  
5. Stall-Feld-Go weiterhin **erst nach** gültigem F0-Ast ≠ X.
