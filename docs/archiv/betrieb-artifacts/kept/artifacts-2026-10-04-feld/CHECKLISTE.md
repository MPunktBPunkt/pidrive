# Feldcheckliste P0 + P1 — heute mitnehmen

**Einstieg Docs:** [`MSC-AKTUELL.md`](MSC-AKTUELL.md)  
**Ziel:** P0-Feld-Provokation → Unplug → P1 kalter Auto-Next ×2  
**FW:** `0.4.42-dev` L3 · **kein** Downgrade / kein OTA nötig für P0  
**Bridge:** `.105` → `.89:9090` · `--msc-lock` an  
**Audio:** `--no-audio` ok für Read-only; optional später Ton

**Artefakt-Ziel:** `docs/betrieb/artifacts-2026-10-04-feld/`

---

## A. Vor dem Losfahren (Zuhause / Hof)

- [ ] Pi `.105` erreichbar, `systemctl is-active pidrive_pump_bridge` = active  
- [ ] Bridge-Log zeigt Retry oder (wenn `.89` schon da) `hello_ack`  
- [ ] Phone/Laptop auf Heim-LAN oder Hotspot mit Zugriff auf `.89` / `.105`  
- [ ] Diese Checkliste + Notizblock / Uhr sichtbar  
- [ ] **Nicht** `feld_prepare_homecoming.sh` laufen lassen (OTA auf 0.4.36!)

### Sobald Zündung / ESP `.89` WLAN hat

```bash
# Laptop (DebianCursor oder Pi-SSH)
curl -sS http://192.168.178.89/api/status | python3 -m json.tool | head -40
# Erwartung: version 0.4.42-dev, pumpTcpUp bald true
ssh pidrive@192.168.178.105 'echo pidrive | sudo -S journalctl -u pidrive_pump_bridge -n 20 --no-pager'
```

- [ ] FW = `0.4.42-dev` (sonst **stop** und OTA L3, nicht 0.4.36)  
- [ ] Bridge: `hello_ack` + ideal `MSC_MAP_FROZEN` mit Rock/Bayern/BOB  
- [ ] Traces leer starten: auf Pi `/tmp/pidrive_msc_reads.jsonl` + `msc_lock.jsonl` truncate

---

## B. PHASE 1 — P0 Feld-Provokation (~5 min)

**Eigene USB-Session. Danach Unplug.**

1. Bridge up **vor** USB-Plug.  
2. USB stecken → Scan abwarten → Favoriten sichtbar (Rock/Bayern/BOB).  
3. Status sichern: `curl …/api/menu` + `…/api/status` → `p0-before.json`.  
4. Am Pi: Menü bewusst weg von Favoriten (Einstellungen / Zurueck-Pfad) — wie im Lab.  
5. Nochmal `api/menu` → muss **Rock/Bayern/BOB** bleiben (nicht Zurueck/Ausgang).  
6. Bridge-Log: `frozen_reject` erwarten.  
7. EAR notieren + Dateien nach `artifacts-2026-10-04-feld/p0-provokation/`.  
8. **USB trennen. Warten bis unplugged.** Session zu Ende.

**PASS:** Namen/UID stabil + Reject geloggt.  
**FAIL:** Menü wird überschrieben → P1 nicht starten, Lock prüfen.

---

## C. PHASE 2 — P1 Durchlauf A (kalt, passiv)

**Neue Session. Kein manueller Next aufs Ziel.**

1. Bridge noch up. Neue Serial erwarten (PDxxxx↑).  
2. USB stecken → **kompletten Scan** abwarten → quiet.  
3. **Preflight** (sofort nach Scan, vor Play):

```bash
curl -sS http://192.168.178.89/api/status -o status-preflight.json
# pro Slot: name, uid, lba0, lba1, bytes
# kalt = wenig/keine Body-Reads auf Ziel-Slot seit Scan (Trace mitlesen)
```

4. EAR-Zeilen (maschinenlesbar mitschreiben):

```
preflight.warmth.fav0 = {bytes, cold, lba0, lba1}
preflight.warmth.fav1 = …
preflight.warmth.fav2 = …
p1.nominal_end_s =   # kurze Datei ~87 s bei 512 KiB @48k
```

5. **Nur eine kurze Datei starten** (512 KiB / Bayern-Slot) — andere unberührt.  
6. **Keine** Bedienung bis Trackende + Auto-Next.  
7. Beobachten: liest kaltes Ziel? Wann relativ zum Ende (±1,5 s)?  
8. Status-Snaps: nach Select, ~Ende, nach Auto-Next (+10 s).  
9. Session sichern: `pidrive_msc_reads.jsonl`, status-*.json, EAR, Bridge-Tail → `p1-run-a/`.

**Erfolg (vorläufig):** Body-Reads kaltes Ziel, Umfang ≈ Dateigröße, Start in ±1,5 s, ov=0, TCP up, Preflight kalt belegt.

---

## D. PHASE 2 — P1 Durchlauf B

1. USB raus. Kurz warten.  
2. Traces auf Pi truncate (oder neuer Dateiname/Ordner).  
3. Komplett wie Durchlauf A (neue Serial, neuer Preflight).  
4. Artefakte → `p1-run-b/`.  
5. Erst **beide** Läufe werten (×2).

---

## E. Nach dem Auto (Zuhause)

```bash
# von Pi holen
mkdir -p docs/betrieb/artifacts-2026-10-04-feld
scp -r pidrive@192.168.178.105:/tmp/pidrive_msc_reads.jsonl \
  pidrive@192.168.178.105:/tmp/pidrive_msc_lock.jsonl \
  docs/betrieb/artifacts-2026-10-04-feld/
# status-JSONs / EAR vom Laptop dazu
```

- [ ] Commit + Push Artefakte  
- [ ] Auswertung A–E + boolesche Erfolgskriterien (nicht Klasse B = „grün“)

---

## Nicht tun

- Ring/PSRAM/Pacing/OTA während der Messung  
- P0 und P1 in **einer** USB-Session  
- Kaltstand nur aus `slotMap.bytes==0`  
- Manueller Select aufs Auto-Next-Ziel  
- `feld_prepare_homecoming.sh` (OTA 0.4.36)  
- Zweites Status-Poll-Chaos parallel zur Bridge
