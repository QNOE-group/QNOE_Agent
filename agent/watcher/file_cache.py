"""SQLite file cache and change queue for the SMB3 watcher daemon.

Tables:
  file_cache    — last-known metadata for all watched files
  change_queue  — files detected as new/modified/deleted, awaiting nightly processing
  rebuild_progress — per-folder timestamp of last CacheRebuilder completion
"""
import sqlite3
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS file_cache (
            id        INTEGER PRIMARY KEY,
            folder    TEXT    NOT NULL,
            file_path TEXT    NOT NULL UNIQUE,
            mtime_ns  INTEGER NOT NULL,
            size      INTEGER NOT NULL,
            ext       TEXT    NOT NULL,
            cached_at TEXT    NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_file_cache_folder ON file_cache(folder);

        CREATE TABLE IF NOT EXISTS change_queue (
            id          INTEGER PRIMARY KEY,
            file_path   TEXT    NOT NULL,
            ext         TEXT    NOT NULL,
            change_type TEXT    NOT NULL,
            detected_at TEXT    NOT NULL,
            stable_at   TEXT,
            processed   INTEGER NOT NULL DEFAULT 0,
            processed_at TEXT,
            UNIQUE(file_path, detected_at)
        );
        CREATE INDEX IF NOT EXISTS idx_change_queue_pending ON change_queue(processed, ext);

        CREATE TABLE IF NOT EXISTS rebuild_progress (
            folder       TEXT PRIMARY KEY,
            completed_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS sharepoint_delta (
            drive_id   TEXT PRIMARY KEY,
            delta_link TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
    """)
    conn.commit()


def get_cached_files(conn: sqlite3.Connection, folder: str) -> dict[str, tuple[int, int]]:
    """Return {file_path: (mtime_ns, size)} for a folder."""
    rows = conn.execute(
        "SELECT file_path, mtime_ns, size FROM file_cache WHERE folder = ?",
        (folder,),
    ).fetchall()
    return {r[0]: (r[1], r[2]) for r in rows}


def update_cache_and_queue(
    conn: sqlite3.Connection,
    folder: str,
    current_files: dict[str, tuple[int, int, str]],
) -> dict[str, int]:
    """Diff current files against cache. Update cache. Enqueue changes.

    current_files: {path: (mtime_ns, size, ext)}

    On first run (cache empty for this folder), populates cache but does NOT enqueue
    — files were already indexed by initial bulk ingestion.

    Returns: {new: N, modified: N, deleted: N}
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    cached = get_cached_files(conn, folder)
    is_seed = len(cached) == 0 and len(current_files) > 0

    stats = {"new": 0, "modified": 0, "deleted": 0}

    current_paths = set(current_files.keys())
    cached_paths = set(cached.keys())

    # New files
    for path in current_paths - cached_paths:
        mtime_ns, size, ext = current_files[path]
        conn.execute(
            """INSERT OR REPLACE INTO file_cache
               (folder, file_path, mtime_ns, size, ext, cached_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (folder, path, mtime_ns, size, ext, now_iso),
        )
        if not is_seed:
            conn.execute(
                """INSERT OR IGNORE INTO change_queue
                   (file_path, ext, change_type, detected_at)
                   VALUES (?, ?, 'new', ?)""",
                (path, ext, now_iso),
            )
            stats["new"] += 1

    # Modified files
    for path in current_paths & cached_paths:
        mtime_ns, size, ext = current_files[path]
        old_mtime, old_size = cached[path]
        if mtime_ns != old_mtime or size != old_size:
            conn.execute(
                """UPDATE file_cache
                   SET mtime_ns = ?, size = ?, cached_at = ?
                   WHERE file_path = ?""",
                (mtime_ns, size, now_iso, path),
            )
            if not is_seed:
                conn.execute(
                    """INSERT OR IGNORE INTO change_queue
                       (file_path, ext, change_type, detected_at)
                       VALUES (?, ?, 'modified', ?)""",
                    (path, ext, now_iso),
                )
                stats["modified"] += 1

    # Deleted files
    for path in cached_paths - current_paths:
        conn.execute("DELETE FROM file_cache WHERE file_path = ?", (path,))
        if not is_seed:
            ext = path.rsplit(".", 1)[-1] if "." in path else ""
            ext = f".{ext}" if ext else ""
            conn.execute(
                """INSERT OR IGNORE INTO change_queue
                   (file_path, ext, change_type, detected_at)
                   VALUES (?, ?, 'deleted', ?)""",
                (path, ext, now_iso),
            )
            stats["deleted"] += 1

    conn.commit()

    if is_seed:
        logger.info("Seed mode: cached %d files for %s (no enqueue)", len(current_files), folder)

    return stats


def mark_stable_files(conn: sqlite3.Connection, stationary_seconds: int) -> int:
    """Re-stat each pending file. Mark stable if unchanged for stationary_seconds.

    If mtime changed since detection, update cache and reset detected_at.
    Returns number of files newly marked stable.
    """
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    marked = 0

    rows = conn.execute(
        """SELECT id, file_path, ext FROM change_queue
           WHERE processed = 0 AND stable_at IS NULL AND change_type != 'deleted'"""
    ).fetchall()

    for row_id, file_path, ext in rows:
        path = Path(file_path)
        try:
            stat = path.stat()
            current_mtime = stat.st_mtime_ns
            current_size = stat.st_size
        except OSError:
            # File gone — mark as stable (will be processed as deletion)
            conn.execute(
                "UPDATE change_queue SET stable_at = ? WHERE id = ?",
                (now_iso, row_id),
            )
            marked += 1
            continue

        # Check against cache
        cached = conn.execute(
            "SELECT mtime_ns, size FROM file_cache WHERE file_path = ?",
            (file_path,),
        ).fetchone()

        if cached and cached[0] == current_mtime and cached[1] == current_size:
            # File unchanged since we cached it — check how long ago detected
            detected = conn.execute(
                "SELECT detected_at FROM change_queue WHERE id = ?", (row_id,)
            ).fetchone()
            if detected:
                detected_dt = datetime.fromisoformat(detected[0])
                if (now - detected_dt).total_seconds() >= stationary_seconds:
                    conn.execute(
                        "UPDATE change_queue SET stable_at = ? WHERE id = ?",
                        (now_iso, row_id),
                    )
                    marked += 1
        else:
            # File changed again — update cache and reset detection time
            conn.execute(
                """UPDATE file_cache SET mtime_ns = ?, size = ?, cached_at = ?
                   WHERE file_path = ?""",
                (current_mtime, current_size, now_iso, file_path),
            )
            conn.execute(
                "UPDATE change_queue SET detected_at = ?, stable_at = NULL WHERE id = ?",
                (now_iso, row_id),
            )

    conn.commit()
    return marked


def get_pending_queue(
    conn: sqlite3.Connection,
    ext_filter: set[str] | None = None,
    only_stable: bool = False,
) -> list[dict]:
    """Return pending queue entries.

    If only_stable=True, only returns entries with stable_at IS NOT NULL.
    """
    sql = "SELECT id, file_path, ext, change_type, detected_at, stable_at FROM change_queue WHERE processed = 0"
    params: list = []

    if only_stable:
        sql += " AND stable_at IS NOT NULL"

    rows = conn.execute(sql, params).fetchall()
    results = []
    for row in rows:
        entry = {
            "id": row[0],
            "file_path": row[1],
            "ext": row[2],
            "change_type": row[3],
            "detected_at": row[4],
            "stable_at": row[5],
        }
        if ext_filter and entry["ext"] not in ext_filter:
            continue
        results.append(entry)
    return results


def mark_processed(conn: sqlite3.Connection, queue_ids: list[int], status: int = 1) -> None:
    """Mark queue entries as processed (1=done, 2=skipped)."""
    now_iso = datetime.now(timezone.utc).isoformat()
    for qid in queue_ids:
        conn.execute(
            "UPDATE change_queue SET processed = ?, processed_at = ? WHERE id = ?",
            (status, now_iso, qid),
        )
    conn.commit()


def cleanup_old_entries(conn: sqlite3.Connection, days: int = 30) -> int:
    """Remove processed queue entries older than `days` days."""
    from datetime import timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    cursor = conn.execute(
        "DELETE FROM change_queue WHERE processed > 0 AND processed_at < ?",
        (cutoff,),
    )
    conn.commit()
    return cursor.rowcount
