#!/usr/bin/env python3
"""Targeted SharePoint re-ingest driven by a missing-files manifest.

Closes the gap found by scripts/sharepoint_coverage_audit.py (2026-07-16):
~11.7K noe-group files silently unindexed because chunk-timeout / OOM-crashed
/ zero-chunk files write no manifest row and no failure record, and the delta
poller never revisits unchanged items (fail-once = fail-forever).

Two modes:

  --build    Diff the full-sync listing cache (JSONL, kept from the Jul-8 run
             via --keep-cache) against sp_manifest and write the missing items
             to a work-list manifest (default logs/sp_missing_manifest.jsonl).
             Plot-export PDFs (numeric names under .../pdf/) and manuscript
             figure PDFs are EXCLUDED by default — they carry no text and
             mostly re-fail; --include-plots overrides.

  --execute  Feed every manifest item back through sharepoint_sync's
             _process_item (download -> chunk -> embed -> upsert -> record),
             smallest files first, with a bounded thread pool and the sync's
             own memory guard. Etag dedup makes re-runs resume instantly.
             Ends with a reconciliation: attempted items still absent from
             sp_manifest are written to logs/sp_reingest_failed.txt — this
             run's failures are NOT silent.

Env knobs (read by sharepoint_sync/splitter at import):
  SP_FILE_CHUNK_TIMEOUT  per-file chunk cap, default 300 — raise to 1800 here
  SP_THREAD_WORKERS      concurrent items (keep small, Docling spikes RAM)
  SP_MIN_FREE_GB         memory-guard floor (default 20)
  PDF_TEXTLAYER_FAST=1   born-digital PDFs via pypdf (fast), scanned skipped

Run as yzamir (same uid as the watcher/nightly manifest writers — no
cross-UID WAL side-files, see mistakes M52) with the SharePoint creds
sourced from secrets/sharepoint.env (group-readable). See
scripts/run_sp_manifest_reingest.sh for the gated launcher.
"""
import argparse
import json
import logging
import os
import re
import sqlite3
import sys
import time
from collections import Counter
from pathlib import Path

logger = logging.getLogger("sp_manifest_reingest")

QNOE_ROOT = os.environ.get("QNOE_ROOT", "/opt/qnoe-agent")
sys.path.insert(0, QNOE_ROOT)

SP_MANIFEST_DB = os.environ.get("SP_MANIFEST_DB", f"{QNOE_ROOT}/memory/sharepoint.db")
DEFAULT_CACHE = ("/tmp/qnoe-sp-listing-cache/"
                 "b_6T8n2h74TUuwrCDNas_S6aIAyKOIvEJCshcZSSKGoTlNllfV.jsonl")
DEFAULT_MANIFEST = f"{QNOE_ROOT}/logs/sp_missing_manifest.jsonl"
FAILED_LIST = f"{QNOE_ROOT}/logs/sp_reingest_failed.txt"

# Mirror sharepoint_sync's filters (present = "the sync should index it")
SUPPORTED_EXTENSIONS = {".py", ".ipynb", ".md", ".rst", ".pdf", ".pptx", ".docx"}
EXCLUDE_PATH_SUBSTRINGS = {".env/", "/venv/", "site-packages/", "node_modules/", "__pycache__/"}

_NUMPLOT = re.compile(r"^\d+(_\d+)?\.pdf$")


def _item_path(item: dict) -> str:
    """Verbatim from sharepoint_sync._item_path — must match manifest rows."""
    parent_path = item.get("parentReference", {}).get("path", "")
    if "root:" in parent_path:
        parent_path = parent_path.split("root:", 1)[1].lstrip("/")
    return f"{parent_path}/{item['name']}".lstrip("/") if parent_path else item["name"]


def _is_plot_class(rel: str, ext: str) -> bool:
    """Class A from the 2026-07-17 forensics: QCoDeS notebook plot exports and
    manuscript figure PDFs — no text layer, near-zero retrieval value."""
    if ext != ".pdf":
        return False
    base = rel.rsplit("/", 1)[-1]
    if "/pdf/" in rel or _NUMPLOT.match(base):
        return True
    return "figure" in rel.lower() or base.lower().startswith("fig")


def build(cache: str, site: str, out: str, max_mb: int, include_plots: bool) -> int:
    conn = sqlite3.connect(f"file:{SP_MANIFEST_DB}?mode=ro", uri=True)
    indexed = {p for (p,) in conn.execute(
        "SELECT item_path FROM sp_manifest WHERE site_name = ?", (site,))}
    conn.close()

    kept, skipped_class = [], Counter()
    with open(cache) as f:
        f.readline()  # metadata line
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if "file" not in item or "deleted" in item:
                continue
            ext = Path(item.get("name", "")).suffix.lower()
            if ext not in SUPPORTED_EXTENSIONS:
                continue
            if item.get("size", 0) > max_mb * 1024 * 1024:
                continue
            rel = _item_path(item)
            if any(s in rel for s in EXCLUDE_PATH_SUBSTRINGS):
                continue
            if rel in indexed:
                continue
            if not include_plots and _is_plot_class(rel, ext):
                skipped_class["plot/figure PDF (excluded)"] += 1
                continue
            kept.append(item)
            skipped_class[ext] += 1

    kept.sort(key=lambda it: it.get("size", 0))  # cheapest first
    with open(out, "w") as f:
        for item in kept:
            f.write(json.dumps(item) + "\n")

    total_mb = sum(it.get("size", 0) for it in kept) / 1048576
    print(f"manifest written: {out}")
    print(f"items: {len(kept)} ({total_mb:.0f} MB)   [excluded plot/figure: "
          f"{skipped_class.pop('plot/figure PDF (excluded)', 0)}]")
    for k, c in skipped_class.most_common():
        print(f"  {k:8} {c}")
    return 0


def execute(manifest_path: str, site: str) -> int:
    # Heavy imports (splitter/embed via sharepoint_sync) only in execute mode.
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from qdrant_client import QdrantClient
    from agent.ingest import sharepoint_sync as sp
    from agent.ingest.sharepoint_client import authenticate

    cfg = sp.load_sharepoint_config(None)
    site_cfgs = [s for s in cfg["sites"] if s["name"] == site]
    if not site_cfgs:
        logger.error("site %s not in sharepoint.yaml", site)
        return 2
    site_cfg = site_cfgs[0]
    temp_dir = Path(cfg.get("temp_dir", "/tmp/qnoe-sharepoint/"))

    items = []
    with open(manifest_path) as f:
        for line in f:
            if line.strip():
                items.append(json.loads(line))
    logger.info("manifest: %d items, timeout=%ss, workers=%s, min_free=%sGB, fast_pdf=%s",
                len(items), sp.FILE_CHUNK_TIMEOUT, sp.THREAD_WORKERS,
                sp.MIN_FREE_GB, os.environ.get("PDF_TEXTLAYER_FAST", "0"))

    token = authenticate(cfg["auth"])
    holder = sp._SharedToken(token, cfg["auth"])
    client = QdrantClient(url=sp.QDRANT_URL)
    logger.info("authentication OK")

    stats = Counter()
    attempted_paths = [_item_path(it) for it in items]

    def _run(item: dict) -> bool:
        drive_id = item.get("parentReference", {}).get("driveId", "")
        return sp._process_item(item, site_cfg, drive_id, temp_dir, holder, client)

    # Bounded sliding window (full_sync pattern) + the sync's memory guard.
    MAX_QUEUED = sp.THREAD_WORKERS * 2
    it = iter(items)
    pending: dict = {}
    done = 0
    with ThreadPoolExecutor(max_workers=sp.THREAD_WORKERS) as pool:
        def _fill() -> None:
            while len(pending) < MAX_QUEUED:
                if not sp._memory_ok():
                    logger.warning("memory guard active — pausing submissions 60s")
                    time.sleep(60)
                    continue
                try:
                    item = next(it)
                except StopIteration:
                    return
                pending[pool.submit(_run, item)] = item

        _fill()
        while pending:
            for fut in as_completed(pending):
                item = pending.pop(fut)
                try:
                    stats["indexed" if fut.result() else "not_indexed"] += 1
                except Exception as exc:
                    logger.error("item error %s: %s", item.get("name", "?"), exc)
                    stats["error"] += 1
                done += 1
                if done % 25 == 0:
                    logger.info("progress %d/%d — %s", done, len(items), dict(stats))
                _fill()
                break

    # Reconciliation: what is STILL not in the manifest? (this run's failures,
    # made visible — the exact silence that created the original gap)
    conn = sqlite3.connect(f"file:{SP_MANIFEST_DB}?mode=ro", uri=True)
    indexed_now = {p for (p,) in conn.execute(
        "SELECT item_path FROM sp_manifest WHERE site_name = ?", (site,))}
    conn.close()
    still_missing = [p for p in attempted_paths if p not in indexed_now]
    with open(FAILED_LIST, "w") as f:
        f.write("\n".join(still_missing) + ("\n" if still_missing else ""))

    logger.info("DONE. attempted=%d indexed_result=%s still_missing=%d (list: %s)",
                len(items), dict(stats), len(still_missing), FAILED_LIST)
    print(f"RESULT attempted={len(items)} stats={dict(stats)} "
          f"still_missing={len(still_missing)} failed_list={FAILED_LIST}")
    return 0 if not still_missing else 1


def main(argv) -> int:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s",
                        datefmt="%Y-%m-%d %H:%M:%S")
    ap = argparse.ArgumentParser(description="Manifest-driven SharePoint re-ingest")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--build", action="store_true")
    mode.add_argument("--execute", action="store_true")
    ap.add_argument("--cache", default=DEFAULT_CACHE, help="full-sync listing cache JSONL")
    ap.add_argument("--site", default="noe-group")
    ap.add_argument("--manifest", default=DEFAULT_MANIFEST)
    ap.add_argument("--max-mb", type=int, default=300)
    ap.add_argument("--include-plots", action="store_true",
                    help="also re-attempt plot-export/figure PDFs (class A)")
    args = ap.parse_args(argv)

    if args.build:
        return build(args.cache, args.site, args.manifest, args.max_mb, args.include_plots)
    return execute(args.manifest, args.site)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
