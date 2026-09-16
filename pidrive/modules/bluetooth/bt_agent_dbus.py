#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bt_agent_dbus.py — PiDrive BlueZ-Pairing-Agent über D-Bus

Ersetzt die bluetoothctl-Sitzung aus bt_agent.py. Der Unterschied ist nicht
kosmetisch:

  bluetoothctl-Agent (alt)           D-Bus-Agent (hier)
  ─────────────────────────────      ────────────────────────────────────────
  antwortet nur, wenn der Pi         antwortet richtungsunabhängig — auch
  das Pairing beginnt                wenn der BMW es beginnt
  liest eine Pipe mit readline()     wird von bluetoothd direkt aufgerufen
  hängt an Eingabeaufforderungen     kennt keine Eingabeaufforderungen
  ohne Zeilenumbruch
  Sichtbarkeit läuft nach 180 s ab   DiscoverableTimeout = 0

Warum das der eigentliche Fehler war: BlueZ fragt beim Pairing einen
registrierten Agenten. Ohne Agent bricht das Pairing ab. Die alte Lösung
registrierte über `bluetoothctl` einen Agenten, dessen Antworten aber nur
innerhalb von `pair_with_agent()` gelesen wurden — also nur beim
Pi-initiierten Pairing. Beginnt der BMW, landete die Rückfrage in einer
Pipe, die niemand ausliest.

Betrieb:
    Eigener Dienst, absichtlich getrennt vom Kern:
      - überlebt Kern-Neustarts, das Pairing-Fenster bleibt offen
      - läuft, bevor der Kern bereit ist
      - berührt die GLib-Hauptschleife von mpris2.py nicht

    Dieses Modul kommt bewusst ohne Projektimporte aus und wird als
    Skriptpfad gestartet, nicht mit "-m". Grund: modules/bluetooth/__init__.py
    zieht über "from modules.bluetooth.bluetooth import *" das gesamte
    Subsystem herein und braucht die Importumgebung des Kerns.

    Aus .../pidrive/pidrive :
      Vordergrund:   sudo python3 modules/bluetooth/bt_agent_dbus.py -f
      ohne BlueZ:    python3 modules/bluetooth/bt_agent_dbus.py --selftest

Bestätigungsverfahren (BMW nutzt Numeric Comparison):
    always  — jede Anfrage bestätigen (Vorgabe; entspricht dem Verhalten,
              das die alte Lösung anstrebte, und kann beim ersten
              Kopplungsversuch nicht aus Regelgründen scheitern)
    window  — nur innerhalb eines offenen Fensters bestätigen, sonst ablehnen
    never   — nie bestätigen (nur zum Messen, was der BMW überhaupt fragt)

    Fenster öffnen:  pidrivectl bt pair-window 300
    Datei:           /tmp/pidrive_bt_pair_window  (Ablauf als Epoch-Sekunden)
"""

from __future__ import annotations

import json
import os
import sys
import time

# Pfade spiegeln bt_helpers.py. Absichtlich hier doppelt: dieser Dienst muss
# starten können, bevor der Kern und dessen Importpfade bereit sind.
AGENT_STATE_FILE  = "/tmp/pidrive_bt_agent.json"
AGENT_EVENTS_FILE = "/tmp/pidrive_bt_agent_events.json"
PAIR_WINDOW_FILE  = "/tmp/pidrive_bt_pair_window"
AGENT_LOG         = "/var/log/pidrive/bt_agent.log"

AGENT_PATH   = "/org/pidrive/btagent"
CAPABILITY   = "DisplayYesNo"      # → BMW-Numeric-Comparison wird RequestConfirmation
EVENTS_MAX   = 200

# Dienste, die ohne Rückfrage erlaubt werden. Alles andere folgt der Regel.
# A2DP Source/Sink, AVRCP Target/Controller, AVDTP, AVCTP, GAP/GATT-Basis.
AUDIO_UUIDS = {
    "0000110a-0000-1000-8000-00805f9b34fb",  # AudioSource
    "0000110b-0000-1000-8000-00805f9b34fb",  # AudioSink
    "0000110c-0000-1000-8000-00805f9b34fb",  # A/V RemoteControlTarget
    "0000110d-0000-1000-8000-00805f9b34fb",  # AdvancedAudioDistribution
    "0000110e-0000-1000-8000-00805f9b34fb",  # A/V RemoteControl
    "0000110f-0000-1000-8000-00805f9b34fb",  # A/V RemoteControlController
    "00000019-0000-1000-8000-00805f9b34fb",  # AVDTP
    "00000017-0000-1000-8000-00805f9b34fb",  # AVCTP
}


# ── Protokoll ────────────────────────────────────────────────────────────────

def _log(msg: str) -> None:
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    try:
        os.makedirs(os.path.dirname(AGENT_LOG), exist_ok=True)
        with open(AGENT_LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass
    try:
        print(line, file=sys.stderr, flush=True)
    except Exception:
        pass


def _write_json_atomic(path: str, data: dict) -> None:
    try:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        os.replace(tmp, path)
    except Exception:
        pass


def _read_json(path: str, default: dict) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


# ── Bestätigungsregel ────────────────────────────────────────────────────────

def pair_window_remaining(now: float | None = None) -> float:
    """Restlaufzeit des Pairing-Fensters in Sekunden, 0 wenn geschlossen."""
    now = time.time() if now is None else now
    try:
        with open(PAIR_WINDOW_FILE, "r", encoding="utf-8") as f:
            until = float(f.read().strip())
    except Exception:
        return 0.0
    return max(0.0, until - now)


def open_pair_window(seconds: int = 300) -> float:
    until = time.time() + max(1, int(seconds))
    try:
        with open(PAIR_WINDOW_FILE, "w", encoding="utf-8") as f:
            f.write(str(until))
    except Exception:
        return 0.0
    return until


def decide_confirm(mode: str, window_s: float, paired_before: bool) -> tuple[bool, str]:
    """
    Reine Funktion — ohne D-Bus prüfbar.

    Rückgabe: (bestätigen, Begründung). Die Begründung landet im Protokoll,
    damit im Fahrzeug nachvollziehbar ist, warum eine Anfrage scheiterte.
    """
    if paired_before:
        return True, "bereits gekoppelt"
    if mode == "never":
        return False, "Regel never"
    if mode == "always":
        return True, "Regel always"
    if mode == "window":
        if window_s > 0:
            return True, f"Fenster offen ({int(window_s)}s)"
        return False, "Fenster geschlossen"
    return True, f"unbekannte Regel {mode!r} — wie always behandelt"


# ── Agent ────────────────────────────────────────────────────────────────────

def _build_agent_class(dbus, dbus_service):
    """
    Agent-Klasse erst zur Laufzeit bauen. So bleibt das Modul importierbar
    und selbsttestbar, auch wenn dbus-python fehlt.
    """

    class Rejected(dbus.DBusException):
        # Ohne _dbus_error_name kommt bei BlueZ ein generischer Fehler an und
        # das Protokoll im btmon-Mitschnitt ist nicht zuzuordnen.
        _dbus_error_name = "org.bluez.Error.Rejected"

    class PiDriveAgent(dbus_service.Object):
        def __init__(self, bus, path, owner):
            super().__init__(bus, path)
            self._owner = owner

        # -- Hilfen ------------------------------------------------------------

        def _note(self, method, device="", detail="", answer="", reason=""):
            self._owner.push_event(method, device, detail, answer, reason)

        def _confirm(self, method, device, detail):
            mode   = self._owner.mode
            win    = pair_window_remaining()
            paired = self._owner.device_is_paired(device)
            ok, reason = decide_confirm(mode, win, paired)
            self._note(method, device, detail,
                       "ja" if ok else "abgelehnt", reason)
            if not ok:
                raise Rejected(reason)
            return True

        # -- org.bluez.Agent1 --------------------------------------------------

        @dbus_service.method("org.bluez.Agent1", in_signature="", out_signature="")
        def Release(self):
            self._note("Release")

        @dbus_service.method("org.bluez.Agent1", in_signature="o", out_signature="")
        def RequestAuthorization(self, device):
            self._confirm("RequestAuthorization", str(device), "")

        @dbus_service.method("org.bluez.Agent1", in_signature="ou", out_signature="")
        def RequestConfirmation(self, device, passkey):
            # Das ist der Aufruf, an dem das BMW-Pairing bisher hängen blieb.
            self._confirm("RequestConfirmation", str(device),
                          f"passkey={int(passkey):06d}")
            self._owner.trust_device(str(device))

        @dbus_service.method("org.bluez.Agent1", in_signature="os", out_signature="")
        def AuthorizeService(self, device, uuid):
            u = str(uuid).lower()
            if u in AUDIO_UUIDS:
                self._note("AuthorizeService", str(device), u, "ja", "Audiodienst")
                return
            self._confirm("AuthorizeService", str(device), u)

        @dbus_service.method("org.bluez.Agent1", in_signature="o", out_signature="u")
        def RequestPasskey(self, device):
            self._note("RequestPasskey", str(device), "", "000000",
                       "feste Vorgabe")
            return dbus.UInt32(0)

        @dbus_service.method("org.bluez.Agent1", in_signature="o", out_signature="s")
        def RequestPinCode(self, device):
            self._note("RequestPinCode", str(device), "", "0000",
                       "feste Vorgabe")
            return "0000"

        @dbus_service.method("org.bluez.Agent1", in_signature="ouq", out_signature="")
        def DisplayPasskey(self, device, passkey, entered):
            self._note("DisplayPasskey", str(device),
                       f"passkey={int(passkey):06d} entered={int(entered)}")

        @dbus_service.method("org.bluez.Agent1", in_signature="os", out_signature="")
        def DisplayPinCode(self, device, pincode):
            self._note("DisplayPinCode", str(device), f"pin={pincode}")

        @dbus_service.method("org.bluez.Agent1", in_signature="", out_signature="")
        def Cancel(self):
            self._note("Cancel", answer="—", reason="von BlueZ abgebrochen")

    return PiDriveAgent


class AgentService:
    """Hält Bus, Agent und Adapterzustand."""

    def __init__(self, adapter="hci0", mode="always", alias="PiDrive"):
        self.adapter_name = adapter
        self.mode         = mode
        self.alias        = alias
        self.bus          = None
        self.agent        = None
        self.loop         = None
        self._events      = []
        self._count       = 0
        self._started     = 0.0

    # -- Protokoll ------------------------------------------------------------

    def push_event(self, method, device="", detail="", answer="", reason=""):
        self._count += 1
        entry = {
            "id":     self._count,
            "ts":     round(time.time(), 3),
            "ts_human": time.strftime("%H:%M:%S"),
            "method": method,
            "device": device.rsplit("/", 1)[-1] if device else "",
            "detail": detail,
            "answer": answer,
            "reason": reason,
        }
        self._events.append(entry)
        if len(self._events) > EVENTS_MAX:
            self._events = self._events[-EVENTS_MAX:]
        _write_json_atomic(AGENT_EVENTS_FILE,
                           {"events": self._events, "total": self._count})
        _log(f"{method} dev={entry['device']} {detail} → {answer or '-'} ({reason})")
        self.write_state(ready=True)

    def write_state(self, ready=True, last_error=""):
        # Schema bleibt kompatibel zu cli.py:889 und diagnose.py:573.
        _write_json_atomic(AGENT_STATE_FILE, {
            "running":     True,
            "ready":       ready,
            "pid":         os.getpid(),
            "started_ts":  getattr(self, "_started", 0) or 0,
            "last_error":  last_error,
            "health_ok":   ready,
            "ts":          round(time.time(), 3),
            # neu
            "kind":        "dbus",
            "mode":        self.mode,
            "pair_window_s": round(pair_window_remaining(), 1),
            "event_count": self._count,
        })

    # -- D-Bus ----------------------------------------------------------------

    def _adapter_props(self):
        import dbus
        obj = self.bus.get_object("org.bluez", f"/org/bluez/{self.adapter_name}")
        return dbus.Interface(obj, "org.freedesktop.DBus.Properties")

    def device_is_paired(self, path: str) -> bool:
        if not path:
            return False
        try:
            import dbus
            obj = self.bus.get_object("org.bluez", path)
            props = dbus.Interface(obj, "org.freedesktop.DBus.Properties")
            return bool(props.Get("org.bluez.Device1", "Paired"))
        except Exception:
            return False

    def trust_device(self, path: str) -> None:
        """Nach dem Koppeln vertrauen — sonst fragt BlueZ bei jedem Verbinden neu."""
        if not path:
            return
        try:
            import dbus
            obj = self.bus.get_object("org.bluez", path)
            props = dbus.Interface(obj, "org.freedesktop.DBus.Properties")
            props.Set("org.bluez.Device1", "Trusted", dbus.Boolean(True))
            _log(f"Trusted=true für {path.rsplit('/', 1)[-1]}")
        except Exception as e:
            _log(f"Trusted setzen fehlgeschlagen für {path}: {e}")

    def apply_adapter_settings(self) -> None:
        """
        Dauerhaft findbar und koppelbar. Der 180-Sekunden-Ablauf der BlueZ-Vorgabe
        war der Grund, warum der Pi im Fahrzeug oft nicht in der Geräteliste stand.
        """
        import dbus
        try:
            p = self._adapter_props()
            p.Set("org.bluez.Adapter1", "Alias", dbus.String(self.alias))
            p.Set("org.bluez.Adapter1", "DiscoverableTimeout", dbus.UInt32(0))
            p.Set("org.bluez.Adapter1", "PairableTimeout",     dbus.UInt32(0))
            p.Set("org.bluez.Adapter1", "Discoverable", dbus.Boolean(True))
            p.Set("org.bluez.Adapter1", "Pairable",     dbus.Boolean(True))
            _log(f"Adapter {self.adapter_name}: alias={self.alias!r} "
                 "discoverable=on pairable=on timeout=0")
        except Exception as e:
            _log(f"Adaptereinstellungen fehlgeschlagen: {e}")

    def _watch_pairing(self) -> None:
        """Paired=true mitschreiben, auch wenn der BMW ohne Rückfrage koppelt."""

        def on_props(interface, changed, invalidated, path=None):
            if interface != "org.bluez.Device1":
                return
            if "Paired" in changed and bool(changed["Paired"]):
                self.push_event("Paired", str(path or ""), "",
                                "—", "von BlueZ gemeldet")
                self.trust_device(str(path or ""))
            elif "Connected" in changed:
                connected = bool(changed["Connected"])
                path_s = str(path or "")
                self.push_event("Connected", path_s,
                                f"connected={connected}",
                                "—", "von BlueZ gemeldet")
                # Link-Event für Watcher-Pause / bt_last (Feldtest-Hygiene)
                try:
                    mac = ""
                    if "dev_" in path_s:
                        mac = path_s.rsplit("dev_", 1)[-1].replace("_", ":")
                    name = ""
                    try:
                        import dbus as _dbus
                        obj = self.bus.get_object("org.bluez", path_s)
                        props = _dbus.Interface(
                            obj, "org.freedesktop.DBus.Properties")
                        name = str(props.Get("org.bluez.Device1", "Alias")
                                   or props.Get("org.bluez.Device1", "Name")
                                   or "")
                    except Exception:
                        pass
                    # Datei ohne Projektimporte (Agent läuft standalone)
                    import json as _json
                    link = {
                        "mac": mac,
                        "name": name,
                        "connected": connected,
                        "reason": "agent_connected" if connected else "agent_disconnected",
                        "ts": int(time.time()),
                    }
                    tmp = "/tmp/pidrive_bt_last_link.json.tmp"
                    with open(tmp, "w", encoding="utf-8") as f:
                        _json.dump(link, f)
                    os.replace(tmp, "/tmp/pidrive_bt_last_link.json")
                    if connected and mac:
                        # bt_last-Hinweis für Core (status liest Settings; Datei als Bridge)
                        hint = {
                            "mac": mac, "name": name,
                            "ts": int(time.time()),
                        }
                        tmp2 = "/tmp/pidrive_bt_prefer_mac.json.tmp"
                        with open(tmp2, "w", encoding="utf-8") as f:
                            _json.dump(hint, f)
                        os.replace(tmp2, "/tmp/pidrive_bt_prefer_mac.json")
                except Exception as e:
                    _log(f"Link-Event schreiben: {e}")

        self.bus.add_signal_receiver(
            on_props,
            dbus_interface="org.freedesktop.DBus.Properties",
            signal_name="PropertiesChanged",
            path_keyword="path",
            bus_name="org.bluez")

    def start(self, run_loop: bool = True) -> bool:
        import dbus
        import dbus.service
        from dbus.mainloop.glib import DBusGMainLoop
        from gi.repository import GLib

        self._started = time.time()
        DBusGMainLoop(set_as_default=True)
        self.bus = dbus.SystemBus()

        agent_cls  = _build_agent_class(dbus, dbus.service)
        self.agent = agent_cls(self.bus, AGENT_PATH, self)

        mgr = dbus.Interface(
            self.bus.get_object("org.bluez", "/org/bluez"),
            "org.bluez.AgentManager1")
        try:
            mgr.RegisterAgent(AGENT_PATH, CAPABILITY)
        except Exception as e:
            if "AlreadyExists" not in str(e):
                raise
            _log("Agent war schon registriert — erneut übernehmen")

        # RequestDefaultAgent entscheidet, wer gefragt wird. Läuft daneben noch
        # die alte bluetoothctl-Sitzung aus bt_agent.py, streiten sich beide um
        # diese Rolle: deren Health-Thread schreibt bei jedem Neustart wieder
        # "default-agent". Darum muss die alte Sitzung abgeschaltet sein
        # (Paket BF-E) — sonst hängt es vom Zufall ab, wer die BMW-Rückfrage
        # bekommt, und die alte Sitzung beantwortet sie nicht.
        mgr.RequestDefaultAgent(AGENT_PATH)
        _log(f"Agent registriert: {AGENT_PATH} capability={CAPABILITY} "
             f"regel={self.mode}")

        self.apply_adapter_settings()
        self._watch_pairing()
        self.write_state(ready=True)

        if not run_loop:
            return True

        self.loop = GLib.MainLoop()
        # Zustand regelmäßig auffrischen, damit "Alter" in CLI/WebUI stimmt
        GLib.timeout_add_seconds(5, lambda: (self.write_state(True), True)[1])
        try:
            self.loop.run()
        except KeyboardInterrupt:
            pass
        finally:
            try:
                mgr.UnregisterAgent(AGENT_PATH)
            except Exception:
                pass
            _log("Agent beendet")
        return True


# ── Selbsttest (ohne BlueZ) ──────────────────────────────────────────────────

def selbsttest() -> int:
    global PAIR_WINDOW_FILE
    fehler = 0

    def pruef(name, ist, soll):
        nonlocal fehler
        if ist != soll:
            print(f"  FEHLER {name}: {ist!r} != {soll!r}")
            fehler += 1
        else:
            print(f"  ok     {name}")

    print("decide_confirm:")
    pruef("always",            decide_confirm("always", 0,   False)[0], True)
    pruef("never",             decide_confirm("never",  999, False)[0], False)
    pruef("window offen",      decide_confirm("window", 42,  False)[0], True)
    pruef("window zu",         decide_confirm("window", 0,   False)[0], False)
    pruef("never aber gepaart", decide_confirm("never", 0,   True)[0],  True)
    pruef("unbekannte Regel",  decide_confirm("quatsch", 0,  False)[0], True)

    print("Pairing-Fenster:")
    _echt = PAIR_WINDOW_FILE
    import tempfile
    PAIR_WINDOW_FILE = os.path.join(tempfile.gettempdir(),
                                    "pidrive_pairwin_selftest")
    try:
        if os.path.exists(PAIR_WINDOW_FILE):
            os.remove(PAIR_WINDOW_FILE)
        pruef("ohne Datei geschlossen", pair_window_remaining() == 0.0, True)
        open_pair_window(60)
        rest = pair_window_remaining()
        pruef("nach Oeffnen offen", 55 < rest <= 60, True)
        with open(PAIR_WINDOW_FILE, "w", encoding="utf-8") as f:
            f.write(str(time.time() - 1))        # abgelaufen
        pruef("abgelaufen geschlossen", pair_window_remaining() == 0.0, True)
        with open(PAIR_WINDOW_FILE, "w", encoding="utf-8") as f:
            f.write("kein-zahlenwert")
        pruef("Muell geschlossen", pair_window_remaining() == 0.0, True)
    finally:
        try:
            os.remove(PAIR_WINDOW_FILE)
        except Exception:
            pass
        PAIR_WINDOW_FILE = _echt

    print("Audio-UUIDs:")
    pruef("A2DP Source erlaubt",
          "0000110a-0000-1000-8000-00805f9b34fb" in AUDIO_UUIDS, True)
    pruef("AVRCP Target erlaubt",
          "0000110c-0000-1000-8000-00805f9b34fb" in AUDIO_UUIDS, True)
    pruef("HFP nicht automatisch",
          "0000111e-0000-1000-8000-00805f9b34fb" in AUDIO_UUIDS, False)

    if fehler:
        print(f"\nSelbsttest fehlgeschlagen: {fehler} Fehler.")
        return 1
    print("\nSelbsttest bestanden.")
    return 0


# ── Einsprung ────────────────────────────────────────────────────────────────

def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(
        description="PiDrive BlueZ-Pairing-Agent (D-Bus)")
    ap.add_argument("-f", "--foreground", action="store_true",
                    help="im Vordergrund laufen (Protokoll nach stderr)")
    ap.add_argument("--adapter", default="hci0")
    ap.add_argument("--mode", default=os.environ.get("PIDRIVE_BT_CONFIRM", "always"),
                    choices=["always", "window", "never"],
                    help="Bestätigungsregel (Vorgabe: always)")
    ap.add_argument("--alias", default="PiDrive",
                    help="Name, unter dem der BMW das Gerät anzeigt")
    ap.add_argument("--open-window", type=int, metavar="SEKUNDEN",
                    help="Pairing-Fenster öffnen und beenden")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)

    if args.selftest:
        return selbsttest()

    if args.open_window is not None:
        until = open_pair_window(args.open_window)
        print(f"Pairing-Fenster offen bis "
              f"{time.strftime('%H:%M:%S', time.localtime(until))} "
              f"({args.open_window}s)")
        return 0

    svc = AgentService(adapter=args.adapter, mode=args.mode, alias=args.alias)
    try:
        svc.start(run_loop=True)
        return 0
    except Exception as e:
        _log(f"Start fehlgeschlagen: {e}")
        _write_json_atomic(AGENT_STATE_FILE, {
            "running": False, "ready": False, "pid": 0, "started_ts": 0,
            "last_error": str(e), "health_ok": False, "ts": time.time(),
            "kind": "dbus",
        })
        return 1


if __name__ == "__main__":
    sys.exit(main())
