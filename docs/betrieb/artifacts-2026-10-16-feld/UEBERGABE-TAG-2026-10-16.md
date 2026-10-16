# Übergabe · Tag 2026-10-16 (Lab + Feld NBT)

**ESP Lab `.88` / Feld `.89` · FW `0.4.52-dev` mess · stall off**  
**Feldende:** ~16:33 · ESP im Auto aus

---

## Ein Satz

Lab Soft-Cycle ist grün (Matrix + Soft-USB 10/10); am NBT ist die 512‑KiB-Vorhersage `8+4×240+56` **widerlegt** zugunsten von **`4×240+2×32`**, während hörbares LIVE nur ~5–6 s nach Klasse‑A‑OTG kommt und Panic/weiße LED weiter blockiert.

---

## Lab (vormittag/mittag) — `.88`

| Gate | Ergebnis | Artefakt |
|------|----------|----------|
| Build + OTA 0.4.52-dev | ☑ | `lab-soft-cycle-052/ota/` |
| Soft-USB Identity-Fix (FW) | ☑ (esp32.pidrive) | Lab-ERGEBNIS |
| Quiet-Gate `play`/`scan` | ☑ | `tools/soft_cycle_orchestrator.py` |
| Soft-USB Zelle | PASS | `matrix-soft-usb-ramlocal-02` |
| Vollmatrix 5 Zellen | **PASS** | `matrix-full-03` |
| Soft-USB Kurz-Kampagne | **10/10 PASS → Stopp** | `overnight-soft-usb/` |

**Capture:** `ram_local` (+ `--no-live-audio` im Lab). `ram_wifi_off` + Soft-USB → 409.

Details: [`../artifacts-2026-10-16-lab/lab-soft-cycle-052/ERGEBNIS.md`](../artifacts-2026-10-16-lab/lab-soft-cycle-052/ERGEBNIS.md)

---

## Feld P0 · 512 KiB MessCapture — `.89`

| Claim | Ergebnis |
|-------|----------|
| Max CBW = 240 Blöcke | **bestätigt** |
| Sequenz `8 + 4×240 + 56` | **widerlegt** |
| Sequenz `240,240,32,240,240,32` (=1024) | **mehrfach bestätigt** (BOB, Gelb, Tip Bayern) |
| LIVE Ohr | **2×** ~5–6 s (Ton+Bild / Ton Rock) nach OTG ohne Weiß |
| Panic / weiße LED | häufig; Episode tot; Serial-Kette `PD0261`→`PD0282` |
| Stream/Play ≠ Ton | ja (Host stuck / Underruns) |

Details: [`feld-512kib-predict-01/ERGEBNIS.md`](feld-512kib-predict-01/ERGEBNIS.md)  
Prep: [`../artifacts-2026-10-16-lab/P0-512KIB-MODELLTEST.md`](../artifacts-2026-10-16-lab/P0-512KIB-MODELLTEST.md)

---

## Priorität jetzt

1. **Panic bei physischem HU-OTG** (Klasse A stabilisieren) — Soft-Cycle umgeht das nur im Lab.  
2. Matrix/Facts: Ableitung Full-File **`4×240 + 2×32`** (Derived → Richtung [S]); **nicht** weiter `8+56` als Vorhersage führen.  
3. Optional: Capture **vor** Tip/OTG scharf + Auto-Stop am Tonfenster (~5 s).  
4. **Hinten:** Soft-Cycle Overnight-100 · Orchestrator-Ausbau · F0 Identity · Ring blind vergrößern · FM-TX GPIO4.

Siehe auch: [`../artifacts-2026-10-16-lab/lab-soft-cycle-052/PRIORITAET-SHIFT.md`](../artifacts-2026-10-16-lab/lab-soft-cycle-052/PRIORITAET-SHIFT.md) (aktualisiert nach Feld).

---

## Repo-Änderungen in diesem Push

| Pfad | Inhalt |
|------|--------|
| `tools/soft_cycle_orchestrator.py` | Quiet-Gate erlaubt `play`/`scan` ohne Stream |
| `docs/betrieb/artifacts-2026-10-16-lab/` | Soft-Cycle + P0-Prep |
| `docs/betrieb/artifacts-2026-10-16-feld/` | P0-Feld + dieses Übergabe-Dokument |
| `docs/fahrzeug/HU-PARAMETER-MATRIX-2026-10-16.md` | Feld-Nachtrag zur 512‑KiB-Sequenz |

**Hinweis:** Soft-USB `armSoftUsbKeepIdentity` liegt in **esp32.pidrive** (separates Repo) — dort ggf. separat committen/pushen.
