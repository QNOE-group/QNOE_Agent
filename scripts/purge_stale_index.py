#!/usr/bin/env python3
"""Purge stale-junk rows from the ingestion index (manifest + Qdrant).

Removes files that should never have been indexed — bundled Python envs,
notebook checkpoints, PyInstaller hooks — but that predate the watcher's
exclusion rules (config/watcher.yaml) and so linger in the index. The watcher
skips them on new scans; nightly orphan-cleanup won't remove them because the
files still exist on disk. Result: they pollute both find_file and RAG.

Rules are **slash-bounded directory segments** (a real directory in the path),
NEVER a bare word — so a legit file like `data_copy.xlsx` is never matched.
Keep RULES in sync with config/watcher.yaml and qnoe_files._EXCLUDE_SUBSTRINGS.

Usage (as qnoe-ai or yzamir on the DGX; Qdrant on localhost:6333):
    python scripts/purge_stale_index.py --dry-run   # count + safety scan, no writes
    python scripts/purge_stale_index.py             # execute (back up first!)

Back up the manifest DBs before executing (Qdrant has nightly snapshots):
    cp <manifest>.db <manifest>.db.bak-pre-purge
"""
import argparse
import json
import os
import sqlite3

RULES = [
    "/.ipynb_checkpoints/", "/site-packages/", "/venv/", "/.venv/",
    "/__pycache__/", "/node_modules/", "/PyInstaller/", "/_pyinstaller/",
    "/Personal/Sergi/QTM - Copy/",
]
DATA_EXT = (".db", ".pptx", ".ppt", ".docx", ".doc", ".pdf", ".xlsx", ".xls",
            ".h5", ".mat", ".csv")
MANIFEST_DBS = [
    os.environ.get("SERVER_MANIFEST_DB", "/home/yzamir/qnoe_server_data/episodic.db"),
    os.environ.get("REPO_MANIFEST_DB", "/opt/qnoe-agent/memory/episodic.db"),
]
QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6333")


def is_junk(path: str) -> bool:
    return any(seg in path for seg in RULES)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="count only, no writes")
    args = ap.parse_args()

    qc = None
    if not args.dry_run:
        from qdrant_client import QdrantClient
        qc = QdrantClient(url=QDRANT_URL)

    for db in MANIFEST_DBS:
        if not os.path.exists(db):
            continue
        con = sqlite3.connect(db, timeout=60)
        rows = con.execute(
            "SELECT file_path, collection, point_ids FROM index_manifest"
        ).fetchall()
        junk = [(fp, col, pids) for (fp, col, pids) in rows if is_junk(fp)]
        name = os.path.basename(db)
        print(f"\n=== {name}: total={len(rows)} DELETE={len(junk)} keep={len(rows)-len(junk)} ===")
        for seg in RULES:
            n = sum(1 for fp, _, _ in junk if seg in fp)
            if n:
                print(f"  {seg}: {n}")
        sus = [fp for fp, _, _ in junk if fp.lower().endswith(DATA_EXT)]
        print(f"  -- SAFETY: {len(sus)} data-type file(s) among matches")
        for fp in sus[:6]:
            print("       ", fp[-95:])
        if args.dry_run:
            con.close()
            continue

        # delete Qdrant points, grouped by collection
        bycol: dict[str, list] = {}
        for fp, col, pids in junk:
            try:
                ids = json.loads(pids) if pids else []
            except Exception:
                ids = []
            bycol.setdefault(col or "group-wide", []).extend(i for i in ids if i)
        from qdrant_client import models as M
        for col, ids in bycol.items():
            for k in range(0, len(ids), 500):
                qc.delete(col, points_selector=M.PointIdsList(points=ids[k:k+500]))
            print(f"  Qdrant: deleted {len(ids)} points from '{col}'")

        # delete manifest rows
        fps = [fp for fp, _, _ in junk]
        for k in range(0, len(fps), 500):
            b = fps[k:k+500]
            con.execute(
                f"DELETE FROM index_manifest WHERE file_path IN ({','.join('?'*len(b))})",
                b,
            )
        con.commit()
        after = con.execute("SELECT COUNT(*) FROM index_manifest").fetchone()[0]
        con.close()
        print(f"  manifest rows now: {after}")

    print("\nDONE" + (" (dry-run — no changes)" if args.dry_run else ""))


if __name__ == "__main__":
    main()
