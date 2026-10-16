# Qualifikation HU-Probe / Soft-Cycle — 2026-10-16

## Status

Die Implementierungs- und Offline-Verträge sind geprüft. Ein Hardware-, Lab-
oder Fahrzeug-PASS wird nicht behauptet.

## Durchgeführte Prüfungen

- IDE-Diagnostik aller geänderten HU-Probe-, ESP-Firmware-, PiDrive- und
  Technology-Audit-Dateien: keine Fehler.
- Source-Review der TinyUSB-Callbacks: kein Netzwerk, JSON oder dynamische
  Allokation im Callback.
- Selection-Barrier-Review:
  - vor Payload-Erzeugung,
  - Produktionsdefault `false`,
  - begrenzter Timeout,
  - `audio_start` erhält die Barrier bei gleicher UID,
  - erfolgreicher Release bewaffnet Scope-1-Pacing,
  - expliziter Stop, Remount und Plug-Wechsel bleiben Kill-Pfade.
- Capture-Vertrag:
  - `ram_local` hält TCP/PUMP für Live-Audio aktiv,
  - `ram_wifi_off` ist ausschließlich Transport-Baseline ohne Live-Audio,
  - rekonstruierte READ10-Kommandos sind `synthesized`,
  - `complete=false` bei Ring-Overflow,
  - paginierter Export und Hard-Stop bei unvollständigem Capture.
- Orchestrator-Vertrag und Dry-run-Pfade wurden durch Code- und Testreview
  gegen die Firmware-API abgeglichen.

## Nicht ausführbar in dieser Umgebung

- Python/pytest: kein funktionsfähiger Python-Interpreter installiert.
- PlatformIO-Build: `pio`/PlatformIO nicht installiert.
- Lab-ESP `.88` und Feld-ESP `.89`: HTTP-Timeout.
- Proxmox-Debian `192.168.178.108`: SSH-Timeout.

Damit bleiben folgende Gates offen:

- Firmware-Kompilierung für `pidrive-s3-mess` 0.4.52-dev,
- ausführbarer Orchestrator-Dry-run,
- 100 Soft-Cycles ohne Reset,
- sechs Wiederholungen je Identity-Dimension,
- echter BMW-Lauf mit vollständigem `ram_local`-Capture.

## Verbindliche Fortsetzung

Die Kommandos, PASS-Kriterien, Stopregeln und Artefakte stehen in
[`SOFT-CYCLE-AUTOTEST-RUNBOOK.md`](../SOFT-CYCLE-AUTOTEST-RUNBOOK.md).
Vor Autoeinsatz müssen Build, Dry-run und Lab-Overnight dort vollständig grün
sein. Fehlende lokale Infrastruktur darf nicht als Produkt- oder Messfehler
klassifiziert werden.
