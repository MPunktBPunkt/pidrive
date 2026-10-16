# Feld P0 · 512 KiB MessCapture — Ergebnis · 2026-10-16 (Nachmittag, NBT)

**Lauf:** `feld-512kib-predict-01` · FW **0.4.52-dev** (mess / `cmdCapture`) · ESP `.89` · Serials `PD0261` → … → `PD0282`  
**stallEnable:** false · Capture-Mode: `ram_local`  
**Operator:** Martin · Desktop-Beobachtung parallel · ~16:04–16:33 · **Feldende:** ESP aus

**Bezug:** Lab-Prep `../../artifacts-2026-10-16-lab/P0-512KIB-MODELLTEST.md` · Matrix Derived `docs/fahrzeug/HU-PARAMETER-MATRIX-2026-10-16.md`

---

## Kurzfassung

| | |
|--|--|
| **P0-Vorhersage `8 + 4×240 + 56`** | **widerlegt** (als exakte Sequenz) |
| **Beobachtete Full-File-Sequenz** | **`240,240,32,240,240,32`** (= **1024** Blöcke) — mehrfach reproduziert |
| **CBW-Obergrenze** | **240 Blöcke** bestätigt (kein >240 in gültigen Captures) |
| **LIVE am Ohr** | selten: **~5 s Ton+Bild** bzw. **~5–6 s Ton** nach sauberem OTG (ohne Weiß) |
| **Blocker** | Panic/weiße LED bei physischem OTG; Host-Cursor stuck / Underrun nach kurzem Fenster |

**Ein Satz:** 512 KiB-Slot wird als `4×240+2×32` gelesen (nicht `8+4×240+56`); hörbares LIVE bleibt ein kurzes Post-Replug-Fenster, oft gekillt durch Panic oder Host-Underrun.

---

## Vorhersage vs. Messung

| Claim | Ergebnis | Beleg |
|-------|----------|-------|
| Max READ = 240 Blöcke | **ja** | Histogramme `mess-cmds-*.json` — max 240 |
| Sequenz `8 + 4×240 + 56` | **nein** | nie beobachtet |
| Sequenz `240×4 + 32×2` (=1024) | **ja** | `mess-cmds-bob-led`, `gelb`, `TIP-BAYERN`; `analysis-bob-led.json` |
| Ton korreliert mit erstem großen READ | **unklar** | Tonfenster oft ohne Capture (zu spät); Full-File-READ ohne Ohr häufig |

---

## Was gelaufen ist (Chronik, gekürzt)

| Zeit (ca.) | Ereignis | Klasse / Serial | Ohr / Capture |
|------------|----------|-----------------|---------------|
| 16:04 | Start NBT, FW 0.4.52 mess | A · PD0261… | Tippen oft ohne Ton; Cache/Autoplay |
| 16:10–18 | Viele Tips (Bayern/BOB/Rock), OTG weiß↔gelb | gemischt B/A | Stream/Play kann armieren ohne Ton; Panic-Kette |
| ~16:18 | OTG raus/rein → **Ton+Bild ~5 s** | A-ähnlich · PD0266 (Panic-History) | Capture zu spät; danach Host≫Abs, Underruns |
| 16:19 | Autoplay → Rock Antenne Bayern | A · PD0266 | LED blinkt; Host stuck bei 4096 |
| 16:20 | OTG → **weiß** | **B** · PD0267→PD0268 | Abort |
| 16:21–22 | Tip ohne Weiß / RST | A · PD0272→**PD0273** `power_on` | kein Ton; Stream ohne Play |
| 16:23–24 | Tip Rock → OTG ohne Weiß → **Ton ~5–6 s** | A · **PD0274** `power_on` | Host-Cursor-Sprung ~3 s; Capture late |
| 16:25 | Tip Bayern (`fav1`) | A · PD0274 | **Full-File `4×240+2×32`**; kein Ton vor OTG |
| 16:26 | OTG → **weiß** | **B** · PD0275→…→PD0278 | Panic-Kaskade |
| 16:27–29 | Viele Replug/Tips | gemischt · endet PD0282 | Tip ohne Arm (`play` leer, Stream aus) |
| 16:33 | **Feldende**, ESP aus | — | — |

---

## Entscheidung / Claims

| Beobachtung | ja/nein | Beleg |
|-------------|---------|-------|
| 240 = CBW-Max | **ja** | alle gültigen Captures |
| Predict-Sequenz 8+4×240+56 | **nein** | — |
| Full-File = 1024 als 240/32-Muster | **ja** | BOB/Bayern Captures |
| Stream/Play ≠ hörbarer Ton | **ja** | mehrfach Status vs. Operator |
| Kurzes LIVE nach Klasse-A-OTG | **ja** | 2× ~5–6 s (Ton+Bild / Ton Rock) |
| Weiße LED = Panic / Episode tot | **ja** | `resetReason=panic`, Serial-Sprünge |
| OTG ohne Weiß ≠ automatisch Ton | **ja** | mehrfach Stille trotz Remount |
| Capture während Tonfenster | **selten** | Fenster zu kurz / Start zu spät |

**Konsequenz (Derived, noch nicht in HU-Technical-Facts):**  
A1-ähnliche Ableitung: Host liest 512 KiB-Slots in **240er-Chunks mit 32er-Zwischenschritten**, Summe 1024 — nicht die Lab-Vorhersage `8+56`. Nächster Engpass bleibt **Transport/Panic** und **Host-Konsum des Live-Rings**, nicht Slot-Größe allein.

**Nicht jetzt:** Soft-Cycle Overnight · F0 Identity · Facts-Commit ohne Review · Ring blind vergrößern.

---

## Auswertung (Detail)

### 1. Modell: 240 bestätigt, Sequenz anders

Wiederholt (BOB LED, Gelb-nach-Weiß, Tip Bayern):

```text
240, 240, 32, 240, 240, 32   →  sum 1024
```

Das ist Full-File-Read des 512 KiB-Slots. Die hypothetische Intro `8` und Outro `56` traten in diesem Feld **nicht** auf.

### 2. LIVE = kurzes Post-Replug-Fenster

Zwei Operator-Treffer am Nachmittag:

1. ~5 s **Ton+Bild** (nach OTG; danach Underrun, `play` leer)  
2. ~5–6 s **Ton** nach Tip Rock + OTG ohne Weiß (`PD0274` / `power_on`)

Muster wie am Morgen (~6 s): Host liest kurz, dann Cursor stuck / Underruns hoch, Abs kann weiterlaufen.

### 3. Tip kann Full-File ohne Ohr

Tip Bayern auf `PD0274`: Capture `TIP-BAYERN` = exakt 1024-Muster, Status kurz `Rock Antenne Bayern`/`fav1` — Operator ohne Ton bis zum (dann panischen) OTG.

### 4. Klasse A/B

Ohne weiße LED: Chance auf Ton. Mit Weiß: Panic, Serial++, Episode verwerfen. Nachmittag oft Panic-Kaskaden (mehrere Serials in Sekunden).

### 5. MessCapture-Praxis

`ram_local` ok. Tonfenster ~5 s → Capture muss **vor** Tip/OTG scharf sein; Mid-flight Start fängt Fast nur Nachlauf/Leer-CMDs.

---

## Artefakte

| Pfad | Inhalt |
|------|--------|
| dieses `ERGEBNIS.md` | Auswertung |
| `mess-cmds-bob-led.json` · `analysis-bob-led.json` | Full-File `240/32` BOB |
| `mess-cmds-gelb.json` | gleiche Sequenz nach Gelb |
| `mess-cmds-TIP-BAYERN.json` | gleiche Sequenz Tip `fav1` |
| `mess-cmds-rock-ear.json` | längerer Rock-Lauf (viele 240er, kein 1024-Muster) |
| `NOTE-TON-BILD.txt` · `NOTE-TON-ROCK.txt` | Operator Tonfenster |
| `status-*-poll.json` / `status-TON-*.json` | Live-Status |
| `status-AUTOPLAY-poll.json` · `status-MULTI-REPLUG-poll.json` | Autoplay / Endphase |
| `ota-052.sh` / Dist-Bin | Prep OTA 0.4.52 |

---

## Nächster Schritt (Vorschlag)

1. **Panic bei physischem OTG** priorisieren (sonst keine stabile Klasse A).  
2. Predict in Matrix/Facts nur als Derived: **`4×240 + 2×32`**, nicht `8+4×240+56`.  
3. Optional: Capture-Arm **vor** geplantem OTG + automatischer Stop bei `play` leer / Underrun-Spike, um Tonfenster zu erwischen.  
4. F0 / Soft-Cycle Overnight weiter hinten anstellen.
