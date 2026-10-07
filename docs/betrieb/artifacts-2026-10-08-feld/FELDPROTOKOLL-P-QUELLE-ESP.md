# Feld morgen früh — P-Quelle (nur ESP, ~15 min)

**Datum:** 2026-10-08 · **FW:** 0.4.46-dev Freeze · **ESP:** `.89` · **kein Stick, kein Hub, kein Stall-OTA**  
**Pocket:** [`feld-s3-prep/GO.md`](feld-s3-prep/GO.md)  
**Hintergrund:** [`../artifacts-2026-10-07-feld/UEBERGABE-FELD-S2-ABEND-2026-10-07.md`](../artifacts-2026-10-07-feld/UEBERGABE-FELD-S2-ABEND-2026-10-07.md)

## Ein Satz Ziel

Wir klären **nur**, woran die HU die Wiedergabeposition **P** hängt — nicht Stall, nicht F1.

Bekannt von dir: nach Remount/RST oft **gleiche Datei** (BOB → oberstes File). Offen: **gleiche Byte-Position?**

## Literatur — kein Rad neu erfinden

NBT Evo speichert Resume **absichtlich** in der Media-Engine:

| Quelle | Aussage |
|--------|---------|
| [davidpetric.com — NBT EVO ID6 dump](https://davidpetric.com/2025/06/23/bmw-nbt-evo-id6-system-dump-analysis/) | SQLite `media.db` / `playback_sessions`: `last_track_id`, **`resume_position`**; Sync über `usbdev_sync` |
| BMW USB-Produktinfo (älter, MSC) | „When the vehicle restarts, playback **might not** resume at the point where it was interrupted.“ → Resume ist Feature, aber nicht garantiert |
| Foren (USB resume) | Nutzer erwarten Fortsetzen; Verhalten je Stick/Format/Neustart unterschiedlich |

**Was das für uns heißt:** P in der HU ist **kein Mystery-Bug**, sondern OEM-Resume. Unser „letztes Rätsel“ ist die **Bindung** für unser virtuelles FAT (welche `track_id`? Name? Größe? Volume-Serial `PDnnnn`?). Das steht in keiner Bedienungsanleitung bytegenau — deshalb ein kurzer Differenzialtest.

Wir erfinden nicht Resume neu; wir messen den **Schlüssel** für PiDrive-Slots.

---

## Was mitnehmen

- Pi (WLAN zum ESP), Handy (Video + Ton), ESP-Kabel, PD0089  
- **Kein** Stick, **kein** Hub  
- Pocket: `GO.md` auf dem Pi unter  
  `~/projects/pidrive/docs/betrieb/artifacts-2026-10-08-feld/feld-s3-prep/`

## Vorher (zu Hause, 5 min)

```bash
cd ~/projects/pidrive && git pull
chmod +x docs/betrieb/artifacts-2026-10-08-feld/feld-s3-prep/*.sh
chmod +x docs/betrieb/artifacts-2026-10-07-feld/feld-s2-prep/*.sh
# Kurz: ESP ping / Metrics
curl -s -m 3 http://192.168.178.89/api/metrics | head -c 200; echo
```

---

## Ablauf am Auto (15 min hart)

Capture wie s2 (wiederverwendet):

```bash
cd ~/projects/pidrive/docs/betrieb/artifacts-2026-10-08-feld/feld-s3-prep
# Terminal 1:
./run-s3.sh 1200
# Terminal 2 (vor jeder Bedienung):
./mark.sh "…"
```

RST (gleiche Serial):  
`curl -s -m 3 -X POST http://192.168.178.89/api/restart`

**Vor Phase 1** laut ins Video: aktuelle `serial` aus Status/Web (oder erster Poll) — z. B. PD0090.

### Minute 0–2 — Start

| Min | Aktion |
|-----|--------|
| 0 | Video: HU-Display + Uhr `watch -n0.2 date +%T.%N` |
| 1 | `./run-s3.sh 1200` · `./mark.sh "s3 start P-Quelle"` |
| 2 | Lebenszeichen: `msc.reads=` wächst |

### Phase A — Soft-RST, gleiche Serial (~4 min) · Marken `A…`

| # | Marke | Aktion | Warten |
|---|-------|--------|--------|
| A0 | `A Rock build` | **Rock** antippen | **40 s** (P aufbauen) |
| A1 | `A RST` | Soft-RST | 15 s |
| A2 | `A Rock tap` | **Rock** antippen (nicht warten auf Autoplay) | **35 s** |

**Orakel hinterher (Q8 um Marke A2):**  
`r16_resume_like` / Start≠0 → P **überlebt Soft-RST**.  
`head_like` / Start bei 0 → P durch RST gelöscht.

### Phase B — Nur Quellenwechsel, kein RST (~3 min) · `B…`

| # | Marke | Aktion | Warten |
|---|-------|--------|--------|
| B0 | `B Rock build` | Rock | 40 s |
| B1 | `B BOB tap` | BOB (dein Trick: oberstes File) | 10 s |
| B2 | `B Rock tap` | Rock wieder | 35 s |

**Orakel:** Resume → P hängt am Track über Abwahl hinweg. Kopf → Abwahl löscht P.

### Phase C — Echtes USB-Remount, Serial darf wechseln (~5 min) · `C…`  ★ Kern

| # | Marke | Aktion | Warten |
|---|-------|--------|--------|
| C0 | `C Rock build` | Rock | 40 s |
| C1 | `C unplug` | **ESP-Kabel ab** | 5 s |
| C2 | `C plug` | Kabel wieder rein | Index ~15–25 s (TUR stabil) |
| C3 | `C serial?` | laut: neue Serial? (Poll/Display) | — |
| C4 | `C Rock tap` | Rock | 35 s |

**Orakel:**

| Ergebnis A / B / C | Deutung |
|--------------------|---------|
| Resume / Resume / **Kopf** | P an **Medium/Serial-Session**; Remount = neuer Schlüssel → Stall kann nach Replug von 0 ausgehen |
| Resume / Resume / **Resume** | P an **Track-Metadaten** (Name/…), Serial egal → Stall muss P≠0 auch nach Replug |
| Kopf / … | Soft-RST löscht P — s2-Resume kam von Vorposition **vor** dem Lauf |
| Resume / **Kopf** / … | Abwahl löscht P; BOB-Trick hilft für Datei, nicht für Position |

### Minute 14–15 — Ende

`./mark.sh "s3 ende"` · Ctrl-C in Terminal 1 · Video stop.

---

## Auswertung (zu Hause / Pi, 5 min)

```bash
cd ~/projects/pidrive/docs/betrieb/artifacts-2026-10-08-feld/feld-s3-prep
RUN=$(ls -d s3-* 2>/dev/null | tail -n1)
# falls run-s3 denselben Ordner-Stil wie s2 nutzt:
# RUN=$(ls -d ../../artifacts-2026-10-07-feld/feld-s2-prep/s2-* | tail -n1)
./run-q8.sh   # siehe Skript — oder:
python3 ~/projects/pidrive/tools/feld_q8_msc_order.py \
  --reads "$RUN/msc_reads.jsonl" --trace "$RUN/trace.jsonl" --out-dir "$RUN/q8"
```

Pro Phase die Episode **nach** `A Rock tap` / `B Rock tap` / `C Rock tap` ansehen:

- `r10.verdict`, `head_like`, `pattern_kib` Präfix `F16 B120…` vs. Kopf-360  
- Serial vor/nach Phase C aus `status-poll.jsonl` (`serial`-Feld)

Ergebnis in eine Zeile `ERGEBNIS.md` im Lauf-Ordner schreiben (Tabelle A/B/C).

---

## Was wir bewusst nicht tun

- Kein Stick / F1-Video  
- Kein Stall-OTA  
- Keine Dateinamen-Änderung am ESP (dafür später Lab-Build oder einmalige FW-Geometrie)  
- Bei Zeitnot: **nur Phase C** + eine von A/B — C ist die neue Information

## Danach (nicht im Auto)

Wenn C = Resume bei neuer Serial → nächster Schritt **Name/Größe** ändern (Lab oder spezieller Build).  
Wenn C = Kopf → P ist medium-gebunden; Stall-Start nach Replug = Offset 0 ist OK, in-Session P≠0 bleibt (A/B).
