"""Nightly maintenance runner for the QNOE lab agent.

Each task is a plain function registered in TASKS (bottom of this file).
Tasks run in order; a failure is logged but does not stop remaining tasks.

To add a new nightly task:
  1. Write  def task_<name>() -> None  — raise on failure, log progress via logger
  2. Append it to TASKS

Usage:
  python -m agent.indexing.nightly_run            # run all tasks
  python -m agent.indexing.nightly_run --dry-run  # print plan without executing
  python -m agent.indexing.nightly_run --task qdrant_snapshot  # run one task
"""
import argparse
import asyncio
import logging
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
import yaml

from agent.ingest.run_ingest import ingest_directory
from agent.ingest.qcodes_scanner import scan_roots as scan_qcodes, scan_specific_dbs

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config (all overridable via environment variables)
# ---------------------------------------------------------------------------

QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6333")
REPOS_DIR = Path(os.environ.get("REPOS_DIR", "/opt/qnoe-agent/repos"))
COLLECTIONS_CONFIG = Path(os.environ.get(
    "COLLECTIONS_CONFIG", "/opt/qnoe-agent/config/repo_collections.yaml"
))
SERVER_ROOT = Path(os.environ.get("SERVER_ROOT", "/ICFO/groups/NOE"))
SNAPSHOT_RETENTION_DAYS = int(os.environ.get("SNAPSHOT_RETENTION_DAYS", "7"))
# AGENT_DATA_DIR must match where ingest workers write their manifest DB.
# The server ingestion job uses /home/yzamir/qnoe_server_data; repo ingestion uses
# /opt/qnoe-agent/memory. Pass explicitly so the two jobs never share a manifest file.
AGENT_DATA_DIR = Path(os.environ.get("AGENT_DATA_DIR", "/opt/qnoe-agent/memory"))
SERVER_DATA_DIR = Path(os.environ.get("SERVER_DATA_DIR", "/home/yzamir/qnoe_server_data"))

SERVER_FOLDERS = [
    "Lab_Instruments", "Manuscripts", "Meetings", "Notebook", "Notebooks",
    "Papers & Books", "Posters", "Presentation", "Presentations", "Projects",
    "Spectromag", "Theses & reports",
]


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------

def task_qdrant_snapshot() -> None:
    """Snapshot all Qdrant collections; prune snapshots older than SNAPSHOT_RETENTION_DAYS."""
    resp = requests.get(f"{QDRANT_URL}/collections", timeout=10)
    resp.raise_for_status()
    collections = [c["name"] for c in resp.json()["result"]["collections"]]
    logger.info("Snapshotting %d collections: %s", len(collections), collections)

    for col in collections:
        r = requests.post(f"{QDRANT_URL}/collections/{col}/snapshots", timeout=60)
        r.raise_for_status()
        logger.info("  created snapshot: %s", col)

    # Prune snapshots older than retention window
    cutoff = datetime.now(timezone.utc) - timedelta(days=SNAPSHOT_RETENTION_DAYS)
    for col in collections:
        r = requests.get(f"{QDRANT_URL}/collections/{col}/snapshots", timeout=10)
        r.raise_for_status()
        for snap in r.json()["result"]:
            raw = snap["creation_time"]
            created = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            if created < cutoff:
                name = snap["name"]
                requests.delete(
                    f"{QDRANT_URL}/collections/{col}/snapshots/{name}", timeout=10
                ).raise_for_status()
                logger.info("  pruned old snapshot: %s / %s", col, name)


def task_index_repos() -> None:
    """Incremental re-index of all cloned GitHub repos (skips unchanged files)."""
    if not REPOS_DIR.exists():
        raise FileNotFoundError(f"Repos directory not found: {REPOS_DIR}")
    if not COLLECTIONS_CONFIG.exists():
        raise FileNotFoundError(f"Collections config not found: {COLLECTIONS_CONFIG}")

    with open(COLLECTIONS_CONFIG) as f:
        config = yaml.safe_load(f)

    excluded = set(config.get("exclude", []))
    repos = sorted(d for d in REPOS_DIR.iterdir() if d.is_dir() and not d.name.startswith("."))
    repos = [r for r in repos if r.name not in excluded]
    logger.info("Re-indexing %d repos", len(repos))

    for repo in repos:
        collection = _resolve_collection(repo.name, config)
        logger.info("  %s -> %s", repo.name, collection)
        ingest_directory(
            team=collection, repo_path=repo, repo_name=repo.name, force=False, dry_run=False,
            manifest_db=str(AGENT_DATA_DIR / "episodic.db"),
        )


def task_index_server() -> None:
    """Incremental re-index of NOE server documents (skips unchanged files)."""
    if not SERVER_ROOT.exists():
        raise FileNotFoundError(f"Server not mounted: {SERVER_ROOT}")
    logger.info("Re-indexing server docs (%d folders)", len(SERVER_FOLDERS))

    for folder_name in SERVER_FOLDERS:
        folder = SERVER_ROOT / folder_name
        if not folder.exists():
            logger.warning("  folder not found, skipping: %s", folder)
            continue
        logger.info("  %s", folder_name)
        ingest_directory(
            team="group-wide", repo_path=folder, repo_name=folder_name, force=False, dry_run=False,
            manifest_db=str(SERVER_DATA_DIR / "episodic.db"),
        )


# ---------------------------------------------------------------------------
# Task registry — append here to add new nightly tasks
# ---------------------------------------------------------------------------

def task_sync_sharepoint() -> None:
    """Full SharePoint sync as nightly safety net. Catches any missed delta events."""
    try:
        from agent.ingest.sharepoint_sync import (
            load_sharepoint_config,
            full_sync,
        )
        from agent.ingest.sharepoint_client import authenticate
    except ImportError as exc:
        logger.warning("SharePoint sync skipped — missing dependency: %s", exc)
        return

    sp_config_path = os.environ.get(
        "SHAREPOINT_CONFIG", "/opt/qnoe-agent/config/sharepoint.yaml"
    )
    if not Path(sp_config_path).exists():
        logger.info("SharePoint sync skipped — %s not found", sp_config_path)
        return

    # Load credentials from secrets file if not already in environment
    sp_env_file = Path("/opt/qnoe-agent/secrets/sharepoint.env")
    if sp_env_file.exists():
        for line in sp_env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())

    cfg = load_sharepoint_config(sp_config_path)
    token = authenticate(cfg["auth"])

    for site in cfg.get("sites", []):
        logger.info("SP full sync (nightly): %s", site["name"])
        stats = full_sync(site, cfg, token)
        logger.info("SP nightly done for %s: %s", site["name"], stats)


def task_scan_qcodes() -> None:
    """Scan for QCoDeS databases and update registry + qcodes-runs collection."""
    roots = []
    if REPOS_DIR.exists():
        roots.append(REPOS_DIR)
    # Server mount guard — same as task_orphan_cleanup
    mount_marker = SERVER_ROOT / "Group_Manual.txt"
    if mount_marker.exists():
        roots.append(SERVER_ROOT)
    else:
        logger.warning("Server mount not available — scanning repos only")
    if not roots:
        raise FileNotFoundError("No scan roots available")
    logger.info("Scanning %d roots for QCoDeS databases", len(roots))
    stats = asyncio.run(scan_qcodes(roots))
    logger.info(
        "QCoDeS scan: %d DBs found, %d skipped, %d new runs, %d cards upserted",
        stats["dbs_found"], stats["dbs_skipped"],
        stats["new_runs"], stats["cards_upserted"],
    )


def task_process_change_queue() -> None:
    """Process stable entries from the watcher's change_queue.

    Handles doc files via ingest_directory (single-file mode) and .db files
    via scan_specific_dbs. Marks entries as processed when done.
    """
    import sqlite3 as _sqlite3
    from agent.watcher.file_cache import get_pending_queue, mark_processed, init_schema

    watcher_db = os.environ.get("WATCHER_DB", "/opt/qnoe-agent/memory/watcher.db")
    if not Path(watcher_db).exists():
        logger.info("Watcher DB not found (%s) — skipping", watcher_db)
        return

    conn = _sqlite3.connect(watcher_db)
    conn.execute("PRAGMA journal_mode=WAL")
    init_schema(conn)

    pending = get_pending_queue(conn, only_stable=True)
    if not pending:
        logger.info("Change queue: no stable entries to process")
        conn.close()
        return

    logger.info("Change queue: %d stable entries to process", len(pending))

    doc_exts = {".pdf", ".docx", ".pptx", ".md", ".txt", ".rst", ".py", ".ipynb"}
    db_exts = {".db"}

    # Split into docs vs databases
    doc_entries = [e for e in pending if e["ext"] in doc_exts and e["change_type"] != "deleted"]
    db_entries = [e for e in pending if e["ext"] in db_exts and e["change_type"] != "deleted"]
    deleted_entries = [e for e in pending if e["change_type"] == "deleted"]

    # Process doc files
    processed_ids: list[int] = []
    if doc_entries:
        doc_paths = [Path(e["file_path"]) for e in doc_entries if Path(e["file_path"]).exists()]
        if doc_paths:
            logger.info("Ingesting %d doc files from change queue", len(doc_paths))
            ingest_directory(
                team="group-wide",
                repo_path=Path("/"),
                repo_name="server-watcher",
                force=True,
                dry_run=False,
                file_list=doc_paths,
                manifest_db=str(SERVER_DATA_DIR / "episodic.db"),
            )
        processed_ids.extend(e["id"] for e in doc_entries)

    # Process .db files
    if db_entries:
        db_paths = [Path(e["file_path"]) for e in db_entries if Path(e["file_path"]).exists()]
        if db_paths:
            logger.info("Scanning %d QCoDeS databases from change queue", len(db_paths))
            asyncio.run(scan_specific_dbs(db_paths))
        processed_ids.extend(e["id"] for e in db_entries)

    # Mark deleted entries as processed (orphan_cleanup handles Qdrant removal)
    processed_ids.extend(e["id"] for e in deleted_entries)

    mark_processed(conn, processed_ids)
    conn.close()
    logger.info("Change queue: processed %d entries", len(processed_ids))


def task_orphan_cleanup() -> None:
    """Remove Qdrant chunks for files missing from disk for 7+ days."""
    from agent.ingest.run_ingest import sweep_orphans

    # Repo manifest (local disk — always available)
    repo_db = str(AGENT_DATA_DIR / "episodic.db")
    stats = sweep_orphans(repo_db, QDRANT_URL)
    logger.info("Repo orphan sweep: %s", stats)

    # Server manifest — only if mount is live
    mount_marker = SERVER_ROOT / "Group_Manual.txt"
    if mount_marker.exists():
        server_db = str(SERVER_DATA_DIR / "episodic.db")
        stats = sweep_orphans(server_db, QDRANT_URL)
        logger.info("Server orphan sweep: %s", stats)
    else:
        logger.warning("Server mount not available — skipping server orphan sweep")


TASKS: list = [
    task_qdrant_snapshot,
    task_index_repos,
    task_sync_sharepoint,
    task_process_change_queue,
    task_orphan_cleanup,
]


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def _resolve_collection(repo_name: str, config: dict) -> str:
    repo_lower = repo_name.lower()
    for collection, patterns in config.get("collections", {}).items():
        for pattern in patterns:
            if pattern.lower() in repo_lower:
                return collection
    return config.get("default", "group-wide")


def run(dry_run: bool = False, only_task: str | None = None) -> int:
    """Run registered tasks in order. Returns number of failures."""
    tasks = TASKS
    if only_task:
        # Accept both 'task_qdrant_snapshot' and 'qdrant_snapshot'
        needle = only_task if only_task.startswith("task_") else f"task_{only_task}"
        tasks = [t for t in TASKS if t.__name__ == needle]
        if not tasks:
            logger.error(
                "Unknown task: %s. Available: %s",
                only_task,
                [t.__name__ for t in TASKS],
            )
            return 1

    logger.info("=" * 60)
    logger.info("Nightly run start — %s UTC", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))
    logger.info("Tasks queued: %s", [t.__name__ for t in tasks])

    if dry_run:
        logger.info("[dry-run] No tasks executed.")
        return 0

    failures = 0
    for task in tasks:
        logger.info("-" * 40)
        logger.info("START  %s", task.__name__)
        t0 = time.monotonic()
        try:
            task()
            logger.info("OK     %s  (%.1fs)", task.__name__, time.monotonic() - t0)
        except Exception as exc:
            logger.error(
                "FAIL   %s  (%.1fs): %s",
                task.__name__, time.monotonic() - t0, exc,
                exc_info=True,
            )
            failures += 1

    logger.info("=" * 60)
    logger.info(
        "Nightly run done — %d/%d tasks succeeded.", len(tasks) - failures, len(tasks)
    )
    return failures


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    parser = argparse.ArgumentParser(description="QNOE nightly maintenance runner")
    parser.add_argument("--dry-run", action="store_true", help="Print plan without executing")
    parser.add_argument("--task", default=None, metavar="NAME", help="Run only this task")
    args = parser.parse_args()

    sys.exit(min(run(dry_run=args.dry_run, only_task=args.task), 1))


if __name__ == "__main__":
    main()
