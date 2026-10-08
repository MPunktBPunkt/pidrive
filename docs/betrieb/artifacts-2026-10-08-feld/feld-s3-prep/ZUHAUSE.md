# Zu Hause — s3 (P-Quelle, nur ESP) · 2026-10-08

- [x] Protokoll + Lab auf `main` (`d2e128a` · morgen-Brief mit Review-Präzisierungen)
- [x] `chmod +x …/feld-s3-prep/*.sh` (lokal ok)
- [x] Lab Pump/Bridge: **grün bis SoftAP** — Nacht + Morgen + Marker/BOB
- [x] Bridge-Fix `esp32.pidrive` `698e607` (reconnect nur HTTP) — L1-Retest PASS
- [ ] **Feld-Pi:** `git pull` (pidrive → aktueller HEAD)
- [ ] **Feld-Pi:** Bridge sync  
      `sudo cp ~/projects/esphub/esp32.pidrive/tools/pump_bridge.py /home/pidrive/pump_bridge.py`  
      (nach `git pull` in esp32.pidrive; s3 ist `--no-audio`, Fix trotzdem mitnehmen)
- [ ] ESP `.89` an: `curl -s -m 3 http://192.168.178.89/api/metrics | head -c 120`
- [ ] Pocket: `GO.md` — Zeitnot **C > A > B**
- [ ] Packen: **Pi · Handy · ESP-Kabel · PD0089** — **kein** Stick, **kein** Hub

**Ziel:** P-Suchraum eingrenzen (nicht Stall). Freeze unverändert.  
**Lab `.88`:** Lieferkette ok — ersetzt den Auto-Lauf nicht.
