# Spike: TinyUSB READ10 — Rückgabe 0 und Teilantwort

**Stand:** 2026-10-06 · Code-Lesung, keine FW-Änderung · Bezug: Risiko R5 in [ANALYSE-HU-FILE-CACHE-BACKPRESSURE-2026-10-06.md](../artifacts-2026-10-06-feld/ANALYSE-HU-FILE-CACHE-BACKPRESSURE-2026-10-06.md), Stufe 2a in [Stufenplan.md](../../planung/Stufenplan.md)

## Ergebnis in einem Satz

TinyUSB unterstützt beides ohne Blockade: **Rückgabe 0** ruft den Callback mit derselben LBA erneut auf (Busy-Retry über die Event-Queue). Eine **Teilantwort** wird gesendet und der Rest mit fortgeschriebener LBA/Offset nachgefordert. Es gibt **keinen geräteseitigen Timeout**. Zwei Fallen gibt es: die CPU-Last des Retry-Loops und kurze USB-Pakete bei Teilantworten.

## Quelle

Upstream `hathach/tinyusb`, `src/class/msc/msc_device.c`, Tags 0.12.0, 0.13.0, 0.14.0, 0.15.0. Die relevante Logik ist in allen vier Versionen identisch. arduino-esp32 2.0.x (Plattform `espressif32@6.4.0`) baut auf Espressifs TinyUSB-Fork aus diesem Zeitraum auf.

Gelesener Ausschnitt (0.15.0, `proc_read10_cmd`):

```c
// remaining bytes capped at class buffer
int32_t nbytes = (int32_t) tu_min32(sizeof(_mscd_buf), p_cbw->total_bytes-p_msc->xferred_len);

// Application can consume smaller bytes
uint32_t const offset = p_msc->xferred_len % block_sz;
nbytes = tud_msc_read10_cb(p_cbw->lun, lba, offset, _mscd_buf, (uint32_t) nbytes);

if ( nbytes < 0 )
{
  // negative means error -> endpoint is stalled & status in CSW set to failed
  set_sense_medium_not_present(p_cbw->lun);
  fail_scsi_op(rhport, p_msc, MSC_CSW_STATUS_FAILED);
}
else if ( nbytes == 0 )
{
  // zero means not ready -> simulate an transfer complete so that this driver callback will fired again
  dcd_event_xfer_complete(rhport, p_msc->ep_in, 0, XFER_RESULT_SUCCESS, false);
}
else
{
  TU_ASSERT( usbd_edpt_xfer(rhport, p_msc->ep_in, _mscd_buf, (uint16_t) nbytes), );
}
```

Und in `mscd_xfer_cb`, `MSC_STAGE_DATA`:

```c
if (SCSI_CMD_READ_10 == p_cbw->command[0])
{
  p_msc->xferred_len += xferred_bytes;
  if ( p_msc->xferred_len >= p_msc->total_len ) p_msc->stage = MSC_STAGE_STATUS;
  else proc_read10_cmd(rhport, p_msc);
}
```

## Bewertung je Variante

| Rückgabe | Verhalten TinyUSB | Folge für uns | Status |
|---|---|---|---|
| `< 0` | Endpoint-Stall, CSW FAILED, Sense „medium not present“ | Die HU sieht einen Medienfehler. **Nie für Live-Lücken verwenden.** | [B] Code |
| `0` | Ein Fake-„xfer complete“ mit 0 Bytes kommt in die Event-Queue. `tud_task` ruft `proc_read10_cmd` sofort wieder auf, mit **gleicher LBA und gleichem Offset**. | Echtes „not ready“, kein Blockieren des Callbacks, EP0 (Control, BOT-Reset) bleibt bedienbar. **Aber:** ohne Pause ein Busy-Loop im USB-Task. | [B] Code |
| `0 < n < angefordert` | `n` Bytes werden gesendet. Danach ruft TinyUSB mit `lba + xferred/512` und `offset = xferred % 512` erneut auf. | Teilantwort möglich. Der Callback muss `offset ≠ 0` korrekt behandeln (der Live-Pfad tut das über `fileOff`). | [B] Code |
| `= angefordert` | normal | heutiges Verhalten | [B] |

Geräteseitig gibt es keinen Timeout: TinyUSB wartet beliebig lange. Die Grenze setzt allein der Host (bei der HU unbekannt: R1). Gibt der Host auf, kommt typischerweise ein **Bulk-Only Mass Storage Reset** (Class-Request auf EP0) oder ein USB-Bus-Reset. Beides setzt die MSC-Stage zurück.

## Die zwei Fallen

### Falle 1: Busy-Loop bei Rückgabe 0
Ein `return 0` ohne Pause lässt den USB-Task in einer Schleife laufen: Event, Callback, Event, Callback. Läuft der USB-Task mit hoher Priorität auf demselben Kern wie der TCP- oder WiFi-Empfang, der den Ring füllt, **verhungert genau der Producer, auf den wir warten**. Das wäre ein Deadlock bis zum Host-Timeout.

**Regel:** Vor jedem `return 0` kurz abgeben, z. B. `vTaskDelay(pdMS_TO_TICKS(2))`. Bei einem Stall von 700 ms sind das ~350 Aufrufe, das ist unkritisch.
Zu prüfen auf dem Gerät: Priorität und Core-Affinität des USB-Tasks in `esp32-hal-tinyusb.c` gegenüber dem PumpServer- und lwIP-Task.

### Falle 2: Kurze Pakete bei Teilantworten
Der ESP32-S3 läuft als **USB Full-Speed** mit 64 B Bulk-Max-Packet-Size. Ist `n` kein Vielfaches von 64, endet der IN-Transfer mit einem Short Packet. Viele Hosts werten das als **Ende der Datenphase**: Residue, CSW-Fehler oder Phase Error.

**Regel:** Teilantworten nur in **Vielfachen von 512 B** (Sektor, und damit auch Vielfaches von 64). Weniger als 512 B verfügbar heißt `return 0` statt Teilantwort.

## Konsequenz für den Stall-Adapter (Stufe 3)

1. **WAIT = `return 0` mit 2 ms Pause.** Blockieren im Callback (Variante C) ist überflüssig, weil `return 0` dasselbe ohne Task-Blockade leistet.
2. **Teilantwort = verfügbare Bytes, abgerundet auf 512.** So rinnt der Ring kontinuierlich ab, statt auf volle 4 KiB zu warten. Bei 48k bedeutet das 512 B ≈ 85 ms Audio statt 0,68 s Wartezeit.
3. **Timeout in der Firmware** (`stall_ms`), weil TinyUSB keinen hat. Danach gibt es Stille für den Rest des Requests, der Cursor bleibt stehen.
4. Der Timeout-Zähler gehört zum **Request**: Er wird bei einer neuen CBW zurückgesetzt, erkennbar an `lba`/`offset`, die nicht zur Fortsetzung passen.

## Noch auf dem Debian-Container zu verifizieren (5 Minuten, nur lesen)

Der Arduino-Wrapper ließ sich hier nicht nachladen. Auf dem Container mit installiertem PlatformIO:

```bash
P=~/.platformio/packages/framework-arduinoespressif32
grep -n "read10_cb\|return" $P/cores/esp32/USBMSC.cpp | head -40      # Rückgabe wird 1:1 durchgereicht?
grep -n "xTaskCreate\|usb_device_task" $P/cores/esp32/esp32-hal-tinyusb.c  # Priorität / Core
grep -rn "CFG_TUD_MSC_EP_BUFSIZE\|CFG_TUD_MSC_BUFSIZE" $P/tools/sdk/esp32s3/include/arduino_tinyusb/  # 4096?
```

Erwartung: `tud_msc_read10_cb` reicht den `int32_t` unseres `pidrive_msc_read` unverändert durch, und der Klassenpuffer ist 4096 B (passt zu `if (bufsize > 4096)` in `UsbMscGadget::onRead`). Weicht eines davon ab, muss Stufe 3 angepasst werden.

## Lab-Nachweis (Teil von Stufe 4)

Ein Lab-Build mit `stall_ms` fest auf 1000 und leerem Ring. SG_IO-READ10 mit `timeout = 5000`:
- Erwartet: `SgIoHdr.duration` ≈ 1000 ms, Daten = Stille, Status OK.
- Mit Producer: Dauer = Zeit bis 512 B im Ring, Daten = Live.
- Mit `timeout = 500` im SG_IO: Linux bricht ab und sendet einen BOT-Reset. Danach muss das Gerät ohne Re-Enumeration weiter antworten.
