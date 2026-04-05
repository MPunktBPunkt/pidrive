"""
modules/dabfm.py - DAB+ / FM Radio Modul (Platzhalter)
PiDrive Project - GPL-v3

Status: In Planung
Moegliche Hardware:
  - DAB+: Nooelec NESDR, RTL-SDR + welle.io
  - FM: RTL-SDR, PiFM
"""

import time
from ui import Item, show_message, C_ORANGE

def build_items(screen, S, settings):
    """Gibt DAB+/FM-Untermenue-Items zurueck."""

    def show_info():
        show_message(screen, "DAB+ / FM",
                     "Noch nicht verfuegbar", color=C_ORANGE)
        time.sleep(2)

    def dab_action():
        show_message(screen, "DAB+",
                     "Hardware wird unterstuetzt:", color=C_ORANGE)
        time.sleep(1)
        show_message(screen, "DAB+",
                     "RTL-SDR + welle.io", color=C_ORANGE)
        time.sleep(2)

    def fm_action():
        show_message(screen, "FM Radio",
                     "RTL-SDR Empfaenger noetig", color=C_ORANGE)
        time.sleep(2)

    items = [
        Item("DAB+ Radio",
             sub="In Planung",
             action=dab_action),
        Item("FM Radio",
             sub="In Planung",
             action=fm_action),
        Item("Info",
             sub="RTL-SDR Hardware",
             action=show_info),
    ]
    return items
