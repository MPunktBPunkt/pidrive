# Feldbericht — Q3b Auto-Next nach RST — 17:38–17:55 · PD0060

**FW:** `0.4.45-dev` · Prefill Seed **B** ab LBA 761 · SoftAP  
**Artefakt:** `docs/betrieb/artifacts-2026-10-04-feld/feld-q3b-next-1738/`  
**Commit:** `7cb0205` (Artifacts); dieser Bericht nach Rohspur-Nachprüfung korrigiert

---

## Ampel

| Prüfpunkt | Status | Beleg |
|-----------|--------|-------|
| Feld-Oracle B (HU Body-LBAs) | **PASS** | LED Prefetch; JSONL: Spans über LBA 761 (u.a. 609–825, exakt 761); `cold` 1→8; 10× `cold_body_burst` |
| Feld-Oracle C' (Seed an MSC) | **FAIL** | `bytesServed` blieb **0**; Seed schon bei GO tot |
| LED / Auto-Next | **PASS** (Read-Indikator) | BOB→Bayern, Bayern→Rock; Tür ~17:55 — **kein Inhaltsnachweis** |
| Detect Cold | nur Log | `play.reject` / `cold_body_burst`, `not_from_head` |
| AV / Ohr | **FAIL** | kein Ton — erwartbar solange Seed≠MP3 / kein MPEG hinter HU-LBAs |

---

## Zeitlinie (korrigiert)

1. **17:38:35** Seed B aktiv (`status-02-seeded`: `active=True`, `bytesServed=0`, **uptime 5min 53s**, `cold=6`)  
2. **17:38:39** `status-03-go`: **`active=False`**, `cold=1`, **uptime 3s**, `phase=scan` → ESP war zwischen Seed und GO **neu gestartet**; RAM-Seed weg  
3. **17:38:39+** Poll: `seedB=0` dauerhaft; ab 17:39:05 fav2 BOB  
4. **17:39–17:42** BOB→Bayern ohne Seed; Bayern-Ende ohne LED (Warm/Cache **Hypothese**, nicht bewiesen)  
5. **17:43–17:44** Operator RST (zweimal) — Seed war **bereits** tot; RST verhindert nur ein Re-Seed  
6. **17:45–17:47** BOB→Bayern→Rock mit LED; `cold`→6; Seed 0  
7. **17:48** Feld-Ende: kein Ton  
8. **17:55** Tür → LED; `cold` 6→8; Diag `cold_body_burst lba=97..153` (Ursache nicht isoliert)

---

## Deutung

1. **C'-FAIL ist Verfahrens-/Gate-Fehler, kein Widerspruch zu 17:32.** SoftAP-Seed ist RAM-only. Entscheidend: Seed starb **~4 s nach Arming** (Reboot), nicht erst durch den Operator-RST 17:43. Der Mistral/GPT-Text, der C′ nur auf RST 17:43/44 zurückführt, ist **unvollständig**.  
2. **17:32 bleibt der positive C'-Beleg** (`bytesServed` ≈ 8 MiB) für die konkrete Konfiguration — nicht pauschal „C′ geschlossen“.  
3. **Oracle B hält** als Read-Evidenz (LED/Cold/JSONL inkl. 761). LED/Cold sagen **nichts** über gültige Audio-Bytes.  
4. **`bytesServed` ≠ SoftAP-8 KiB-Datei:** FW füllt alle MSC-Reads mit `fileOff ≥ fromOff` mit Seed-Muster; 8 MiB bei 17:32 sind wiederholte/große Body-Reads, nicht die 8 KiB-Stichprobe `softap_B_lba761.bin`.  
5. **AV:** hörbar nur wenn gültiges MPEG in den **tatsächlich gelesenen** LBAs liegt und ausgeliefert wird (Stufen A→D), nicht „nur Producer anwerfen“.

---

## Maßnahmen (verbindlich)

1. **Gate vor GO:** `active=True` + `uptime` nicht gerade resettet; sonst **ABORT** und neu seed­en.  
2. **Seed-Watchdog** bis Burst: bei `active→False` oder Uptime-Sprung sofort abbrechen / melden.  
3. **Prozedur:** letzte RST → Seed → Gate → Auto-Next **ohne** weiteren RST/USB/Remount.  
4. **C'-Wiederholung** erst mit Gate+Watchdog; PASS nur `bytesServed↑` **und** zeitlich passende HU-Body-LBAs.  
5. **AV separat** nach A→D (Inhalt an HU-LBAs); Freeze/Detect unverändert bis Hörbeweis.  
6. Reboot 17:38:35→39 klären (manuell vs. Crash) — optional, blockiert C'-Retry nicht, wenn Gate greift.

---

## Freeze

Ring/PSRAM/Pacing/Detect-Policy unverändert. Sequenz-GO gesperrt bis hörbarer AV-Nachweis.
