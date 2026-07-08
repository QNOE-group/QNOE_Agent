"""QCoDeS database scanner — dedicated qcodes-runs collection + registry.

Scans directories for QCoDeS .db files, extracts measurement run metadata,
and maintains:
  1. A `qcodes-runs` Qdrant collection with summary cards (for RAG)
  2. A `qcodes_registry` SQLite table (structured discovery index for B3)
  3. A `qcodes_db_hashes` SQLite table (file-level skip logic)

Usage:
  python -m agent.ingest.qcodes_scanner                    # scan default roots
  python -m agent.ingest.qcodes_scanner --dry-run           # discover without writing
  python -m agent.ingest.qcodes_scanner --root /path/to/dir # scan specific root
"""
import argparse
import asyncio
import hashlib
import json
import logging
import os
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    PointStruct,
    SparseIndexParams,
    SparseVector,
    SparseVectorParams,
    VectorParams,
)

from .embed import embed_documents, embed_sparse, VECTOR_DIM
from .excluded import find_prune_args

logger = logging.getLogger(__name__)

QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6333")
AGENT_DATA_DIR = os.environ.get("AGENT_DATA_DIR", "/opt/qnoe-agent/memory")
REPOS_DIR = Path(os.environ.get("REPOS_DIR", "/opt/qnoe-agent/repos"))
SERVER_ROOT = Path(os.environ.get("SERVER_ROOT", "/ICFO/groups/NOE"))

COLLECTION = "qcodes-runs"
UPSERT_BATCH = 100


# ---------------------------------------------------------------------------
# SQLite schema
# ---------------------------------------------------------------------------

def _init_db(db_path: str) -> sqlite3.Connection:
    """Open (or create) the manifest DB and ensure QCoDeS tables exist."""
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS qcodes_registry (
            id                  INTEGER PRIMARY KEY,
            db_path             TEXT    NOT NULL,
            run_id              INTEGER NOT NULL,
            exp_name            TEXT,
            sample_name         TEXT,
            run_name            TEXT,
            parameters          TEXT,
            completed_timestamp TEXT,
            description_json    TEXT,
            indexed_at          TEXT    NOT NULL,
            UNIQUE(db_path, run_id)
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_qcodes_registry_timestamp
        ON qcodes_registry(completed_timestamp)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_qcodes_registry_sample
        ON qcodes_registry(sample_name)
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS qcodes_db_hashes (
            id         INTEGER PRIMARY KEY,
            db_path    TEXT    NOT NULL UNIQUE,
            sha256     TEXT    NOT NULL,
            run_count  INTEGER NOT NULL,
            scanned_at TEXT    NOT NULL
        )
    """)
    conn.commit()
    return conn


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------

def _find_db_files(root: Path) -> list[Path]:
    """Find all .db files under root using OS `find` (CIFS-efficient)."""
    cmd = [
        "find", str(root),
        *find_prune_args(root),
        "-type", "f",
        "-name", "*.db",
        "!", "-path", "*/.git/*",
        "!", "-name", "~$*",
        "!", "-iname", "Thumbs.db",
        "-print",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return [Path(p) for p in result.stdout.splitlines() if p.strip()]


def _is_qcodes_db(path: Path) -> bool:
    """Check if a .db file is a QCoDeS database (has experiments + runs tables)."""
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5)
    except Exception:
        return False
    try:
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
        return {"experiments", "runs"}.issubset(tables)
    except Exception:
        return False
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Run extraction
# ---------------------------------------------------------------------------

def _extract_runs(db_path: Path) -> list[dict]:
    """Extract all measurement runs from a QCoDeS database.

    Returns list of dicts with keys:
        run_id, run_name, exp_name, sample_name, parameters,
        completed_timestamp, description_json
    """
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=5)
    except Exception as exc:
        logger.warning("Cannot open QCoDeS DB %s: %s", db_path, exc)
        return []

    conn.row_factory = sqlite3.Row
    runs = []
    try:
        rows = conn.execute("""
            SELECT r.run_id, r.name AS run_name, r.completed_timestamp,
                   r.run_description, e.name AS exp_name, e.sample_name
            FROM runs r
            JOIN experiments e ON r.exp_id = e.exp_id
        """).fetchall()

        for row in rows:
            # Extract parameter names from description JSON
            params = []
            desc_raw = row["run_description"] or "{}"
            try:
                desc = json.loads(desc_raw)
                paramspecs = (
                    desc.get("interdependencies", {}).get("paramspecs", [])
                    or desc.get("paramspecs", [])
                )
                params = [p["name"] for p in paramspecs if "name" in p]
            except Exception:
                pass

            runs.append({
                "run_id": row["run_id"],
                "run_name": row["run_name"] or "",
                "exp_name": row["exp_name"] or "",
                "sample_name": row["sample_name"] or "",
                "parameters": params,
                "completed_timestamp": row["completed_timestamp"] or "",
                "description_json": desc_raw,
            })
    except Exception as exc:
        logger.warning("Failed to extract runs from %s: %s", db_path, exc)
    finally:
        conn.close()

    return runs


# ---------------------------------------------------------------------------
# Summary card generation
# ---------------------------------------------------------------------------

def _derive_repo(db_path: Path) -> str:
    """Derive a repo/source tag from the file path."""
    db_str = str(db_path)
    repos_str = str(REPOS_DIR)
    server_str = str(SERVER_ROOT)

    if db_str.startswith(repos_str):
        rel = Path(db_str[len(repos_str):].lstrip("/"))
        return rel.parts[0] if rel.parts else db_path.name
    elif db_str.startswith(server_str):
        rel = Path(db_str[len(server_str):].lstrip("/"))
        return f"server/{rel.parts[0]}" if rel.parts else "server"
    else:
        return db_path.parent.name or "unknown"


def _make_summary_cards(db_path: Path, runs: list[dict]) -> list[dict]:
    """Generate Qdrant payload dicts for a list of runs."""
    repo = _derive_repo(db_path)
    cards = []
    for run in runs:
        ts = run["completed_timestamp"] or "unknown"
        params_str = ", ".join(run["parameters"]) if run["parameters"] else "unknown"
        text = (
            f"QCoDeS measurement run\n"
            f"Experiment: {run['exp_name']}\n"
            f"Sample: {run['sample_name']}\n"
            f"Run {run['run_id']}: {run['run_name']}\n"
            f"Completed: {ts}\n"
            f"Parameters: {params_str}\n"
            f"Database: {db_path.name}"
        )
        cards.append({
            "text": text,
            "source": str(db_path),
            "repo": repo,
            "chunk_type": "prose",
            "start_line": run["run_id"],
        })
    return cards


def _file_fingerprint(db_path: Path) -> str:
    """Compute a fast fingerprint from file metadata (size + mtime).

    Avoids reading entire file over CIFS — QCoDeS DBs can be hundreds of MB.
    """
    stat = db_path.stat()
    raw = f"{stat.st_size}:{stat.st_mtime_ns}"
    return hashlib.sha256(raw.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Async Qdrant helpers
# ---------------------------------------------------------------------------

async def _ensure_collection(client: AsyncQdrantClient, collection: str) -> None:
    existing = [c.name for c in (await client.get_collections()).collections]
    if collection not in existing:
        await client.create_collection(
            collection_name=collection,
            vectors_config=VectorParams(size=VECTOR_DIM, distance=Distance.COSINE),
            sparse_vectors_config={"text-sparse": SparseVectorParams(
                index=SparseIndexParams(on_disk=False)
            )},
        )
        logger.info("Created collection: %s", collection)


# ---------------------------------------------------------------------------
# Main scan logic
# ---------------------------------------------------------------------------

async def scan_roots(roots: list[Path], dry_run: bool = False) -> dict:
    """Scan roots for QCoDeS databases and update registry + Qdrant.

    Returns stats dict: {dbs_found, dbs_skipped, new_runs, cards_upserted}
    """
    manifest_db = os.path.join(AGENT_DATA_DIR, "episodic.db")
    conn = _init_db(manifest_db)
    client = AsyncQdrantClient(url=QDRANT_URL) if not dry_run else None

    if client:
        await _ensure_collection(client, COLLECTION)

    stats = {
        "dbs_found": 0,
        "dbs_skipped": 0,
        "new_runs": 0,
        "cards_upserted": 0,
    }

    # Discover all .db files
    all_db_files: list[Path] = []
    for root in roots:
        if not root.exists():
            logger.warning("Root not found, skipping: %s", root)
            continue
        found = _find_db_files(root)
        logger.info("Found %d .db files in %s", len(found), root)
        all_db_files.extend(found)

    now_iso = datetime.now(timezone.utc).isoformat()

    for db_path in all_db_files:
        # 1. Fingerprint check — skip unchanged files (size + mtime)
        try:
            fingerprint = _file_fingerprint(db_path)
        except Exception as exc:
            logger.warning("Cannot stat %s: %s", db_path, exc)
            continue

        existing = conn.execute(
            "SELECT sha256 FROM qcodes_db_hashes WHERE db_path = ?",
            (str(db_path),),
        ).fetchone()
        if existing and existing[0] == fingerprint:
            stats["dbs_skipped"] += 1
            continue

        # 2. Check if it's actually a QCoDeS DB
        if not _is_qcodes_db(db_path):
            continue

        stats["dbs_found"] += 1

        # 3. Extract all runs
        all_runs = _extract_runs(db_path)
        if not all_runs:
            conn.execute(
                """INSERT OR REPLACE INTO qcodes_db_hashes
                   (db_path, sha256, run_count, scanned_at)
                   VALUES (?, ?, 0, ?)""",
                (str(db_path), fingerprint, now_iso),
            )
            conn.commit()
            continue

        # 4. Find new runs (not yet in registry)
        existing_run_ids = {
            r[0] for r in conn.execute(
                "SELECT run_id FROM qcodes_registry WHERE db_path = ?",
                (str(db_path),),
            ).fetchall()
        }
        new_runs = [r for r in all_runs if r["run_id"] not in existing_run_ids]

        if dry_run:
            logger.info(
                "[DRY-RUN] %s: %d total runs, %d new",
                db_path.name, len(all_runs), len(new_runs),
            )
            stats["new_runs"] += len(new_runs)
            continue

        # 5. Insert new runs into registry
        for run in new_runs:
            conn.execute(
                """INSERT OR IGNORE INTO qcodes_registry
                   (db_path, run_id, exp_name, sample_name, run_name,
                    parameters, completed_timestamp, description_json, indexed_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    str(db_path),
                    run["run_id"],
                    run["exp_name"],
                    run["sample_name"],
                    run["run_name"],
                    json.dumps(run["parameters"]),
                    run["completed_timestamp"],
                    run["description_json"],
                    now_iso,
                ),
            )
        conn.commit()
        stats["new_runs"] += len(new_runs)

        # 6. Generate summary cards for new runs and upsert to qcodes-runs
        if new_runs:
            cards = _make_summary_cards(db_path, new_runs)
            texts = [c["text"] for c in cards]
            vectors = embed_documents(texts)
            sparse_vecs = embed_sparse(texts)

            for i in range(0, len(cards), UPSERT_BATCH):
                batch_slice = slice(i, i + UPSERT_BATCH)
                await client.upsert(
                    collection_name=COLLECTION,
                    points=[
                        PointStruct(
                            id=str(uuid4()),
                            vector={
                                "": vec,
                                "text-sparse": SparseVector(
                                    indices=sv.indices.tolist(),
                                    values=sv.values.tolist(),
                                ),
                            },
                            payload=card,
                        )
                        for vec, sv, card in zip(
                            vectors[batch_slice], sparse_vecs[batch_slice],
                            cards[batch_slice],
                        )
                    ],
                )
            stats["cards_upserted"] += len(cards)
            logger.info(
                "Indexed %s: %d new runs, %d cards",
                db_path.name, len(new_runs), len(cards),
            )

        # 7. Update hash table
        conn.execute(
            """INSERT OR REPLACE INTO qcodes_db_hashes
               (db_path, sha256, run_count, scanned_at)
               VALUES (?, ?, ?, ?)""",
            (str(db_path), fingerprint, len(all_runs), now_iso),
        )
        conn.commit()

    if client:
        await client.close()
    conn.close()
    return stats


async def scan_specific_dbs(db_paths: list[Path], dry_run: bool = False) -> dict:
    """Scan specific .db files (used by watcher's change_queue processor).

    Same logic as scan_roots but skips discovery — operates on explicit paths.
    """
    manifest_db = os.path.join(AGENT_DATA_DIR, "episodic.db")
    conn = _init_db(manifest_db)
    client = AsyncQdrantClient(url=QDRANT_URL) if not dry_run else None

    if client:
        await _ensure_collection(client, COLLECTION)

    stats = {"dbs_found": 0, "dbs_skipped": 0, "new_runs": 0, "cards_upserted": 0}
    now_iso = datetime.now(timezone.utc).isoformat()

    for db_path in db_paths:
        if not db_path.exists():
            continue

        try:
            fingerprint = _file_fingerprint(db_path)
        except Exception as exc:
            logger.warning("Cannot stat %s: %s", db_path, exc)
            continue

        existing = conn.execute(
            "SELECT sha256 FROM qcodes_db_hashes WHERE db_path = ?",
            (str(db_path),),
        ).fetchone()
        if existing and existing[0] == fingerprint:
            stats["dbs_skipped"] += 1
            continue

        if not _is_qcodes_db(db_path):
            continue

        stats["dbs_found"] += 1
        all_runs = _extract_runs(db_path)
        if not all_runs:
            conn.execute(
                """INSERT OR REPLACE INTO qcodes_db_hashes
                   (db_path, sha256, run_count, scanned_at) VALUES (?, ?, 0, ?)""",
                (str(db_path), fingerprint, now_iso),
            )
            conn.commit()
            continue

        existing_run_ids = {
            r[0] for r in conn.execute(
                "SELECT run_id FROM qcodes_registry WHERE db_path = ?",
                (str(db_path),),
            ).fetchall()
        }
        new_runs = [r for r in all_runs if r["run_id"] not in existing_run_ids]

        if dry_run:
            stats["new_runs"] += len(new_runs)
            continue

        for run in new_runs:
            conn.execute(
                """INSERT OR IGNORE INTO qcodes_registry
                   (db_path, run_id, exp_name, sample_name, run_name,
                    parameters, completed_timestamp, description_json, indexed_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (str(db_path), run["run_id"], run["exp_name"], run["sample_name"],
                 run["run_name"], json.dumps(run["parameters"]),
                 run["completed_timestamp"], run["description_json"], now_iso),
            )
        conn.commit()
        stats["new_runs"] += len(new_runs)

        if new_runs:
            cards = _make_summary_cards(db_path, new_runs)
            texts = [c["text"] for c in cards]
            vectors = embed_documents(texts)
            sparse_vecs = embed_sparse(texts)
            for i in range(0, len(cards), UPSERT_BATCH):
                batch_slice = slice(i, i + UPSERT_BATCH)
                await client.upsert(
                    collection_name=COLLECTION,
                    points=[
                        PointStruct(
                            id=str(uuid4()),
                            vector={
                                "": vec,
                                "text-sparse": SparseVector(
                                    indices=sv.indices.tolist(),
                                    values=sv.values.tolist(),
                                ),
                            },
                            payload=card,
                        )
                        for vec, sv, card in zip(
                            vectors[batch_slice], sparse_vecs[batch_slice],
                            cards[batch_slice],
                        )
                    ],
                )
            stats["cards_upserted"] += len(cards)

        conn.execute(
            """INSERT OR REPLACE INTO qcodes_db_hashes
               (db_path, sha256, run_count, scanned_at) VALUES (?, ?, ?, ?)""",
            (str(db_path), fingerprint, len(all_runs), now_iso),
        )
        conn.commit()

    if client:
        await client.close()
    conn.close()
    return stats


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    parser = argparse.ArgumentParser(
        description="Scan for QCoDeS databases and index to qcodes-runs collection"
    )
    parser.add_argument("--dry-run", action="store_true", help="Discover without writing")
    parser.add_argument("--root", action="append", metavar="PATH", help="Root directory to scan (repeatable)")
    args = parser.parse_args()

    if args.root:
        roots = [Path(r) for r in args.root]
    else:
        roots = []
        if REPOS_DIR.exists():
            roots.append(REPOS_DIR)
        if SERVER_ROOT.exists():
            roots.append(SERVER_ROOT)

    if not roots:
        logger.error("No scan roots available")
        sys.exit(1)

    logger.info("Scanning %d roots for QCoDeS databases%s",
                len(roots), " (dry run)" if args.dry_run else "")
    stats = asyncio.run(scan_roots(roots, dry_run=args.dry_run))
    logger.info(
        "Done: %d DBs found, %d skipped (unchanged), %d new runs, %d cards upserted",
        stats["dbs_found"], stats["dbs_skipped"], stats["new_runs"],
        stats["cards_upserted"],
    )


if __name__ == "__main__":
    main()
