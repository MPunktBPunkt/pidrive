# BMW-AVRCP-Probe — Ergebnis Phase (-1)

**Gemessen:** 2026-09-16 19:36  
**Mitschnitt:** `/var/log/pidrive/bmw_hb_messung_20260916_193414/bmw_probe.btsnoop` (131605 dekodierte Zeilen)  
**Auftrag:** [../auftraege/AUFTRAG-MENUE-UND-GATEWAY.md](../auftraege/AUFTRAG-MENUE-UND-GATEWAY.md) Paket G1  
**Auswertung:** `tools/bmw_avrcp_analyze.py` — Interpretationsschluessel vorab festgeschrieben

---

## Urteil

### BMW oeffnet L2CAP PSM 0x001B nicht

**Beleg:** Kein Connection Request und kein Datenverkehr auf PSM 27 (0x001b) im gesamten Mitschnitt.

**Bedeutung:** Browsing ist am NBT Evo nicht nutzbar. Ein echtes Listen-Menue faellt weg, der 3-Zeilen-Pfad bleibt Zielbild.

**Folge fuer das Gateway:** S3 gestrichen, S1 bleibt Zielbild. A17 entspannt sich.

> Ein negatives Ergebnis ist **wertvoll**, nicht enttaeuschend. Es spart im
> Gateway-Repo die Entscheidung fuer einen aufwendigen Stackwechsel.

---

## Messfragen

| ID | Frage | Ergebnis |
|----|-------|----------|
| -1.1 | Wird PSM 0x001B (Browsing) vom BMW geoeffnet? | nicht beobachtet |
| -1.2 | Kommen SetBrowsedPlayer / GetFolderItems / ChangePath? | — |
| -1.3 | SDP-Feature-Bits (59 Browsing, 60 Searching, 65 NowPlaying) | siehe Abschnitt SDP — **manuell auszuwerten** |
| -1.4 | Erscheinen Title/Artist/Album im iDrive? | **Sichtpruefung im Fahrzeug** — siehe unten |
| -1.5 | Pass-Through-Subset | — |

---

## Rohbefunde

### L2CAP-Kanaele

- Control (PSM 23 / 0x0017): nicht beobachtet
- Browsing (PSM 27 / 0x001B): nicht beobachtet

### Browse-PDUs

—

### Control-PDUs

—

---

## SDP (-1.3)

Abgelegt vom Aufnahmeskript:

- `/var/log/pidrive/bmw_hb_messung_20260916_193414/sdp/bluetoothctl_info.txt`
- `/var/log/pidrive/bmw_hb_messung_20260916_193414/sdp/bmw_browse.txt`
- `/var/log/pidrive/bmw_hb_messung_20260916_193414/sdp/local_browse.txt`

Festzuhalten ist: AVRCP-Version aus dem Profile Descriptor, der rohe
`SupportedFeatures`-Wert, und — der verlaesslichste Hinweis — ob ein
**Additional Protocol Descriptor mit AVCTP-Browsing-PSM 0x001B** vorhanden
ist. Das ist ein eindeutiges Ja/Nein und nicht von der Bitnummerierung
abhaengig.

---

## Sichtpruefung im Fahrzeug (-1.4)

Sitzung 2026-09-16 (erster Connect). Details: [BMW-ERSTER-TEST-2026-09-16.md](BMW-ERSTER-TEST-2026-09-16.md).

| Gesendet (Beispiel) | Am iDrive sichtbar? | Feld |
|----------|---------------------|------|
| `xesam:title` (Testpush / ICY) | teilweise / wechselhaft | teils „Unbekannt“, teils Titel; zwischendurch fälschlich „Spotify“ |
| `xesam:artist` | teilweise / wechselhaft | „Unbekannter Interpret“ beobachtet; Ton war z. B. RHCP |
| `xesam:album` | teilweise / wechselhaft | „Unbekanntes Album“ beobachtet |

Ursache Display-Fehler u. a. MPRIS-Priorität Spotify-Flag (Fix v0.11.141). **HB5 noch nicht voll bestanden.**  
AVRCP Pass-Through / Drehrad: **0 Events** → **-1.5 / HB6 offen.**

Ohne wiederholte, stabile drei Zeilen bleibt S1 als Produktziel gefährdet — unabhängig vom negativen Browsing-Ergebnis.

