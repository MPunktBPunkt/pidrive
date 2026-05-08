"""modules/radio — Radio/RF-Subsystem (DAB, FM, Scanner, RTL-SDR, Spectrum)
Proxy-Modul: importiert alle Radio-Komponenten aus der flachen modules/-Ebene.
Neue Importe können modules.radio statt modules.dab_* nutzen.
"""
from modules.radio_impl import (  # noqa: F401,F403
    dab, dab_helpers, dab_play, dab_scan, dab_dls,
    fm, scanner, spectrum, rtlsdr, webradio,
)
