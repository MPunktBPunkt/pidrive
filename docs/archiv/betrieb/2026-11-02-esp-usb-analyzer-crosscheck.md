# Betriebshinweis: USB-Gadget Cross-Check (esp32.pidrive × usb-analyzer)

**Datum:** 2026-11-02  
**Scope:** Lab-Ergebnisse am **ESP-USB-MSC-Pfad** (nicht BT/AVRCP).

Der ausführliche Bug-/Messbericht liegt im ESP-Repo:

→ **[esp32.pidrive `docs/lab/USB-ANALYZER-CROSSCHECK.md`](https://github.com/MPunktBPunkt/esp32.pidrive/blob/main/docs/lab/USB-ANALYZER-CROSSCHECK.md)**

## Kurz für PiDrive-Betrieb

| Thema | Ergebnis |
|-------|----------|
| Instrumentierung MSC | **Nicht blind** — Analyzer-Host-Stimulus und Gadget-Counter matchen (byte-exact) |
| Telemetrie-Bugs am ESP | `imageBytes` falsch bei L3 · HTTP `version` 0.0.0 · USB-Produktstring = Espressif-Default |
| ID3 im Idle | nur minimal (`TSSE`); Cover/TIT2 brauchen aktiven Stream |
| BMW-ähnlicher Lab-Host | verfügbar über usb-analyzer `bmw-hu-stimulus` — ergänzt NBT-Replay / Feld |

**Nicht claimed:** echte NBT-Evo-FACTS aus diesem Lab-Lauf.

Gegenstück AOA/MSC-Sonde: [hu-probe Bericht](https://github.com/MPunktBPunkt/hu-probe/blob/main/docs/feld/USB-ANALYZER-CROSSCHECK.md).
