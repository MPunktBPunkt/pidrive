# Lab triage nach Claude-Review · 2026-10-17

## Claude-Claims geprüft

| Claim | Urteil | Beleg |
|-------|--------|-------|
| B5 „4 KiB Live = HU-Architektur“ zu stark | **Zustimmung** | `mscTrace.n=4096` = Callback (E5/R15); CBW-Architektur = E11 (`blocks` 8/240). Matrix: **nicht** als HU-Lesearchitektur führen |
| fav1@16465 beweist Favoriten-Struktur nicht allein | **Zustimmung** | LBA seit ≥06.10. belegt |
| Aber: NBT las neue DIR-Cluster | **Neu aus mess.json** | LBA **65** (Favoriten cl2) + **73** (Menue cl3) + Root 33 — `feld-mess-dir-hits.json` |
| Stall war schon am NBT (s6/~65 s) | **Zustimmung** | R29; kein „erster Stall“ |
| playGuess=0 → Stall-Arm prüfen vor Leiter | **Zustimmung** | R30; Feld `playGuessCount=0` |
| resetReason power_on nach software | **Zustimmung** | OTG-Poll `software` → Bayern `power_on`; `plugCount=2`/`unplugCount=1` → **Replug dazwischen** |
| underruns = Bytezähler | **Zustimmung + FW** | `StreamBuffer::readAt` → `underruns_++` **pro fehlendem Live-Byte**; 732404 ≈ 1,4×524288 |
| Ordner = NBT-Cache / konstante BPB-ID | **Hypothese testbar** | Lab: `fatVolumeId` 1346634188→**1358003479**, Serial PD0489 gehalten; SG_IO BPB vid match |

## Lab ausgeführt

1. `stallEnable=false` erzwungen (Rest von Vollleiter: armed/timeouts Historie)
2. Volume-ID-Rotation via `/api/config` + `media_remount keepIdentity`
3. SG_IO LBA0: BPB vid = 1358003479 ✓
4. DIR-Hits aus Feld-`mess.json` nachgezogen

## Maßnahmen (Priorität)

Siehe `MASSNAHMEN-NACH-TRI-REVIEW-2026-10-17.md` und Feld-Übergabe.
