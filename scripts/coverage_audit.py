#!/usr/bin/env python3
"""Coverage audit — the standing check for SILENT index gaps.

For each top-level server folder it compares:
  * PRESENT  = indexable docs on the server (via the broad /mnt/noe mount,
               same extension + exclusion rules as the ingest), and
  * INDEXED  = rows in the manifest under the canonical /ICFO path,
and flags folders indexed below --min-coverage.

This catches BOTH gap classes that silently starved the corpus for months
(see memory/mistakes M56):
  * ACL-denied folders — never scanned via /ICFO (e.g. Theses & reports: 19
    indexed of 3,345 present), and
  * find-timeout-truncated folders — readable but the old 300s `find` cap
    returned a fraction (e.g. Manuscripts: 311 of 5,450).
Both "succeeded" with no error. Only a present-vs-indexed reconciliation shows it.

PRESENT is read from the cached find-manifest (cheap); --refresh re-runs the
un-timed find. Run alongside the nightly (posts a line) or on demand:
  PYTHONPATH=/opt/qnoe-agent AGENT_DATA_DIR=/home/yzamir/qnoe_server_data \
    /opt/qnoe-agent/venv/bin/python -m scripts.coverage_audit   # or python scripts/coverage_audit.py
"""
import argparse
import json
import os
import sqlite3
import sys
from collections import Counter
from pathlib import Path

# Allow running both as a module and as a bare script.
try:
    from agent.ingest.ingest_server import SERVER_FOLDERS
    from agent.ingest.run_ingest import _find_files
except ModuleNotFoundError:
    sys.path.insert(0, os.environ.get("QNOE_ROOT", "/opt/qnoe-agent"))
    from agent.ingest.ingest_server import SERVER_FOLDERS
    from agent.ingest.run_ingest import _find_files

SERVER_ROOT = Path(os.environ.get("SERVER_ROOT", "/mnt/noe"))
STORE_ROOT = os.environ.get("INGEST_STORE_ROOT", "/ICFO/groups/NOE").rstrip("/")
AGENT_DATA_DIR = os.environ.get("AGENT_DATA_DIR", "/home/yzamir/qnoe_server_data")
MANIFEST_DB = os.path.join(AGENT_DATA_DIR, "episodic.db")
FIND_CACHE = Path(os.environ.get("FIND_CACHE", os.path.join(AGENT_DATA_DIR, "full_scan_filelist.txt")))


def present_by_folder(refresh: bool) -> Counter:
    """Indexable docs present per top-level folder (from the find-cache, or a
    fresh un-timed find of the allowlist minus EXCLUDE_FOLDERS)."""
    if FIND_CACHE.exists() and not refresh:
        paths = [x for x in FIND_CACHE.read_text().splitlines() if x.strip()]
        c = Counter()
        for p in paths:
            try:
                c[Path(p).relative_to(SERVER_ROOT).parts[0]] += 1
            except Exception:
                pass
        return c
    excluded = {f.strip() for f in os.environ.get("EXCLUDE_FOLDERS", "").split(",") if f.strip()}
    c = Counter()
    for folder in SERVER_FOLDERS:
        if folder in excluded:
            continue
        fp = SERVER_ROOT / folder
        if fp.exists():
            c[folder] = len(_find_files(fp))
    return c


def indexed_by_folder() -> Counter:
    """Manifest rows per top-level folder under the canonical STORE_ROOT."""
    c = Counter()
    conn = sqlite3.connect(MANIFEST_DB)
    try:
        cur = conn.execute("SELECT file_path FROM index_manifest WHERE file_path LIKE ?",
                           (STORE_ROOT + "/%",))
        pre = len(STORE_ROOT) + 1
        for (fp,) in cur:
            rel = fp[pre:]
            if "/" in rel:
                c[rel.split("/", 1)[0]] += 1
    finally:
        conn.close()
    return c


def audit(refresh: bool, min_cov: float) -> dict:
    present = present_by_folder(refresh)
    indexed = indexed_by_folder()
    rows = []
    for folder in sorted(set(present) | set(indexed)):
        p = present.get(folder, 0)
        i = indexed.get(folder, 0)
        cov = (i / p) if p else None                 # None = nothing present to index
        gapped = p > 0 and (cov is None or cov < min_cov)
        rows.append({"folder": folder, "present": p, "indexed": i,
                     "coverage": round(cov, 3) if cov is not None else None,
                     "gap": bool(gapped)})
    rows.sort(key=lambda r: (not r["gap"], -(r["present"] - r["indexed"])))
    gapped = [r for r in rows if r["gap"]]
    return {"rows": rows, "gapped": gapped, "min_coverage": min_cov,
            "total_present": sum(present.values()), "total_indexed": sum(indexed.values())}


def summary_line(res: dict) -> str:
    g = res["gapped"]
    if not g:
        return f"Coverage audit: all folders >= {int(res['min_coverage']*100)}% indexed ✅ ({res['total_indexed']}/{res['total_present']})"
    worst = "; ".join(f"{r['folder']} {r['indexed']}/{r['present']}" for r in g[:4])
    return f"Coverage audit: ⚠️ {len(g)} folder(s) under {int(res['min_coverage']*100)}% — {worst}"


def main(argv) -> int:
    ap = argparse.ArgumentParser(description="Server index coverage audit")
    ap.add_argument("--refresh", action="store_true", help="re-run the un-timed find instead of the cache")
    ap.add_argument("--min-coverage", type=float, default=float(os.environ.get("MIN_COVERAGE", "0.8")))
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--line", action="store_true")
    args = ap.parse_args(argv)
    res = audit(args.refresh, args.min_coverage)
    if args.json:
        print(json.dumps({**res, "summary": summary_line(res),
                          "present_source": "find" if args.refresh else str(FIND_CACHE)}))
    elif args.line:
        print(summary_line(res))
    else:
        print(f"{'folder':<22}{'present':>9}{'indexed':>9}{'cover':>8}")
        for r in res["rows"]:
            cov = "n/a" if r["coverage"] is None else f"{int(r['coverage']*100)}%"
            flag = "  <-- GAP" if r["gap"] else ""
            print(f"{r['folder']:<22}{r['present']:>9}{r['indexed']:>9}{cov:>8}{flag}")
        print("\n" + summary_line(res))
    return 1 if res["gapped"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
