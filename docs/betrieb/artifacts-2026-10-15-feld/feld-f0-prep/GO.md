# Feld F0 — Pocket · ~20–30 min

**FW: `0.4.51-dev` · `stallEnable=false` · kein Stall-Tuning**  
Ziel: Identity vs Prefetch-Cache vs Play-Intent **diskriminieren** (nicht „Ton erzwingen“).

Kanonisch: [`../UEBERGABE-F0-NAECHSTE-KI-2026-10-15.md`](../UEBERGABE-F0-NAECHSTE-KI-2026-10-15.md)

```bash
cd ~/pidrive/docs/betrieb/artifacts-2026-10-15-feld/feld-f0-prep
./f0-check.sh before
# Nach OTA-Smoke:
./run-f0.sh poll 900    # Terminal 1
# Terminal 2:
./mark.sh "F0 start B0 control"
./f0-identity.sh status
```

### Pre-Gates (Abort wenn nein)

| Check | Soll |
|-------|------|
| `version` | `0.4.51-dev` (oder ≥ mit fatVolumeId/Remount) |
| `stall_enable` | `false` |
| OTG Klasse **A** | keine weiße LED, Serial/Uptime stabil |
| Smoke | Menü + eine Head-Station hörbar |

### Läufe (Reihenfolge fest)

| ID | Aktion | Isolation |
|----|--------|-----------|
| **B0** | P≫0 aufspielen → OTG Replug **ohne** Identity-Wechsel | Kontrolle |
| **B1** | nur **serial** rotieren (`./f0-identity.sh serial`) → Replug/Remount-Effekt | Diff nur Serial+Rev |
| **B2** | nur **label** (`./f0-identity.sh label`) | Diff nur Labels |
| **B3** | nur **volume-id** (`./f0-identity.sh volume-id`) | Diff nur Volume-ID |

Pro Lauf: `./f0-check.sh before-<id>` → Aktion → `./mark.sh "…"` → Ohr + `./f0-check.sh after-<id>` → `./f0-identity.sh verify` wenn Rotation.

### Pflicht mitschreiben (nicht nur Ohr)

- Identity vor/nach (`bpbVolumeId` / `bpbLabel` / `rootLabel` / `usbSerial`)  
- Reads: keine / Mid / Head / Full  
- `playingUid` / `play.guess` / LIVE-Bytes  
- Hörbar? (ja/nein + was: Live vs Silence)  
- Klasse A/B  

### Nicht

- Dimensionen mischen · Identity + Head-Force · Stall an · Episode B auswerten · D1 starten
