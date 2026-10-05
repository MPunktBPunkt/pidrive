#!/usr/bin/env python3
"""Lab: menu page (Meta vs Sender) + return paths + AV smoke + correlate.

Reproduces field symptom: HU/session on Favoriten/Quellen/Stop while MSC lock
keeps Rock/Bayern/BOB slots; AV needs sender page + live producer.

Example:
  python3 tools/m3_lab_menu_page_session.py --esp http://192.168.178.88 --dev /dev/sda
"""
from __future__ import annotations

import argparse
import json
import socket
import struct
import subprocess
import time
import urllib.request
from pathlib import Path

BRIDGE = Path("/home/martin/projects/esphub/esp32.pidrive/tools/pump_bridge.py")
MENU = Path("/tmp/pidrive_menu.json")
LOCK_LOG = Path("/tmp/pidrive_msc_lock.jsonl")
READS_LOG = Path("/tmp/pidrive_msc_reads.jsonl")
FRAME_MAX = 512
ID3_BUDGET = 128

STATIONS_ROOT = [
    {"uid": "fav0", "name": "Rock Antenne", "kind": "station"},
    {"uid": "fav1", "name": "Rock Antenne Bayern", "kind": "station"},
    {"uid": "fav2", "name": "Radio BOB!", "kind": "station"},
    {"uid": "pump:page_next", "name": "Menue", "kind": "action"},
]

META_NODES = [
    {"uid": "14037496848256783396", "id": "fav_folder", "label": "Favoriten", "type": "folder"},
    {"uid": "1628800432581751424", "id": "src", "label": "Quellen", "type": "folder"},
    {"uid": "7194960129032930190", "id": "stop", "label": "Stop", "type": "action"},
    {"uid": "pump:page_next", "id": "more", "label": "Mehr... (+3)", "type": "action"},
]

META_MSC_ITEMS = [
    {"uid": "14037496848256783396", "name": "Favoriten", "kind": "folder"},
    {"uid": "1628800432581751424", "name": "Quellen", "kind": "folder"},
    {"uid": "7194960129032930190", "name": "Stop", "kind": "action"},
    {"uid": "pump:page_next", "name": "Mehr... (+3)", "kind": "action"},
]


def http_json(url: str, method: str = "GET", body: bytes | None = None, timeout: float = 12) -> dict:
    req = urllib.request.Request(
        url,
        data=body,
        method=method,
        headers={"Content-Type": "application/json"} if body is not None else {},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
        return json.loads(raw.decode()) if raw else {}


def menu_names(esp: str) -> list[str]:
    doc = http_json(esp.rstrip("/") + "/api/menu")
    return [str(i.get("name") or "") for i in (doc.get("menu") or {}).get("items") or []]


def slot_names(st: dict) -> list[str]:
    return [str(s.get("name") or "") for s in (st.get("msc") or {}).get("slotMap") or []]


def live_bytes(st: dict) -> int:
    m = st.get("msc") or {}
    s = m.get("stream") or {}
    sb = int(m.get("streamBytes") or 0)
    ud = int(s.get("underruns") or 0)
    return sb - ud


def stream_summary(st: dict) -> dict:
    m = st.get("msc") or {}
    s = m.get("stream") or {}
    return {
        "active": s.get("active"),
        "uid": s.get("uid"),
        "size": s.get("size"),
        "liveBytes": live_bytes(st),
        "playingUid": st.get("playingUid"),
        "playingName": st.get("playingName"),
    }


def write_menu(rev: int, nodes: list[dict], path_ids: list | None = None) -> None:
    MENU.write_text(
        json.dumps(
            {"rev": rev, "path_ids": path_ids or ["root"], "nodes": nodes},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def save_pair(out: Path, tag: str, esp: str) -> None:
    st = http_json(esp.rstrip("/") + "/api/status")
    mn = http_json(esp.rstrip("/") + "/api/menu")
    (out / f"status-{tag}.json").write_text(json.dumps(st, indent=2))
    (out / f"menu-{tag}.json").write_text(json.dumps(mn, indent=2))


def lab_play(esp: str, uid: str) -> dict:
    return http_json(
        esp.rstrip("/") + "/api/lab/play",
        method="POST",
        body=json.dumps({"uid": uid}).encode(),
    )


def correlate_row(st: dict) -> dict:
    m = st.get("msc") or {}
    s = m.get("stream") or {}
    abs_base = int(s.get("absBase") or 0)
    abs_end = int(s.get("absEnd") or 0)
    host_abs = int(s.get("hostAbsCursor") or 0)
    return {
        **stream_summary(st),
        "menu": menu_names_from_status(st),
        "slotMap": slot_names(st),
        "host_in_window": abs_end > abs_base and abs_base <= host_abs < abs_end,
        "abs": [abs_base, abs_end],
    }


def menu_names_from_status(st: dict) -> list[str]:
    return slot_names(st)


def dd_bytes(dev: str, lba: int, sectors: int) -> bytes:
    return subprocess.check_output(
        [
            "dd",
            f"if={dev}",
            "bs=512",
            f"skip={lba}",
            f"count={sectors}",
            "iflag=direct",
            "status=none",
        ],
        stderr=subprocess.DEVNULL,
    )


def build_minimal_id3(title: str) -> bytes:
    enc = b"\x00" + title.encode("latin-1", errors="replace")[:30]
    frame = b"TIT2" + struct.pack(">I", len(enc)) + b"\x00\x00" + enc
    size = len(frame)
    header = b"ID3\x03\x00\x00" + bytes(
        [(size >> 21) & 0x7F, (size >> 14) & 0x7F, (size >> 7) & 0x7F, size & 0x7F]
    )
    return (header + frame)[:ID3_BUDGET]


class PumpTcp:
    def __init__(self, host: str, port: int = 9090):
        self.s = socket.create_connection((host, port), timeout=8)
        self.s.settimeout(0.35)
        self.buf = b""

    def close(self) -> None:
        try:
            self.s.close()
        except OSError:
            pass

    def send_json(self, obj: dict) -> None:
        self.s.sendall((json.dumps(obj, separators=(",", ":")) + "\n").encode())

    def send_bin(self, kind: int, payload: bytes, gap_s: float = 0.002) -> None:
        off = 0
        while off < len(payload):
            chunk = payload[off : off + FRAME_MAX]
            hdr = bytes((0x01, kind, len(chunk) & 0xFF, (len(chunk) >> 8) & 0xFF))
            self.s.sendall(hdr + chunk)
            off += len(chunk)
            time.sleep(gap_s)

    def recv_lines(self, deadline: float) -> list[dict]:
        out: list[dict] = []
        while time.time() < deadline:
            try:
                chunk = self.s.recv(4096)
            except socket.timeout:
                continue
            except OSError:
                break
            if not chunk:
                break
            self.buf += chunk
            while b"\n" in self.buf:
                line, self.buf = self.buf.split(b"\n", 1)
                text = line.decode("utf-8", errors="replace").strip()
                if text.startswith("{"):
                    try:
                        out.append(json.loads(text))
                    except json.JSONDecodeError:
                        pass
        return out


def wait_bridge_frozen(log_path: Path, timeout: float = 30) -> list[str]:
    t0 = time.time()
    while time.time() - t0 < timeout:
        if log_path.is_file():
            txt = log_path.read_text(encoding="utf-8", errors="replace")
            if "MSC_MAP_FROZEN" in txt or "frozen map" in txt.lower():
                break
        time.sleep(0.4)
    return []


def host_read_burst(dev: str, lba: int, sectors: int = 32) -> None:
    try:
        dd_bytes(dev, lba, sectors)
    except subprocess.CalledProcessError:
        pass


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--esp", default="http://192.168.178.88")
    ap.add_argument("--esp-ip", default="192.168.178.88")
    ap.add_argument("--dev", default="/dev/sda")
    ap.add_argument("--mp3", default="docs/betrieb/artifacts-2026-10-03-m3/mp3/L1.mp3")
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    esp = args.esp.rstrip("/")
    mp3_path = Path(args.mp3)
    if not mp3_path.is_file():
        raise SystemExit(f"mp3 missing: {mp3_path}")

    stamp = time.strftime("%H%M")
    day = time.strftime("%Y-%m-%d")
    out = Path(args.out) if args.out else Path(
        f"docs/betrieb/artifacts-{day}-lab/lab88-menu-page-{stamp}"
    )
    out.mkdir(parents=True, exist_ok=True)

    report: dict = {"steps": {}, "verdict": {}, "out": str(out)}

    print("== reset lab state ==")
    http_json(f"{esp}/api/lab/body_seed", method="POST", body=b'{"slot":0,"tag":"off"}')
    http_json(f"{esp}/api/lab/stop", method="POST", body=b"{}")
    time.sleep(0.3)

    for p in (LOCK_LOG, READS_LOG):
        try:
            p.write_text("")
        except OSError:
            pass

    st0 = http_json(f"{esp}/api/status")
    if not (st0.get("msc") or {}).get("plugged"):
        raise SystemExit("ESP MSC not plugged — need USB host session")

    bridge_log = out / "bridge.log"
    print("== bridge (msc-lock, no-audio) ==")
    proc = subprocess.Popen(
        [
            "python3",
            str(BRIDGE),
            "--transport",
            "tcp",
            "--host",
            args.esp_ip,
            "--no-audio",
            "--msc-lock",
            "--interval",
            "0.5",
        ],
        stdout=bridge_log.open("w"),
        stderr=subprocess.STDOUT,
        text=True,
    )

    try:
        write_menu(6001, [{"uid": "folder:x", "id": "x", "label": "Ignore", "type": "folder"}], ["root"])
        deadline = time.time() + 35
        sealed: list[str] = []
        while time.time() < deadline:
            time.sleep(0.5)
            txt = bridge_log.read_text(encoding="utf-8", errors="replace")
            if "MSC_MAP_FROZEN" in txt or "sealed" in txt.lower():
                sealed = menu_names(esp)
                if sealed and any("Rock" in n or "BOB" in n or "Bayern" in n for n in sealed):
                    break
        if not sealed:
            sealed = menu_names(esp)
        save_pair(out, "00-sealed-sender", esp)
        st_sealed = http_json(f"{esp}/api/status")
        report["steps"]["seal"] = {
            "menu_api": sealed,
            "slotMap": slot_names(st_sealed),
            "match": sealed == slot_names(st_sealed),
        }
        print("sealed", sealed, "slotMap", slot_names(st_sealed))

        # --- Meta page (Pi-UI settings + lab/play page_next) ---
        print("== meta page repro ==")
        write_menu(6002, META_NODES, ["settings"])
        time.sleep(4.0)
        lab_play(esp, "pump:page_next")
        time.sleep(2.0)
        save_pair(out, "01-meta-session", esp)
        st_meta = http_json(f"{esp}/api/status")
        api_meta = menu_names(esp)
        slots_meta = slot_names(st_meta)
        meta_like = any(n in api_meta for n in ("Favoriten", "Quellen", "Stop"))
        report["steps"]["meta_repro"] = {
            "menu_api": api_meta,
            "slotMap": slots_meta,
            "meta_like_api": meta_like,
            "lock_kept_sender_slots": any(
                x in slots_meta for x in ("Rock Antenne", "Rock Antenne Bayern", "Radio BOB!")
            ),
            "stream": stream_summary(st_meta),
        }

        print("== meta: lab/play Stop + correlate (expect no live) ==")
        http_json(f"{esp}/api/lab/stop", method="POST", body=b"{}")
        time.sleep(0.4)
        lab_play(esp, "7194960129032930190")
        time.sleep(1.0)
        slot = next((s for s in st_meta["msc"]["slotMap"] if s.get("uid") == "fav0"), None)
        if slot:
            host_read_burst(args.dev, int(slot["lba0"]) + 700, 24)
        time.sleep(0.5)
        st_meta_play = http_json(f"{esp}/api/status")
        save_pair(out, "02-meta-stop-reads", esp)
        report["steps"]["meta_av_negative"] = correlate_row(st_meta_play)

        # --- Return A: page_home via lab/play ---
        print("== return A: pump:page_home ==")
        lab_play(esp, "pump:page_home")
        time.sleep(2.5)
        save_pair(out, "03-return-page-home", esp)
        st_home = http_json(f"{esp}/api/status")
        home_names = menu_names(esp)
        report["steps"]["return_page_home"] = {
            "menu_api": home_names,
            "slotMap": slot_names(st_home),
            "sender_visible": any("Rock" in n or "BOB" in n for n in home_names),
        }

        # --- Return B: remount + bridge reseal ---
        print("== return B: remount + root menu ==")
        http_json(f"{esp}/api/lab/remount", method="POST", body=b"{}")
        time.sleep(2.0)
        write_menu(6003, [{"uid": "folder:x", "id": "x", "label": "Ignore", "type": "folder"}], ["root"])
        time.sleep(5.0)
        save_pair(out, "04-return-remount", esp)
        st_rem = http_json(f"{esp}/api/status")
        rem_names = menu_names(esp)
        report["steps"]["return_remount"] = {
            "menu_api": rem_names,
            "slotMap": slot_names(st_rem),
            "remountGen": (st_rem.get("msc") or {}).get("remountGen"),
        }

        # --- Field-like meta (no lock): MSC slotMap = Favoriten/Quellen/Stop ---
        print("== field-like meta (no msc-lock) ==")
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        proc = None
        time.sleep(0.5)
        http_json(f"{esp}/api/lab/stop", method="POST", body=b"{}")
        time.sleep(1.5)
        for attempt in range(5):
            try:
                pump_meta = PumpTcp(args.esp_ip, 9090)
                pump_meta.send_json({"t": "hello", "ver": 1})
                try:
                    pump_meta.recv_lines(time.time() + 2.0)
                except OSError:
                    pass
                pump_meta.send_json(
                    {"t": "menu_set", "rev": 6010, "page": 0, "items": META_MSC_ITEMS}
                )
                try:
                    pump_meta.recv_lines(time.time() + 2.0)
                except OSError:
                    pass
                pump_meta.close()
                break
            except OSError as e:
                print(f"field-meta pump attempt {attempt + 1}: {e}", flush=True)
                time.sleep(1.0)
        else:
            raise SystemExit("pump TCP unavailable for field-meta menu_set")
        time.sleep(1.0)
        save_pair(out, "05-field-meta-nolock", esp)
        st_fn = http_json(f"{esp}/api/status")
        fn_api = menu_names(esp)
        fn_slots = slot_names(st_fn)
        field_meta = any(n in fn_api for n in ("Favoriten", "Quellen", "Stop")) and any(
            n in fn_slots for n in ("Favoriten", "Quellen", "Stop")
        )
        lab_play(esp, "7194960129032930190")
        time.sleep(0.8)
        st_fn2 = http_json(f"{esp}/api/status")
        save_pair(out, "06-field-meta-stop", esp)
        report["steps"]["field_meta_nolock"] = {
            "menu_api": fn_api,
            "slotMap": fn_slots,
            "field_meta_slotMap": field_meta,
            "stream": correlate_row(st_fn2),
        }
        proc = None

        # --- AV smoke on sender page (direct pump, no bridge audio) ---
        print("== AV smoke (pump TCP + host reads) ==")
        http_json(f"{esp}/api/lab/stop", method="POST", body=b"{}")
        time.sleep(0.3)
        pump = PumpTcp(args.esp_ip, 9090)
        mp3 = mp3_path.read_bytes()
        try:
            pump.send_json({"t": "hello", "ver": 1})
            try:
                pump.recv_lines(time.time() + 2.0)
            except OSError:
                pass
            pump.send_json({"t": "audio_stop"})
            time.sleep(0.15)
            pump.send_json(
                {
                    "t": "menu_set",
                    "rev": int(time.time()) % 100000,
                    "page": 0,
                    "items": STATIONS_ROOT,
                }
            )
            try:
                pump.recv_lines(time.time() + 2.0)
            except OSError:
                pass
            time.sleep(1.0)
            save_pair(out, "07-av-menu", esp)

            pump.send_json(
                {
                    "t": "audio_start",
                    "uid": "fav0",
                    "codec": "mp3",
                    "br": "48k",
                    "cSrc": "menu-lab",
                    "cPath": "menu-lab",
                    "cTry": "menu-lab",
                }
            )
            try:
                pump.recv_lines(time.time() + 1.0)
            except OSError:
                pass
            pump.send_bin(0x56, build_minimal_id3("Menu-Lab-AV"), gap_s=0.05)
            pump.send_bin(0x55, mp3[: min(len(mp3), 200 * 1024)], gap_s=0.002)
            time.sleep(1.2)

            st_av = http_json(f"{esp}/api/status")
            slot0 = next(s for s in st_av["msc"]["slotMap"] if s.get("uid") == "fav0")
            host_read_burst(args.dev, int(slot0["lba0"]) + 700, 32)
            time.sleep(0.6)
            st_av2 = http_json(f"{esp}/api/status")
            save_pair(out, "08-av-after-feed", esp)
            live = live_bytes(st_av2)
            s = (st_av2.get("msc") or {}).get("stream") or {}
            av_ok = bool(s.get("active")) and live > 0
            report["steps"]["av_smoke"] = {
                "stream": stream_summary(st_av2),
                "pass": av_ok,
            }
            print("AV smoke", "PASS" if av_ok else "FAIL", report["steps"]["av_smoke"])
            pump.send_json({"t": "audio_stop"})
        finally:
            pump.close()

        if LOCK_LOG.exists():
            (out / "msc_lock.jsonl").write_text(LOCK_LOG.read_text(encoding="utf-8", errors="replace"))
        if bridge_log.exists():
            pass  # already at out/bridge.log

        rejections = "frozen_reject" in bridge_log.read_text(encoding="utf-8", errors="replace")
        report["verdict"] = {
            "meta_reproduced_api": meta_like,
            "field_meta_slotMap": report["steps"].get("field_meta_nolock", {}).get(
                "field_meta_slotMap"
            ),
            "lock_kept_slots": report["steps"]["meta_repro"].get("lock_kept_sender_slots"),
            "meta_live_zero": not report["steps"]["meta_av_negative"].get("active"),
            "return_page_home": report["steps"]["return_page_home"].get("sender_visible"),
            "av_smoke_pass": report["steps"]["av_smoke"].get("pass"),
            "bridge_frozen_reject_logged": rejections,
        }
        overall = bool(
            report["verdict"].get("lock_kept_slots")
            and report["verdict"].get("meta_live_zero")
            and report["verdict"].get("av_smoke_pass")
            and (
                meta_like
                or report["verdict"].get("field_meta_slotMap")
                or rejections
            )
        )
        report["ok"] = overall

        (out / "REPORT.json").write_text(json.dumps(report, indent=2))
        (out / "EAR.txt").write_text(
            "\n".join(
                [
                    f"Lab menu-page session {day} {stamp} ok={overall}",
                    "Abend: HU auf Rock/Bayern/BOB (nicht Favoriten/Quellen/Stop); "
                    "Mehr… nur wenn Lock Sender-Slots behält.",
                    f"Zurück Sender: page_home={report['verdict']['return_page_home']} "
                    f"remount+reseal siehe status-04-return-remount.",
                    f"AV Lab smoke liveBytes>0: {report['verdict']['av_smoke_pass']}.",
                    f"Meta Negativ live=0: {report['verdict']['meta_live_zero']}.",
                    "",
                ]
            )
        )
        (out / "GESAMTBERICHT-MENU-PAGE-AV-PREP.md").write_text(
            "\n".join(
                [
                    "# Lab Menü-Seite + AV-Prep",
                    "",
                    f"**ESP:** `{esp}` · **Artefakt:** `{out}`",
                    "",
                    "## Befund",
                    "",
                    f"- API-Menü Meta (Favoriten/Quellen/Stop): **{meta_like}**",
                    f"- MSC slotMap behält Sender trotz Meta-Session: "
                    f"**{report['verdict']['lock_kept_slots']}**",
                    f"- Meta + Reads: `stream.active=false`, liveBytes=0: "
                    f"**{report['verdict']['meta_live_zero']}**",
                    f"- Rückweg `pump:page_home`: Sender in API sichtbar "
                    f"**{report['verdict']['return_page_home']}**",
                    f"- AV-Smoke Sender + Pump: **{report['verdict']['av_smoke_pass']}**",
                    "",
                    "## Operator Abend (Feld)",
                    "",
                    "1. Bridge `--msc-lock` wie Feld.",
                    "2. Erst wenn HU **Rock Antenne / Bayern / BOB** zeigt → AV/Correlate.",
                    "3. Liegt HU auf **Favoriten/Quellen/Stop** → `Mehr…` / **Seite 1** "
                    "(`pump:page_home`) oder Remount nur nach Lab-Prozedur; kein C′.",
                    "",
                ]
            )
        )
        print(json.dumps(report["verdict"], indent=2))
        print(f"OUT={out} ok={overall}")
        return 0 if overall else 1
    finally:
        if proc is not None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
