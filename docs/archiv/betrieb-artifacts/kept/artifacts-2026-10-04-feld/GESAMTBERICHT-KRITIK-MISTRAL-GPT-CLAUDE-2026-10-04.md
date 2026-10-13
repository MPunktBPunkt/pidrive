# Gesamtbericht (kritisch): Feld 2026-10-04 + Mistral/GPT/Claude + Lab-Nachweis

**Für die nächste KI.** Normativer Kurz-Einstieg: [`../MSC-AKTUELL.md`](../MSC-AKTUELL.md).  
**Rohdaten:** dieses Verzeichnis · Offline-P1: [`P1-OFFLINE-REGRADE-2026-10-04.json`](P1-OFFLINE-REGRADE-2026-10-04.json) · Lab: [`../artifacts-2026-10-04-lab/lab88-av-stream-1400/`](../artifacts-2026-10-04-lab/lab88-av-stream-1400/)  
**Basis-Commit vor diesem Bericht:** `89232ff` · FW `0.4.42-dev` · Bridge `--msc-lock`

---

## 0. Urteil in einem Absatz

P0 bleibt Feld-PASS. **P1 ist nicht „nicht messbar“** — die Traces zeigen zweimal dasselbe kalte fav0-Body-Burst-Muster ~87 s nach Kurzdatei-Aktivität (Lauf B Burst1 **+0,35 s** zum Nominalende). Voll-GRÜN für P1 fehlt weiter (schwache Startuhr, kein Ohr). **`bufferMs=0` ist tote Telemetrie** (FW schreibt den Wert nie) — Mistral/früherer Feldbericht haben das überbewertet. Der echte AV-Befund bei PD0058: **`streamBytes == underruns` → 0 Live-Bytes**. LED korreliert mit MSC-Bursts, nicht mit Live-AV. Nächster Engpass: **welche Daten die HU im Cold-Body-Burst liest (Q3b/Prefill)** und **warum Detect den Burst verpasst / Warm-Head falsch triggert** — nicht Ring/PSRAM, nicht bufferMs-Jagd.

---

## 1. Bewertung der drei Analysen

| Aussage | Mistral | GPT | Claude | **Diese Auswertung** |
|---------|---------|-----|--------|----------------------|
| P0 PASS | ✓ | ✓ | ✓ | **Übernehmen** |
| P1 „nicht messbar“ | zu streng | „offen/nicht negativ“ | **Widerlegt durch Traces** | **Claude im Kern richtig** → `P1_BODY_NEXT_EVIDENCED`, Timing **PASS_WEAK** |
| bufferMs=0 = zentrale Blockade / Host liest nicht | zu stark | Messwert≠Ursache | Symptom (Cache) | **Alle unvollständig:** Wert ist **tot im Code**; echte Metrik = underruns |
| LED = MSC, ≠ AV | ✓ vorsichtig | ✓ | ✓ + Burst-Korrelation | **Übernehmen**; Minuten-LED ≈ Auto-Next-~87 s-Burst |
| PD0058 Detect OK, AV FAIL | ✓ | ✓ 4 Zustände | Detect falsch getriggert | **GPT-Trennung + Claude-Detect-Kritik + underruns=sb** |
| Freeze halten | ✓ | ✓ | ✓ | **Übernehmen** |
| Als Nächstes nur Lab-AV-Buffer | 1. Priorität | Instrumentierung zuerst | Prefill/Q3b zuerst | **Hybrid:** Dead-bufferMs dokumentiert; dann **Prefill/Q3b + Detect-Muster**, nicht Buffer-Refactor |

---

## 2. Verifizierte P1-Offline-Auswertung

Nominal: 512 KiB @ 48 kbit/s = **87,381 s**. Scan-Kopf fav0 ≈ **380 928 B** → Body ab ~LBA **753** kalt.

| Lauf | Anchor (fav1-Touch) | fav0 Burst1 (n_sum=484, ~1,98 MiB, lba0=1953) | fav0 Burst2 (n_sum=1479, ~5,8 MiB) |
|------|---------------------|-----------------------------------------------|-----------------------------------|
| A PD0056 | 10:50:38.602 | 10:51:58.799 · Δ=**80,20 s** (−7,18) | 10:52:05.864 · Δ=**87,26 s** (−0,12) |
| B PD0057 | 10:54:51.242 | 10:56:18.974 · Δ=**87,73 s** (**+0,35**) | 10:56:26.057 · Δ=94,82 s (+7,43) |

- Muster **identisch** (484 → ~5 s Pause → 1479).  
- **B Burst1 liegt im ±1,5 s-Fenster** zum Nominalende.  
- Preflight: fav0 nur Kopf warm → Body-Next war **kalt** im Sinne der LBA-Frage.  
- **Caveats:** Anchor ≠ `play_uid`/UI-Film; kein Hörbeweis; `p1-run-b/msc_reads.jsonl` enthält Session-A-Reste → nur zeitgefensterte Analyse.

**Ampel P1:** nicht ROT, nicht voll GRÜN → **PASS_WEAK / Evidenz für kalten Body-Next**, Timing bedingt belastbar.

**LED:** User „stark bei Wechsel zu Rock“ = diese Bursts; BOB 11:06 ohne neue Reads = kein LED — passt.

---

## 3. AV / Detect — korrigierte Metriken

### 3.1 `bufferMs` (Code + Lab)

- `App::bufferMs` nur Init=0 + JSON-Export; **keine Writer** im Tree.  
- Lab `lab/play fav1` + ffmpeg: StreamBuffer `size` 6 KiB→**48 KiB voll**, `underruns=0`, **`bufferMs` dauerhaft 0**.  
→ **Nicht** als Fehlerursache jagen; Telemetrie ggf. später an `stream.size`/Bitrate anbinden oder entfernen.

### 3.2 PD0058 (echtes AV-Versagen)

| Zustand | Wert |
|---------|------|
| `play_uid` / `audio_start` / ffmpeg / `audio_ack` | ja |
| User Ton/Bild | nein |
| fav1 Snapshot | `streamBytes=311296`, `underruns=311296` → **live≈0** |

Detect kann auf Warm-Head/`seq_short` feuern, während der **echte Cold-Body-Burst** (P1) als `not_from_head` verworfen wird — Claude hier richtig.

### 3.3 Architektur-Konsequenz

Menü-Lock ≠ AV. Cold-Body-Next existiert. Overlay liefert im Detect-Fall oft **Silence (underrun)**. Sequenz mit **Kopf-Freeze (~0,33–0,5 MiB) + Body-Vorbefüllung** bleibt ein ernsthafter Kandidat (Plan-Geometrie), aber **Q3b (Ton A/B im Body)** fehlt.

---

## 4. Verbindliche Entscheidungsregeln (aktualisiert)

```
P0 Feld PASS → halten
P1 Body-Next: EVIDENCED (PASS_WEAK) — nicht „unmeasurable“
P1 voll GRÜN: erst mit belastbarer Startuhr + ideal Ohr/Q3b
bufferMs: ignorieren (dead)
AV-Metrik: streamBytes vs underruns (+ stream.size)
Detect: nicht blind lockern; Cold-Body-Burst zuerst loggen
Freeze Ring/PSRAM/Pacing: halten
BT-Hybrid: Fallback, keine Lösungserzählung
Sequenz-GO: noch nein — aber nicht mehr wegen „HU liest nie kalt“
```

---

## 5. Arbeitsauftrag nächste KI (Priorität)

1. **Q3b Lab:** Body-Region fav0 mit bekanntem Inhalt A vorbefüllen / nach Scan auf B ändern; Host-Burst wie Feld (ab ~LBA 1953); Oracle — wird B gelesen? (ersetzt blindes bufferMs-Debug)  
2. **Detect-Diagnose:** PD0056/57 Burst vs PD0058 Warm-Touch — `evaluatePlay`-Bedingungen dokumentieren; optional **nur Log** „cold_body_burst“.  
3. **Feld mit Ohr/Film:** Kurzdatei → warten auf ~87 s Rock-Burst; UI-Timer mitfilmen; Prefill-Inhalt hörbar?  
4. **Telemetrie:** `bufferMs` nicht als KPI; Status um live_bytes=`streamBytes-underruns` ergänzen (optional, kleines Diff).  
5. Q3a Oracle parallel; Freeze halten.

---

## 6. Lesereihenfolge

1. [`../MSC-AKTUELL.md`](../MSC-AKTUELL.md)  
2. Dieser Bericht  
3. [`P1-OFFLINE-REGRADE-2026-10-04.json`](P1-OFFLINE-REGRADE-2026-10-04.json)  
4. [`FELD-ERGEBNIS-2026-10-04.md`](FELD-ERGEBNIS-2026-10-04.md) (historische Ampel — P1-Zeile überholt)  
5. [`otg-1058/`](otg-1058/) · [`p1-run-a/`](p1-run-a/) · [`p1-run-b/`](p1-run-b/)  
6. [`../artifacts-2026-10-04-lab/lab88-av-stream-1400/`](../artifacts-2026-10-04-lab/lab88-av-stream-1400/)  
7. Plan Rev.5 · Semantik-Doc  

---

## 7. Fazit

Der Feldtag hat **mehr** geliefert als der erste Kurzbericht: reproduzierbares kaltes Auto-Next-Body-Muster + LED-Korrelation + Detect/AV-Entkopplung. Der größte Methodenfehler war, **`bufferMs=0` als Kernblockade** und **P1 als unmessbar** zu führen. Die Architekturfrage verschiebt sich zu **Inhalt des Cold-Bursts (Prefill/Q3b)** und **Detect-Trigger**, nicht zu Menü oder Ring-Größe.
