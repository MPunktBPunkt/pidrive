#!/usr/bin/env python3
"""Archive a docs/betrieb/artifacts-* day: keep reports, tar raw, index SQLite.

Examples:
  python3 tools/archive_artifacts_day.py --day docs/betrieb/artifacts-2026-10-07-feld --dry
  python3 tools/archive_artifacts_day.py --before 2026-10-08 --apply
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import shutil
import sqlite3
import tarfile
from pathlib import Path
from typing import Any, Iterable

KEEP_NAME_RE = re.compile(
    r"(?i)^("
    r"ERGEBNIS.*|UEBERGABE.*|GESAMTBERICHT.*|ANALYSE.*|MASSNAHMEN.*|"
    r"A1-REPORT\.json|IDENTITY-REPORT\.json|REPORT\.json|summary\.json|"
    r".*-REPORT\.json|probe-summary\.json|NOTE\.txt|README\.md"
    r")$"
)
KEEP_SUFFIXES = {".md"}
DAY_RE = re.compile(r"^artifacts-(\d{4}-\d{2}-\d{2})")


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def archive_root(root: Path) -> Path:
    return root / "docs" / "archiv" / "betrieb-artifacts"


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            block = fh.read(chunk)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def should_keep(rel: Path) -> bool:
    name = rel.name
    if name in {".gitkeep"}:
        return False
    if KEEP_NAME_RE.match(name):
        return True
    if rel.suffix.lower() in KEEP_SUFFIXES and name.upper().startswith(
        ("ERGEBNIS", "UEBERGABE", "GESAMT", "ANALYSE", "README", "PLAN", "KRITIK")
    ):
        return True
    # Keep short markdown/txt notes at top levels, not deep console dumps
    if rel.suffix.lower() == ".md" and len(rel.parts) <= 3:
        return True
    return False


def iter_files(day_dir: Path) -> Iterable[Path]:
    for path in sorted(day_dir.rglob("*")):
        if path.is_file():
            yield path


def ensure_db(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)
    con.executescript(
        """
        CREATE TABLE IF NOT EXISTS artifact_day (
          name TEXT PRIMARY KEY,
          archived_at TEXT NOT NULL,
          tarball TEXT,
          sha256 TEXT,
          tar_bytes INTEGER,
          file_count INTEGER,
          kept_count INTEGER,
          source_bytes INTEGER
        );
        CREATE TABLE IF NOT EXISTS report (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          day TEXT NOT NULL,
          rel_path TEXT NOT NULL,
          kind TEXT,
          pass INTEGER,
          fw TEXT,
          payload_json TEXT,
          UNIQUE(day, rel_path)
        );
        """
    )
    return con


def distill_report(path: Path) -> dict[str, Any] | None:
    try:
        if path.suffix.lower() != ".json":
            if path.suffix.lower() == ".md":
                text = path.read_text(encoding="utf-8", errors="replace")[:4000]
                return {
                    "kind": "markdown",
                    "pass": None,
                    "fw": None,
                    "payload": {"head": text[:500], "bytes": path.stat().st_size},
                }
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None

    name = path.name.lower()
    payload: dict[str, Any] = {}
    passed = None
    fw = None
    kind = "json"

    if "a1-report" in name or name == "report.json":
        kind = "a1" if "a1" in name else "report"
        passed = data.get("pass")
        sel = data.get("selection") or {}
        pref = data.get("prefetch") or {}
        payload = {
            "selection": sel.get("class"),
            "gate_green": sel.get("gate_green"),
            "stall_armed": sel.get("stall_armed"),
            "prefetch_coverage": pref.get("coverage_pct"),
            "prefetch_classes": pref.get("classes"),
        }
        st = data.get("status_final") or data.get("status_initial") or {}
        fw = st.get("version")
    elif "identity" in name:
        kind = "identity"
        passed = data.get("pass")
        payload = {
            "dimension": data.get("dimension"),
            "changed_fields": data.get("changed_fields"),
            "one_dimension_only": data.get("one_dimension_only"),
        }
    elif name == "summary.json":
        kind = "summary"
        b = (data.get("stufe_B") or {}) if isinstance(data, dict) else {}
        ev = b.get("eval") or {}
        passed = b.get("pass")
        payload = {"eval": ev, "mode": data.get("mode")}
    else:
        # generic small json
        if path.stat().st_size > 200_000:
            return {
                "kind": "json_large_skipped",
                "pass": None,
                "fw": None,
                "payload": {"bytes": path.stat().st_size},
            }
        payload = {"keys": sorted(list(data.keys()))[:40] if isinstance(data, dict) else []}
        passed = data.get("pass") if isinstance(data, dict) else None

    return {"kind": kind, "pass": passed, "fw": fw, "payload": payload}


def day_date(name: str) -> dt.date | None:
    m = DAY_RE.match(name)
    if not m:
        return None
    return dt.date.fromisoformat(m.group(1))


def archive_one(day_dir: Path, root: Path, apply: bool, dry: bool) -> dict[str, Any]:
    if not day_dir.is_dir():
        raise FileNotFoundError(day_dir)
    name = day_dir.name
    ar = archive_root(root)
    kept_root = ar / "kept" / name
    roh_dir = ar / "roh"
    roh_dir.mkdir(parents=True, exist_ok=True)
    tar_path = roh_dir / f"{name}.tar.gz"
    db_path = ar / "index.sqlite"

    files = list(iter_files(day_dir))
    source_bytes = sum(p.stat().st_size for p in files)
    keep_rels: list[Path] = []
    for path in files:
        rel = path.relative_to(day_dir)
        if should_keep(rel):
            keep_rels.append(rel)

    result: dict[str, Any] = {
        "day": name,
        "files": len(files),
        "kept": len(keep_rels),
        "source_bytes": source_bytes,
        "tar": str(tar_path.relative_to(root)),
        "apply": apply,
        "dry": dry,
    }

    if dry:
        print(json.dumps(result, indent=2))
        return result

    # 1) tar entire day (self-contained restore)
    if tar_path.exists():
        tar_path.unlink()
    with tarfile.open(tar_path, "w:gz") as tar:
        tar.add(day_dir, arcname=name)
    digest = sha256_file(tar_path)
    tar_bytes = tar_path.stat().st_size

    # 2) kept tree (reports only)
    if kept_root.exists():
        shutil.rmtree(kept_root)
    for rel in keep_rels:
        src = day_dir / rel
        dst = kept_root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

    # 3) index
    con = ensure_db(db_path)
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    con.execute(
        """
        INSERT INTO artifact_day(name, archived_at, tarball, sha256, tar_bytes, file_count, kept_count, source_bytes)
        VALUES(?,?,?,?,?,?,?,?)
        ON CONFLICT(name) DO UPDATE SET
          archived_at=excluded.archived_at,
          tarball=excluded.tarball,
          sha256=excluded.sha256,
          tar_bytes=excluded.tar_bytes,
          file_count=excluded.file_count,
          kept_count=excluded.kept_count,
          source_bytes=excluded.source_bytes
        """,
        (
            name,
            now,
            str(tar_path.relative_to(root)),
            digest,
            tar_bytes,
            len(files),
            len(keep_rels),
            source_bytes,
        ),
    )
    for rel in keep_rels:
        distilled = distill_report(kept_root / rel)
        if not distilled:
            continue
        con.execute(
            """
            INSERT INTO report(day, rel_path, kind, pass, fw, payload_json)
            VALUES(?,?,?,?,?,?)
            ON CONFLICT(day, rel_path) DO UPDATE SET
              kind=excluded.kind,
              pass=excluded.pass,
              fw=excluded.fw,
              payload_json=excluded.payload_json
            """,
            (
                name,
                str(rel).replace("\\", "/"),
                distilled["kind"],
                None
                if distilled["pass"] is None
                else (1 if distilled["pass"] else 0),
                distilled.get("fw"),
                json.dumps(distilled.get("payload") or {}, ensure_ascii=False),
            ),
        )
    con.commit()
    con.close()

    # 4) replace hot dir with stub
    if apply:
        stub = day_dir  # replace in place
        # move aside then write stub folder
        tmp = day_dir.with_name(day_dir.name + ".ARCHIVE_TMP")
        if tmp.exists():
            shutil.rmtree(tmp)
        day_dir.rename(tmp)
        stub.mkdir(parents=True)
        rel_kept = kept_root.relative_to(root)
        rel_tar = tar_path.relative_to(root)
        kept_list = "\n".join(f"- `{p.as_posix()}`" for p in keep_rels[:80])
        if len(keep_rels) > 80:
            kept_list += f"\n- … +{len(keep_rels) - 80} weitere"
        (stub / "README.md").write_text(
            f"""# Archiviert: `{name}`

Dieses Hot-Verzeichnis wurde am {now[:10]} nach
[`docs/archiv/ARTIFACTS-POLICY.md`](../../archiv/ARTIFACTS-POLICY.md) ausgelagert.

| | Pfad |
|--|--|
| Berichte (kept) | [`{rel_kept}`](../../archiv/betrieb-artifacts/kept/{name}/) |
| Rohdaten (tar.gz) | [`{rel_tar}`](../../archiv/betrieb-artifacts/roh/{name}.tar.gz) |
| Index | [`docs/archiv/betrieb-artifacts/index.sqlite`](../../archiv/betrieb-artifacts/index.sqlite) |

SHA-256 Tar: `{digest}` · {tar_bytes} Bytes · {len(files)} Dateien → {len(keep_rels)} kept

## Kept (Auszug)

{kept_list or '_keine keep-Treffer_'}

Restore Rohdaten:

```bash
tar -xzf {rel_tar} -C /tmp
```
""",
            encoding="utf-8",
        )
        shutil.rmtree(tmp)

    result.update(
        {
            "sha256": digest,
            "tar_bytes": tar_bytes,
            "kept_root": str(kept_root.relative_to(root)),
        }
    )
    print(json.dumps(result, indent=2))
    return result


def list_days(betrieb: Path, before: str | None) -> list[Path]:
    cutoff = dt.date.fromisoformat(before) if before else None
    days = []
    for path in sorted(betrieb.glob("artifacts-20*")):
        if not path.is_dir():
            continue
        d = day_date(path.name)
        if d is None:
            continue
        if cutoff and d >= cutoff:
            continue
        days.append(path)
    return days


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--day", type=Path, help="single artifacts-* directory")
    ap.add_argument("--before", help="archive all artifact days with date < YYYY-MM-DD")
    ap.add_argument("--apply", action="store_true", help="replace hot dir with stub README")
    ap.add_argument("--dry", action="store_true", help="only print plan")
    args = ap.parse_args()
    root = repo_root()
    betrieb = root / "docs" / "betrieb"

    targets: list[Path] = []
    if args.day:
        day = args.day if args.day.is_absolute() else root / args.day
        targets = [day]
    elif args.before:
        targets = list_days(betrieb, args.before)
    else:
        ap.error("need --day or --before")

    if not targets:
        print("no matching days")
        return 1

    # write/update archive README
    ar = archive_root(root)
    ar.mkdir(parents=True, exist_ok=True)
    readme = ar / "README.md"
    if not readme.exists():
        readme.write_text(
            "# Betrieb-Artefakte (Archiv)\n\n"
            "Siehe [`../ARTIFACTS-POLICY.md`](../ARTIFACTS-POLICY.md).\n\n"
            "- `kept/` — Berichte\n"
            "- `roh/*.tar.gz` — vollständige Tagesordner\n"
            "- `index.sqlite` — Metadaten / PASS-Index\n",
            encoding="utf-8",
        )

    for day in targets:
        # skip if already only stub (single README)
        kids = [p for p in day.iterdir()] if day.is_dir() else []
        if (
            day.is_dir()
            and len(kids) == 1
            and kids[0].name == "README.md"
            and "Archiviert:" in kids[0].read_text(encoding="utf-8", errors="replace")
        ):
            print(json.dumps({"day": day.name, "skipped": "already_stub"}))
            continue
        archive_one(day, root, apply=args.apply and not args.dry, dry=args.dry)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
