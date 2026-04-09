"""
modules/dabfm.py - DAB+/FM kombiniert
PiDrive v0.6.1 - pygame-frei
"""
import ipc, time
from ui import Item

def build_items(screen, S, settings):
    def no_rtlsdr():
        ipc.write_progress("RTL-SDR fehlt", "DAB+/FM nicht verfuegbar", color="red")
        time.sleep(2); ipc.clear_progress()

    return [Item("DAB+/FM", action=no_rtlsdr)]
