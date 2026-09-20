# Boot-Beschleunigung (Pi + PiDrive)

**Stand:** 2026-09-20 · gemessen auf `192.168.178.105`

## Vorher (typisch)

| Phase | Dauer |
|-------|-------|
| Kernel | ~5 s |
| Userspace bis graphical | **~2 min 40 s** |
| Davon `systemd-networkd-wait-online` | **~2 min** (Timeout, Failure) |
| Davon `pidrive-wifi-recover` `sleep 30` | **30 s** (auch wenn WLAN schon ok) |
| `pidrive_core` Start | erst danach |

Ursache: NetworkManager managed WLAN, aber `systemd-networkd-wait-online` bleibt enabled und hält `network-online.target`. `pidrive_core` wartete darauf.

## Maßnahmen (Repo)

1. **`systemd-networkd-wait-online` maskieren**, wenn NetworkManager aktiv (`install.sh`)
2. **`pidrive_core` / pump*:** `After=network.target` statt `network-online`
3. **wifi-recover:** kein festes `sleep 30`; schneller Boot-Check + Timer nach 45 s
4. **cloud-init** auf Car-Pi deaktivieren (Firstboot-Reste)
5. Raspotify nicht mehr an `network-online` / networkd-wait koppeln



## Runde 2 (Core früher)

6. **`After=multi-user.target` am Core entfernen** — sonst startet Core erst nach fast allen multi-user-Diensten
7. **Raspotify `OnFailure=` Crash-Report** abkoppeln / Generator maskieren
8. **NM-wait-online Timeout** auf 5 s (Drop-in)
9. **pump*** Units auf dem Pi auf `network.target` bringen (Repo war schon so)

## Nach Deploy am Pi

```bash
cd ~/pidrive && git pull
# Units + Maskierung (oder install.sh Abschnitt erneut)
sudo cp systemd/pidrive_core.service /etc/systemd/system/
sudo cp systemd/pidrive-wifi-recover.service /etc/systemd/system/
sudo cp systemd/pidrive-wifi-recover.timer /etc/systemd/system/
sudo systemctl disable --now systemd-networkd-wait-online.service
sudo systemctl mask systemd-networkd-wait-online.service
sudo systemctl daemon-reload
sudo systemctl restart pidrive_core
sudo systemctl enable --now pidrive-wifi-recover.timer
sudo reboot
# danach:
systemd-analyze
systemd-analyze blame | head -15
```

## Nachher (gemessen 2026-09-20, gleicher Pi)

| Phase | Dauer |
|-------|-------|
| Kernel + Userspace | **~24 s** (vorher ~2 min 45 s) |
| graphical.target | ~19 s |
| `pidrive_web` | früh aktiv (HTTP 200) |
| `pidrive_core` | ~1 s in blame |

Noch sichtbar (~10 s): `NetworkManager-wait-online`, `raspotify-crash-report-generator` — unkritisch für Core/Web.
