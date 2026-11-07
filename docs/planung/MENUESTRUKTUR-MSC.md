# MSC-Menüstruktur — finales Zielbild

**Status:** Normativ (Zielbild) · **Stand:** 2026-10-24  
**Bezug:** [MSC-AKTUELL](../betrieb/MSC-AKTUELL.md) · [HU-Technical-Facts](../fahrzeug/HU-Technical-Facts.md) (R37–R45) · [Maßnahmen 23.10.](MASSNAHMEN-MSC-FULLMENU.md) · Interim v1: [FELDTEST §3.10](../archiv/betrieb/FELDTEST-ESP-MSC-BMW-2026-09-28.md#310-zielbild-v1-review-konsens-2026-09-30--bmw-robustes-msc-menü)

Kein Firmware-Auftrag. Play-Slot-MiB final erst nach Größenleiter (P0).

---

## 1. Korrekturen (häufige Missverständnisse)

| Annahme | Präzisierung |
|---------|----------------|
| Neue/gescannnte Sender erst nach OTG-Remount | Nach **USB-Cycle** (Firmware D+ oder physisches OTG). Soft-Remount / NOT READY **wirkt nicht** (R37). |
| Nicht-bereit → Stall | Stall = **Body-Bremse** am getippten Play-Slot, nachdem der Head steht. Nicht: fehlenden Dir-Eintrag vortäuschen oder Browse bremsen. |
| Live neue Dateien einfügen | **Nein.** Pi baut Snapshot → ESP patched stabile Slots → Cycle → HU sieht neue Namen. |

---

## 2. Produktmodell

```text
PiDrive (Gehirn)
  ├── menu_set Snapshot  →  esp32.pidrive  →  USB-Cycle D+  →  HU Dir/Browse
  └── MP3-Frames live    →  esp32.pidrive  →  READ10 Head, dann Body
                                                    │
                                    Body ready? ───┼── ja → Live / Silence
                                                   └── nein → BUSY Stall nur Body
```

Drei Schichten (HU):

1. **Navigator/Browse** — Ordner + 8.3; ändert sich nur bei Snapshot + Cycle.
2. **Player-Metadaten** — ID3 im festen Head (~80 KiB); Body darf später kommen.
3. **Audio** — dynamischer Body hinter fester Size; Stall nur hier.

Hochvolatiles (Scan-Fortschritt, SNR, „suche…“) **nicht** als wachsende Dateiliste — WebUI oder ID3-Text in einem festen Steuer-/Status-Slot.

**Vertrag (Kurzformel):** kleines, stabiles FAT-Menü + wenige Play-Rollen mit immer gültigem Kopf; dynamisch nur der Audio-Körper hinter fester Size. Browse aus Dir, Player aus ID3.

---

## 3. Zielbaum

Eine Root-Seite: ein Play-Anker + Quellordner + Steuer. Tiefe 1–2. Pro Ordner ≤32 sichtbare MP3s (FULLMENU-Kappe). Überlauf = nächste Seite per Steuer-Stub (`NEXT.MP3` → neuer Snapshot + Cycle) — keine Soft-Paging-Illusion in einer Mount-Epoche.

```text
/
├── 0ZULETZT.MP3          Play-Slot: letzter Hörkontext (Resume-Anker)
├── FAVORIT/              gemischte Favoriten (DAB/FM/Stream/…)
├── DAB/                  DAB+-Ensemble-Ausschnitt (Seite N)
├── FM/                   FM-Presets / Scan-Ergebnis-Seite
├── MP3/                  aktuelle Playlist / Ordner-Ausschnitt (keine Vollbibliothek)
├── SCANNER/              Scanner-Kanäle als Slots
├── AIRBAND/              Airband-Kanäle
└── STEUER/               Stub-MP3s: Stop, Scan, Seite+, About, …
```

**Defaults (verbindlich):**

- Root enthält **einen** Play-Anker `0ZULETZT.MP3` (Alphabet oben + Resume); weitere Play-Dateien nur unter Quellordnern.
- Nach Scan/Übernehmen: Pi published Snapshot und löst **automatisch USB-Cycle** aus; physisches OTG nur Fallback.
- MP3 = **gecappte Playlist/Ordnerseite**, kein Spiegel der gesamten Library auf dem Stick.

---

## 4. Slot-Rollen

| Rolle | Beispiele | Geometrie | Inhalt |
|-------|-----------|-----------|--------|
| Play | `0ZULETZT`, `DAB/01….MP3`, `FAVORIT/…` | feste Size; Head ≥~80 KiB immer gültig; Body groß genug für Live (MiB → Größenleiter P0) | Live oder Silence; ID3 = Anzeigename |
| Nav/Steuer | `STEUER/SCAN.MP3`, `NEXT.MP3`, `STOP.MP3` | gleiche Slot-Größe ok (heute 160 KiB); Body kurz/still | Tip → Pump-Action; ID3 = Menütext |
| Leer/Reserve | ungenutzte Indizes | Dir stabil oder ausgeblendet über Snapshot-Seite | nie ad-hoc Cluster umbauen |

Directory-Namen, Größen, Cluster **ändern sich nicht** wegen Inhaltswechsel — nur Body und ggf. ID3-Bytes in festen Offsets. 8.3 für Browse, ID3 für Player.

---

## 5. Quellentypen

| Quelle | Regel |
|--------|--------|
| **DAB+ / FM** | Favoriten + aktuelle Scan-Seite als feste Dateien. Scan auf dem Pi; Ergebnis erst im nächsten Snapshot. Während Scan: Steuer-ID3 „Scan…“ oder WebUI — keine neuen Root-Dateien mid-flight. |
| **MP3-Files** | `MP3/` max. eine Seite (≤~30); Weiter = `STEUER/NEXT` + Cycle. Aktueller Titel zusätzlich in `0ZULETZT`. |
| **Scanner / Airband** | Ein Kanal = eine Play-Datei. Aktiv = einer der Play-Bodies live; Rest Silence + gültiger Head. |
| **Steuerfiles** | Echte MP3s mit gültigem Head (kein leerer Platzhalter). Actions: Stop, Scan, Seite±, Quelle, About. |

---

## 6. Ready-Semantik (Stall)

```text
Tap Play-Slot
  → Head sofort lieferbar (ID3 „Sendername“ / „lädt…“)
  → Body: Producer ≥ 1 CBW Vorlauf → Live
  → sonst Stall (BUSY) nur auf Body-Reads dieses Slots
  → Browse/FAT weiter schnell (kein globaler Stall)
```

Nicht-bereit **ohne** Tip: Slot darf in der Liste stehen (Silence + ID3) oder erst in der nächsten Snapshot-Seite erscheinen — nicht per Stall „verstecken“. Stall während Browse kann die Menü-UI ~20 s träge machen (R35) — deshalb Stall nicht als Menü-Lock missbrauchen.

---

## 7. Bewusst nicht final

- Beliebig wachsende Dateiliste = PiDrive-Library auf dem Stick  
- Soft-Remount als Menü-Update  
- Identity/Serial als Cache-Breaker  
- Stall als allgemeiner Menü-Lock  
- Soft-Paging (≤4 + Mehr…) als Produktmodell — abgelöst durch FULLMENU + Snapshot-Seiten  

**Historisch:** [FELDTEST §3.10](../archiv/betrieb/FELDTEST-ESP-MSC-BMW-2026-09-28.md#310-zielbild-v1-review-konsens-2026-09-30--bmw-robustes-msc-menü) = Interim v1 (Soft-Paging, ≤4 Slots). Dieses Dokument ersetzt es als Zielbild.
