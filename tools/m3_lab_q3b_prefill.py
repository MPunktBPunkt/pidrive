#!/usr/bin/env python3
"""Q3b Lab: Prefill body behind frozen scan head + Oracles A/B/C.

Geometry (O1 closed, fav0 lba0=81):
  Scan head frozen: absolute LBA 81..760  (fileOff 0 .. 347648)
  Prefill body:     absolute LBA >= 761   (fileOff >= 348160)
  Burst-0 span:     753..4624 (first event lba0=1953)

Oracles (all required for PASS):
  A — SoftAP body_read matches expected seed pattern (slot content)
  B — Host issues MSC reads for the target LBAs after switch (lab-simulated cold burst)
  C — Host dd bytes (actual MSC response) match expected seed pattern B

Tests: A, B, C (A→B switch), control (stay A, no remount).

Example:
  python3 tools/m3_lab_q3b_prefill.py --esp http://192.168.178.88 --dev /dev/sda
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

SECTOR = 512
FROM_OFF = 348160  # LBA 761 on fav0
HEAD_END_OFF = 347648  # last byte of LBA 760 inclusive end+1 = (760-81+1)*512
SAMPLE_SECTORS = 16  # 8 KiB
# Probe points inside burst-0 body (absolute LBA)
PROBE_LBAS = (761, 1000, 1472, 1953, 3000, 4624)
# Sparse cold-burst simulation covering early + late regions
BURST_READS = (
    (761, 64),  # early body (would be missed if prefill started at 1953)
    (1529, 64),
    (1953, 128),
    (3000, 64),
    (4500, 64),
)


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


def http_bytes(url: str, timeout: float = 12) -> tuple[bytes, dict[str, str]]:
    with urllib.request.urlopen(url, timeout=timeout) as r:
        headers = {k.lower(): v for k, v in r.headers.items()}
        return r.read(), headers


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


def wait_dev(dev: str, timeout: float = 25.0) -> None:
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            dd_bytes(dev, 0, 1)
            return
        except subprocess.CalledProcessError:
            time.sleep(0.4)
    raise SystemExit(f"device {dev} not ready")


def sha16(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()[:16]


def expect_cell(tag: str, file_off: int) -> bytes:
    """Mirror LabBodySeed::cellAt."""
    cell = bytearray(16)
    cell[0:4] = b"Q3B1"
    cell[4] = ord(tag)
    cell[8:12] = struct.pack(">I", file_off & ~15)
    s = sum(cell[0:12]) & 0xFFFFFFFF
    cell[12:16] = struct.pack(">I", s)
    return bytes(cell)


def expect_pattern(tag: str, file_off: int, n: int) -> bytes:
    out = bytearray()
    o = 0
    while o < n:
        abs_off = file_off + o
        into = abs_off & 15
        cell = expect_cell(tag, abs_off - into)
        take = min(16 - into, n - o)
        out.extend(cell[into : into + take])
        o += take
    return bytes(out)


def pattern_ok(blob: bytes, tag: str, file_off: int) -> bool:
    if len(blob) < 16:
        return False
    exp = expect_pattern(tag, file_off, len(blob))
    return blob == exp


def seed(esp: str, slot: int, tag: str, from_off: int = FROM_OFF) -> dict:
    body = json.dumps({"slot": slot, "tag": tag, "fromOff": from_off}).encode()
    return http_json(f"{esp}/api/lab/body_seed", method="POST", body=body)


def softap_body(esp: str, slot: int, file_off: int, n: int = SAMPLE_SECTORS * SECTOR) -> bytes:
    raw, _ = http_bytes(f"{esp}/api/lab/body_read?slot={slot}&off={file_off}&n={n}")
    return raw


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--esp", default="http://192.168.178.88")
    ap.add_argument("--dev", default="/dev/sda")
    ap.add_argument("--slot", type=int, default=0)
    ap.add_argument("--from-off", type=int, default=FROM_OFF)
    ap.add_argument("--out", default="")
    ap.add_argument("--skip-remount", action="store_true",
                    help="Skip initial remount (use if media already stable)")
    args = ap.parse_args()

    esp = args.esp.rstrip("/")
    stamp = time.strftime("%H%M")
    day = time.strftime("%Y-%m-%d")
    out = Path(args.out) if args.out else Path(
        f"docs/betrieb/artifacts-{day}-lab/lab88-q3b-{stamp}"
    )
    out.mkdir(parents=True, exist_ok=True)

    print("== Q3b stop live overlay ==")
    try:
        http_json(f"{esp}/api/lab/stop", method="POST", body=b"{}")
    except Exception as e:
        print(f"lab/stop warn: {e}")
    time.sleep(0.3)

    if not args.skip_remount:
        print("== initial remount (once) ==")
        http_json(f"{esp}/api/lab/remount", method="POST", body=b"{}")
        time.sleep(2.5)
    wait_dev(args.dev)

    st0 = http_json(f"{esp}/api/status")
    (out / "status-00.json").write_text(json.dumps(st0, indent=2))
    slot = st0["msc"]["slotMap"][args.slot]
    lba0 = int(slot["lba0"])
    lba1 = int(slot["lba1"])
    print(
        f"fw={st0['version']} serial={st0['msc'].get('usbSerial')} "
        f"slot={args.slot} uid={slot.get('uid')} lba={lba0}..{lba1}"
    )
    if lba0 != 81:
        print(f"WARN: expected fav0 lba0=81, got {lba0}")

    # Warm host cache a bit then proceed
    try:
        dd_bytes(args.dev, 0, 8)
    except subprocess.CalledProcessError:
        pass
    time.sleep(0.5)

    # --- Head baseline (must stay frozen across A→B) ---
    head_lba = lba0 + 100  # inside scan head
    head_a = dd_bytes(args.dev, head_lba, SAMPLE_SECTORS)
    (out / "host_head.bin").write_bytes(head_a)
    head_hash = sha16(head_a)
    print(f"head baseline lba={head_lba} sha16={head_hash}")

    results: dict = {
        "fw": st0.get("version"),
        "serial": st0["msc"].get("usbSerial"),
        "slot": args.slot,
        "lba0": lba0,
        "from_off": args.from_off,
        "prefill_lba": lba0 + args.from_off // SECTOR,
        "head_hash": head_hash,
        "tests": {},
    }

    def oracle_a(tag: str) -> dict:
        samples = {}
        ok_all = True
        for abs_lba in PROBE_LBAS:
            if abs_lba < lba0 or abs_lba > lba1:
                continue
            file_off = (abs_lba - lba0) * SECTOR
            if file_off < args.from_off:
                continue
            soft = softap_body(esp, args.slot, file_off)
            ok = pattern_ok(soft, tag, file_off)
            samples[str(abs_lba)] = {
                "file_off": file_off,
                "sha16": sha16(soft),
                "match": ok,
                "n": len(soft),
            }
            ok_all = ok_all and ok
            (out / f"softap_{tag}_lba{abs_lba}.bin").write_bytes(soft)
        return {"pass": ok_all and bool(samples), "samples": samples}

    def host_burst(tag: str, after_ts: float) -> dict:
        """Lab Oracle B+C via controlled host reads (NOT an observed HU cold-burst).

        Oracle B (lab): we ourselves issue dd READs after t_switch — proves the
        host path accepted post-switch requests for those LBAs. Field Oracle B
        must use a real HU USB trace instead.

        Oracle C: MSC response bytes from dd must match the expected pattern
        AND len(blob) == sectors*512 (short transfers fail).
        """
        reads = []
        ok_c = True
        for abs_lba, nsec in BURST_READS:
            if abs_lba < lba0 or abs_lba + nsec - 1 > lba1:
                continue
            file_off = (abs_lba - lba0) * SECTOR
            expect_n = nsec * SECTOR
            t0 = time.time()
            try:
                blob = dd_bytes(args.dev, abs_lba, nsec)
            except subprocess.CalledProcessError as e:
                blob = b""
                print(f"  dd fail lba={abs_lba}: {e}")
            t1 = time.time()
            len_ok = len(blob) == expect_n
            match = None
            if file_off >= args.from_off:
                match = bool(len_ok and pattern_ok(blob, tag, file_off))
                ok_c = ok_c and bool(match)
            elif not len_ok:
                ok_c = False
            reads.append(
                {
                    "lba": abs_lba,
                    "sectors": nsec,
                    "expect_bytes": expect_n,
                    "got_bytes": len(blob),
                    "len_ok": len_ok,
                    "file_off": file_off,
                    "sha16": sha16(blob) if blob else None,
                    "match_tag": match,
                    "ts": t0,
                    "after_switch": t0 >= after_ts,
                    "dt_ms": int((t1 - t0) * 1000),
                    "oracle_b_note": "controlled_host_dd",
                }
            )
            if blob:
                (out / f"host_{tag}_lba{abs_lba}.bin").write_bytes(
                    blob[: SAMPLE_SECTORS * SECTOR]
                )
        # Lab Oracle B: planned LBAs successfully fully-read after switch
        oracle_b = (
            len(reads) >= 3
            and all(r["after_switch"] and r["len_ok"] for r in reads)
        )
        return {
            "oracle_b": oracle_b,
            "oracle_b_kind": "lab_controlled_host_dd",
            "oracle_c": ok_c and bool(reads),
            "oracle_c_coverage": "sampled_lbas_not_full_span",
            "reads": reads,
        }

    # ===== Test A: seed A, Oracle A =====
    print("== Test A: seed A ==")
    sa = seed(esp, args.slot, "A", args.from_off)
    (out / "seed_A.json").write_text(json.dumps(sa, indent=2))
    time.sleep(0.2)
    oa = oracle_a("A")
    # Also check host delivers A (pre-switch baseline for C)
    t_a = time.time()
    hb_a = host_burst("A", t_a)
    results["tests"]["A"] = {
        "oracle_a": oa,
        "host": hb_a,
        "pass": oa["pass"] and hb_a["oracle_c"],
    }
    print(f"  Oracle A={oa['pass']} host_C={hb_a['oracle_c']}")

    # ===== Test B: seed B (no remount), Oracle A for B =====
    print("== Test B: seed B (no remount) ==")
    remount_gen_before = st0["msc"].get("remountGen")
    sb = seed(esp, args.slot, "B", args.from_off)
    t_switch = time.time()
    (out / "seed_B.json").write_text(json.dumps({"resp": sb, "t_switch": t_switch}, indent=2))
    time.sleep(0.2)
    st_b = http_json(f"{esp}/api/status")
    (out / "status-01-after-B.json").write_text(json.dumps(st_b, indent=2))
    remount_gen_after = st_b["msc"].get("remountGen")
    no_remount = remount_gen_before == remount_gen_after
    ob = oracle_a("B")
    results["tests"]["B"] = {
        "oracle_a": ob,
        "no_remount": no_remount,
        "remountGen": [remount_gen_before, remount_gen_after],
        "pass": ob["pass"] and no_remount,
    }
    print(f"  Oracle A(B)={ob['pass']} no_remount={no_remount}")

    # ===== Test C: cold-burst after A→B — Oracles B+C =====
    print("== Test C: host cold-burst after switch → expect B ==")
    hc = host_burst("B", t_switch)
    head_after = dd_bytes(args.dev, head_lba, SAMPLE_SECTORS)
    head_frozen = head_after == head_a
    (out / "host_head_after_B.bin").write_bytes(head_after)
    # Early region 761 must be B (critical O1 check)
    early = next((r for r in hc["reads"] if r["lba"] == 761), None)
    early_b = bool(early and early.get("match_tag"))
    results["tests"]["C"] = {
        "oracle_b": hc["oracle_b"],
        "oracle_c": hc["oracle_c"],
        "head_frozen": head_frozen,
        "early_lba761_is_B": early_b,
        "t_switch": t_switch,
        "reads": hc["reads"],
        "pass": hc["oracle_b"] and hc["oracle_c"] and head_frozen and early_b and no_remount,
    }
    print(
        f"  Oracle B={hc['oracle_b']} C={hc['oracle_c']} "
        f"head_frozen={head_frozen} early761_B={early_b}"
    )

    # ===== Control: back to A, burst must be A, no remount =====
    print("== Control: seed A again, burst expect A ==")
    seed(esp, args.slot, "A", args.from_off)
    t_ctrl = time.time()
    time.sleep(0.2)
    st_c = http_json(f"{esp}/api/status")
    (out / "status-02-control.json").write_text(json.dumps(st_c, indent=2))
    hctrl = host_burst("A", t_ctrl)
    no_remount_ctrl = st_c["msc"].get("remountGen") == remount_gen_after
    results["tests"]["control"] = {
        "oracle_c": hctrl["oracle_c"],
        "no_remount": no_remount_ctrl,
        "reads": hctrl["reads"],
        "pass": hctrl["oracle_c"] and no_remount_ctrl,
    }
    print(f"  control_C={hctrl['oracle_c']} no_remount={no_remount_ctrl}")

    # Cleanup seed
    try:
        seed(esp, args.slot, "off", args.from_off)
    except Exception:
        pass

    tA = results["tests"]["A"]["pass"]
    tB = results["tests"]["B"]["pass"]
    tC = results["tests"]["C"]["pass"]
    tCtrl = results["tests"]["control"]["pass"]
    if tA and tB and tC and tCtrl:
        verdict = "PASS"
    elif tC and (tA or tB):
        verdict = "PASS_WEAK"
    else:
        verdict = "FAIL"
    results["verdict"] = verdict
    results["note"] = (
        "Lab Oracle B = host-simulated cold-burst (dd), not HU. "
        "Oracle C = actual MSC response bytes via dd iflag=direct. "
        "lba1 in field traces is NOT transfer end."
    )

    (out / "report.json").write_text(json.dumps(results, indent=2))
    (out / "NOTES.md").write_text(
        "\n".join(
            [
                f"# Q3b Prefill Lab — `{out.name}`",
                "",
                f"**Verdict:** `{verdict}`",
                f"**FW:** `{results['fw']}` · Serial `{results['serial']}`",
                f"**Prefill:** fromOff={args.from_off} (abs LBA {results['prefill_lba']})",
                "",
                "## Results",
                f"- Test A (seed A / Oracle A+host): **{tA}**",
                f"- Test B (seed B SoftAP / no remount): **{tB}**",
                f"- Test C (burst after A→B / Oracle B+C / head frozen / LBA761=B): **{tC}**",
                f"- Control (stay/return A, no remount): **{tCtrl}**",
                "",
                "## Oracles",
                "- **A** SoftAP `/api/lab/body_read` == expected Q3B1 pattern",
                "- **B** Host issued post-switch reads for burst LBAs (lab-simulated)",
                "- **C** Host `dd` MSC response bytes == expected pattern",
                "",
                "## Geometry",
                f"- Scan head: LBA {lba0}..760 (frozen hash {head_hash})",
                f"- Prefill body: LBA >= {results['prefill_lba']}",
                "- Do not start prefill at 1953 — burst also reads 761..1952",
                "",
            ]
        )
    )
    print(json.dumps({"verdict": verdict, "tests": {k: v["pass"] for k, v in results["tests"].items()}}, indent=2))
    print(f"artefacts: {out}")
    return 0 if verdict.startswith("PASS") else 1


if __name__ == "__main__":
    raise SystemExit(main())
