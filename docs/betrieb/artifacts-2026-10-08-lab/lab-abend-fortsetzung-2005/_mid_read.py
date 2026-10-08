
import json, sys
sys.path.insert(0, "/home/martin/projects/pidrive/tools")
from pathlib import Path
from nbt_hu_sim import HuSim, load_profile, prep_lab, snap_retry
esp = "http://192.168.178.88"
out = Path("/home/martin/projects/pidrive/docs/betrieb/artifacts-2026-10-08-lab/lab-abend-fortsetzung-2005/mid-sg")
out.mkdir(exist_ok=True)
profile = load_profile(Path("/home/martin/projects/pidrive/tools/profiles/nbt_evo_2026-10-06.json"))
hu = HuSim("/dev/sg0", profile)
pump = None
try:
    pump = prep_lab(esp, "192.168.178.88", None, remount=False)
    hu.open()
    hu.refresh_slots(esp)
    # mid-file fav2: 64 KiB into body (past ID3/head)
    n = 0
    for off in range(65536, 65536 + 32 * 4096, 4096):
        n += len(hu.read_n("fav2", off, 4096))
    post = snap_retry(esp)
    (out / "status.json").write_text(json.dumps(post, indent=2))
    print(json.dumps({"bytes": n, "rej": (post.get("msc") or {}).get("playRejectCount")}))
finally:
    hu.close()
    if pump:
        try: pump.close()
        except Exception: pass
