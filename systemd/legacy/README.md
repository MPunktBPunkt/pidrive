# Legacy systemd units (TFT-Ära)

Diese Units gehören zur entfernten Display-/Launcher-Zeit (`launcher.py`,
`main_display.py`, TFT fb1). Sie werden **nicht** mehr installiert oder
aktiviert.

- `pidrive.service` — alter Monolith (→ heute `pidrive_core` + `pidrive_web` + …)
- `pidrive_display.service` — SPI-Statusanzeige (entfernt v0.10.83 / v0.11.96)

Bei Altinstallationen: `systemctl disable --now pidrive pidrive_display` und
Unit-Dateien unter `/etc/systemd/system/` löschen.
