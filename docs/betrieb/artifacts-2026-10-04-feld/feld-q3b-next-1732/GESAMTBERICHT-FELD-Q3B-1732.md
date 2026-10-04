# Feldbericht — Q3b Seed-over-Live — 17:32–17:35 · PD0060

**FW:** `0.4.45-dev` · Prefill Seed **B** ab LBA 761 · nach RST  
**Artefakt:** `docs/betrieb/artifacts-2026-10-04-feld/feld-q3b-next-1732/`

---

## Ampel

| Prüfpunkt | Status | Beleg |
|-----------|--------|-------|
| Feld-Oracle B (HU Body-LBAs) | **PASS** | Trace 17:34:30–42; has761+has1953; ~body unique 15552 |
| Feld-Oracle C' (Seed an MSC) | **PASS** | `bytesServed` 0 → **8 040 448** während Rock-Burst |
| LED / Auto-Next | **PASS** | Operator: LED vor und beim Wechsel zu Rock ~17:34 |
| Detect Cold | Log `not_from_head` | unverändert; Play über Head/`audio.start fav0` |
| AV / Ohr | **FAIL** | Operator: kein Ton |

---

## Zeitlinie

1. 17:32 RST → Prepare Seed B, `bytesServed=0`  
2. 17:33 Bayern (fav1) Kurztrack  
3. **17:34:31** Wechsel fav0 Rock; LED aktiv  
4. 17:34:31–42 dichter fav0-Body-Read; Seed-Zähler steigt auf ~8 MiB  
5. 17:35 Ohr: **kein Ton**

---

## Deutung

1. **Architekturfrage Prefill/Datenfrische:** beantwortet — HU fordert Body an, ESP liefert mit `0.4.45` die Seed-Bytes **auch bei aktivem Live-Overlay**.  
2. **Hörbarkeit:** Seed-Muster `Q3B1…` ist **kein MPEG** → kein Ton erwartbar und bestätigt.  
3. **Nächster Engpass:** echter **Producer/AV-Pfad** (gültiges MP3 in den von der HU gelesenen LBAs bzw. Ring mit `liveBytes>0` und Cursor im Fenster) — nicht Detect-Policy, nicht Prefill-Geometrie.

Vorgänger 16:53 (`feld-q3b-1653`): Oracle C blockiert durch Live-Maskierung → mit 0.4.45 behoben für Seed-Diagnose.

---

## Freeze

Ring/PSRAM/Pacing/Detect-Policy unverändert. Seed-Override nur bei aktivem `body_seed`. Sequenz-GO weiter gesperrt bis hörbarer AV-Nachweis mit echtem Audio.
