# Feld-Go Abend · 2026-10-17 ~17:51–18:06

**ESP `.89` · FW `0.4.53-dev` · Bridge `.105` · Stall aus · UART: nein**

## Ampel

| Maßnahme | Ergebnis |
|----------|----------|
| M20 Klasse-A-Repro | **PASS** (n≥3 Ton, kein Weiß) — danach wieder Panic |
| M21 Ton-Dauer | **~6–7 s** ×3 (Soll ~8 s ohne Stall) |
| M22 Play-Guess | **labil** — greift in guten Zyklen (`msPlugToPlayGuess` 17–22 s), nach Panic-Serie oft 0 |
| M24 Volume-ID only | Gate **OK** (VID rotiert, Serial gehalten) — Ordner-Erklärung **geschwächt** |
| Ordner-UI | Favoriten unter **Mediensuche** sichtbar (nicht „fehlendes DIR“) |
| Stall-Leiter (M23) | **nicht** gestartet (Guess/Stabilität unzureichend) |

## Ablauf (Operator + Status)

| Zeit | Ereignis | Telemetrie-Kern |
|------|----------|-----------------|
| 17:51 | OTG aus; M24 apply | VID `1346634033→1792252297`, Serial `PD0305` |
| 17:52 | Stecken | `power_on`, Serial→`PD0306` |
| 17:53 | Replug / Bayern-Pfad | `play=fav1`, `guess=1`, `live≈37 KiB`, Stream an |
| 17:54–55 | 3× Bayern Replug, **6–7 s Ton**, kein Weiß | Stream `fav1`, oft schon `live=0` + hohe `underruns` (nach Fenster) |
| 17:56 | **Weiße LED** | `resetReason=panic`, `PD0310`, up~37 s |
| 17:56 | Ordner-Korrektur | Favoriten in Mediensuche |
| 17:57–18:00 | Rock tip, „alle Files“, BOB | oft Panic-Boots; Prefetch/`not_from_head` |
| 18:01–18:05 | Stuck: Tonfenster nicht mehr | Serial bis `PD0324`; Rejects ohne Guess |
| 18:05 | OTG raus, **RST**, OTG rein, Rock | wieder `power_on` (`PD0325`) — Prefetch-Stuck bleibt |
| 18:06 | Session Ende | — |

## Neu gemessene / eingegrenzte Parameter

| Parameter | Feldwert | Hinweis |
|-----------|----------|---------|
| Ring `stream.cap` | **49152 B** | unverändert |
| Voller Ring | `liveAvailMs=8192` | ≈ **8,2 s** Audio → R25 bestätigt |
| Operator-Ton | **6–7 s** | Teilfüllung / Tip nach Scan |
| `msPlugToPlayGuess` | **16694 / 21467 ms** | Guess spät nach gutem Plug |
| Weiß ↔ Panic | gekoppelt | UART für Ursache offen |
| `play.reject` Stuck | `not_from_head` (prefetch), `plug_window` | kein Head-Seq → kein LIVE |
| Host first SCSI | Inquiry/Capacity ~**1000 ms**, `first_read` ~**1005 ms** | stabil hu-like |
| Soft-Serial | `PD0305`→`PD0325` | Drift auch ohne Panic (Remount/Plug) |
| M24 | VID-only Gate true | Ordner trotzdem da (Ansicht) |

## Stream ≠ Ohr

Bei den Bayern-Ton-Snapshots oft: `stream.active=true`, `playingUid=""`, `liveAvailBytes=0`, `underruns` ≫ Ring. Das Ohr hatte das Ringfenster schon gehört; Telemetrie zeigt danach Stille-Bytes. `underruns` = Bytezähler (C6), nicht Event-Count.

## Ordner / M24

- Morgen (`feld-ota-053`): „nur Dateien“ — Abend: Favoriten unter **Mediensuche**.
- M24 Volume-ID-Rotation allein erklärt/fixes die Anzeige nicht; nächster Ordner-Hebel eher **M25** (Serial/RemountGen) oder UI-Pfad dokumentieren, nicht Layout umbauen.

## Artefakte

```
status/                 17× status-*.json
m20-repro/              OPERATOR.md + 4× poll-*.jsonl
m24-volume-id/          before/after/GATE/config + ERGEBNIS
GO.md ANKUNFT.md        Prep
uart/                   leer (kein Kabel)
```

## Nächstes Feld

1. UART bei nächstem Weiß (Q11/VBUS)
2. Play-Guess stabilisieren **vor** Stall (M22→M23)
3. Weniger Replug-Sturm nach erstem Tonfenster
4. Optional M25 Serial-Bump A/B zu M24
