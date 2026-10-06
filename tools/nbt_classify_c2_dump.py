#!/usr/bin/env python3
"""C2 diagnose: dump OTHER blocks from fav1 with silence-phase analysis."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
# Load sibling as package-free module via runpy-style path
import importlib.util

_ROOT = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("nbt_hu_sim", _ROOT / "nbt_hu_sim.py")
assert _spec and _spec.loader
m = importlib.util.module_from_spec(_spec)
sys.modules["nbt_hu_sim"] = m
_spec.loader.exec_module(m)

OUT = Path("docs/betrieb/artifacts-2026-10-06-lab/lab88-classify-c2")
SYNC = m.KSIL[:4]


def phase_analysis(blob: bytes) -> dict:
    first = blob.find(SYNC)
    lame = blob.find(b"LAME3.100")
    best_p, best_hits = 0, 0
    for p in range(156):
        hits = sum(1 for o in range(p, len(blob) - 3, 156) if blob[o : o + 4] == SYNC)
        if hits > best_hits:
            best_p, best_hits = p, hits
    hits0 = sum(1 for o in range(0, len(blob) - 4, 156) if blob[o : o + 4] == SYNC)
    return {
        "first4": blob[:4].hex(),
        "first_sync_off": first,
        "lame_off": lame,
        "hits_phase0": hits0,
        "best_phase": best_p,
        "best_hits": best_hits,
        "old_would_enter_silence_branch": blob[:4] == SYNC
        or (SYNC in blob[:8] and b"LAME3.100" in blob),
        "has_ff_fb": blob[:2] == b"\xff\xfb",
        "has_ff_f3": blob[:2] == b"\xff\xf3",
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    esp = "http://192.168.178.88"
    profile = m.load_profile(_ROOT / "profiles" / "nbt_evo_2026-10-06.json")
    pump = m.prep_lab(esp, "192.168.178.88", None, remount=True)
    hu = m.HuSim("/dev/sg0", profile)
    try:
        hu.open()
        hu.refresh_slots(esp)
        slot = hu.slots["fav1"]
        samples: list[dict] = []
        other_n = sil_n = id3_n = 0
        off = 0
        while off < slot.size and other_n < 25:
            blob = hu.read_n("fav1", off)
            if not blob:
                break
            klass = m.classify_block(blob, off)
            if klass == "OTHER":
                samples.append({"off": off, "n": len(blob), "klass": klass, **phase_analysis(blob), "hex64": blob[:64].hex()})
                other_n += 1
            elif klass == "SILENCE":
                sil_n += 1
            elif klass == "ID3":
                id3_n += 1
            off += len(blob)

        preview = {"ID3": 0, "SILENCE": 0, "OTHER": 0, "LIVE": 0, "SEED": 0}
        off = 0
        while off < slot.size:
            n = min(4096, slot.size - off)
            n = (n // 512) * 512
            if n <= 0:
                break
            blob, _ = m.read_sg(hu.sg_fd, slot.lba0 + off // 512, n, 5000)
            k = m.classify_block(blob, off)
            preview[k] = preview.get(k, 0) + 1
            off += len(blob)

        report = {
            "counts_during_dump_walk": dict(hu.class_counts),
            "silence_seen_before_25_other": sil_n,
            "id3_seen": id3_n,
            "other_samples": len(samples),
            "full_file_old_classifier": preview,
            "samples": samples[:20],
        }
        (OUT / "OTHER-DUMP.json").write_text(json.dumps(report, indent=2))
        print(json.dumps({k: report[k] for k in report if k != "samples"}, indent=2))
        print("--- first 8 OTHER ---")
        for s in samples[:8]:
            print(
                f"off={s['off']:7d} first4={s['first4']} sync@{s['first_sync_off']:4d} "
                f"best_p={s['best_phase']:3d} hits0={s['hits_phase0']:2d} best={s['best_hits']:2d} "
                f"enter={s['old_would_enter_silence_branch']}"
            )
    finally:
        hu.close()
        try:
            pump.close()
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
