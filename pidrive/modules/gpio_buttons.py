"""
modules/gpio_buttons.py — GPIO-Tasten am Joy-IT RB-TFT3.5 Display (v0.8.19)

Hardware: Joy-IT RB-TFT3.5, Raspberry Pi 3B
  Key1 = GPIO23 (Pin 16) → scroll up / Menü hoch
  Key2 = GPIO24 (Pin 18) → enter / Auswahl bestätigen
  Key3 = GPIO25 (Pin 22) → back / zurück

Schreibt File-Trigger nach /tmp/pidrive_cmd — identisch zu WebUI/AVRCP.
Graceful Fallback wenn RPi.GPIO nicht installiert (z.B. im Entwicklungsmodus).

Debounce: 200ms — verhindert Mehrfachauslösung bei einem Tastendruck.
"""

import os
import time
import threading
import log

CMD_FILE   = "/tmp/pidrive_cmd"
DEBOUNCE_S = 0.20   # 200ms Entprellung

# GPIO-Belegung laut Joy-IT RB-TFT3.5 Pinout
KEY1_GPIO = 23   # up
KEY2_GPIO = 24   # enter
KEY3_GPIO = 25   # back

_gpio_ok   = False
_thread    = None
_stop_flag = False

# Mapping GPIO → Trigger-Befehl
_KEY_MAP = {
    KEY1_GPIO: "up",
    KEY2_GPIO: "enter",
    KEY3_GPIO: "back",
}


def _write_cmd(cmd: str):
    try:
        with open(CMD_FILE, "w") as f:
            f.write(cmd.strip() + "\n")
    except Exception as e:
        log.error(f"GPIO: write_cmd({cmd}): {e}")


def _gpio_loop():
    """
    Polling-Loop für GPIO-Tastenstatus.
    Wird in eigenem Daemon-Thread gestartet.
    Polling statt Interrupts wegen GPIO-Konflikten mit SPI-Display.
    """
    global _stop_flag
    import RPi.GPIO as GPIO

    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)

    for pin in _KEY_MAP:
        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        # SPI-Display nutzt GPIO24/25 für DC/Reset — nur als Input konfigurieren

    last_press = {pin: 0.0 for pin in _KEY_MAP}
    last_state = {pin: True for pin in _KEY_MAP}   # True = nicht gedrückt (pull-up)

    log.info(f"GPIO: Loop gestartet (Key1=GPIO{KEY1_GPIO}→up, Key2=GPIO{KEY2_GPIO}→enter, Key3=GPIO{KEY3_GPIO}→back)")

    try:
        while not _stop_flag:
            now = time.time()
            for pin, cmd in _KEY_MAP.items():
                try:
                    state = GPIO.input(pin)   # False = gedrückt (active-low mit pull-up)
                    pressed = (state == GPIO.LOW)

                    if pressed and not last_state[pin]:
                        # Flanke: nicht-gedrückt → gedrückt
                        if (now - last_press[pin]) >= DEBOUNCE_S:
                            last_press[pin] = now
                            log.info(f"GPIO: KEY GPIO{pin} → {cmd}")
                            _write_cmd(cmd)
                    last_state[pin] = pressed
                except Exception as e:
                    log.warn(f"GPIO: read GPIO{pin}: {e}")

            time.sleep(0.05)   # 50ms Polling-Intervall
    finally:
        try:
            GPIO.cleanup()
        except Exception:
            pass
        log.info("GPIO: Loop beendet")


def start() -> bool:
    """
    GPIO-Button-Thread starten.
    Gibt True zurück wenn GPIO verfügbar, False wenn nicht (z.B. kein RPi.GPIO).
    """
    global _gpio_ok, _thread, _stop_flag

    try:
        import RPi.GPIO  # noqa: F401 — nur Import-Test
        _gpio_ok = True
    except ImportError:
        log.warn("GPIO: RPi.GPIO nicht installiert — Tasten deaktiviert")
        log.warn("GPIO: Installation: pip3 install RPi.GPIO --break-system-packages")
        return False
    except RuntimeError as e:
        log.warn(f"GPIO: RuntimeError (kein Raspberry Pi?): {e}")
        return False

    _stop_flag = False
    _thread = threading.Thread(target=_gpio_loop, daemon=True, name="gpio_buttons")
    _thread.start()
    return True


def stop():
    global _stop_flag
    _stop_flag = True
    if _thread:
        _thread.join(timeout=2.0)


def is_active() -> bool:
    return _gpio_ok and _thread is not None and _thread.is_alive()
