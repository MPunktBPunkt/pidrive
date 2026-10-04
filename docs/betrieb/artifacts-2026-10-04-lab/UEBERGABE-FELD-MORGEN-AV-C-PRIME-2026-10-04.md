# Übergabe Feld morgen — C′-Retry + AV (nach Lab A+B)

**Normativ gekürzt** nach GPT-Kalibrierung · Details: [`lab88-av-mpeg-2035/KRITIK-MISTRAL-GPT-AV-AB.md`](lab88-av-mpeg-2035/KRITIK-MISTRAL-GPT-AV-AB.md) · [`MSC-AKTUELL.md`](../MSC-AKTUELL.md)

## Was steht

- **Nachlesen auslösbar:** Auto-Next (Kurzdatei → ~87 s → Cold-Body nächster Slot). Tür nur beobachten.  
- **MSC kann MPEG-Bytes liefern (Lab A+B):** Ring voll, Host-dd im Live-Fenster → Sync/ID3, `liveBytes>0`.  
- **Nicht geschlossen:** HU bekommt dieselben Bytes im Burst · hörbarer Ton.

## Doppelauftrag (getrennt)

### Lauf 1 — C′ (Seed)
`feld_q3b_next_prepare.sh` (Gate) → `feld_q3b_seed_watchdog.py` → Auto-Next, **kein RST nach Seed**.  
PASS: `bytesServed↑` + HU-Body-LBAs zeitlich korreliert.

### Lauf 2 — AV (Seed aus)
Echter Producer · Korrelation `fileOff` ↔ `absBase..absEnd` / `hostAbsCursor` · `liveBytes`/`underruns` · Fingerprint · **Ohr**.  
PASS: hörbar + Inhalt an HU-LBAs — nicht aus C′ ableiten.

**Lab 21:24 Nachzug:** außerhalb Fenster → `underruns↑`; Sync-Fingerprint allein unterscheidet Live vs. Silence-Fill **nicht**.  
Hilfsskript: `python3 tools/feld_av_correlate.py --esp http://192.168.178.89 --watch-s 90 --out <OUT>`  
Bericht: [`lab88-av-window-2124/GESAMTBERICHT-AV-WINDOW-BOUNDS.md`](lab88-av-window-2124/GESAMTBERICHT-AV-WINDOW-BOUNDS.md).

## Freeze

Ring/PSRAM/Pacing/Detect unverändert. Sequenz-GO gesperrt bis Hörtest.
