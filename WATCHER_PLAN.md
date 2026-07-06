# Plan: SMB3 File Watcher Daemon + Queue-Based Nightly Processing

> Claude Code memory: [[memory/ingestion]] · Mistakes: [[memory/mistakes#M7 — QCoDeS find timeout on CIFS]]

## Context

The nightly ingestion scans `/ICFO/groups/NOE/` via `find` over CIFS, which takes **hours** (Notebook alone has 32k+ files and `find` can exceed 1h). We confirmed that `CIFS_IOC_NOTIFY` (ioctl `0x4005cf09`) works on this mount — kernel 6.17, SMB 3.1.1. The ioctl blocks until the server reports a change in a watched subtree, but does NOT return filenames.

**Goal:** Replace the nightly `find`-based scans (`task_index_server` + `task_scan_qcodes`) with:
1. A **watcher daemon** that runs continuously, detects changes via SMB3 notify, and queues changed files in SQLite
2. A **nightly queue processor** that ingests only the queued files — no `find` needed
3. A **stationary file check** that prevents indexing `.db` files during active measurements

---

## Files to create/modify

| File | Action |
|---|---|
| `agent/watcher/__init__.py` | **CREATE** — empty package |
| `agent/watcher/file_cache.py` | **CREATE** — SQLite cache + queue operations |
| `agent/watcher/smb_watcher.py` | **CREATE** — the daemon |
| `config/watcher.yaml` | **CREATE** — watcher configuration |
| `agent/indexing/nightly_run.py` | EDIT — replace `task_index_server` + `task_scan_qcodes` with `task_process_change_queue` |
| `agent/ingest/qcodes_scanner.py` | EDIT — add `scan_specific_dbs()` that accepts explicit paths |
| `runbook/RUNBOOK.md` | EDIT — add watcher setup steps |
| `HANDOFF.md` | EDIT — mention watcher daemon |
| `TODO.md` | EDIT — add watcher tasks |

---

## 1. SQLite schema (in `episodic.db` at `SERVER_DATA_DIR`)

```sql
-- Local cache of file metadata per watched folder
CREATE TABLE IF NOT EXISTS file_cache (
    id        INTEGER PRIMARY KEY,
    folder    TEXT    NOT NULL,       -- e.g. "Notebook" or "Notebook/2024"
    file_path TEXT    NOT NULL UNIQUE,
    mtime_ns  INTEGER NOT NULL,
    size      INTEGER NOT NULL,
    ext       TEXT    NOT NULL,       -- lowercase e.g. ".pdf"
    cached_at TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_file_cache_folder ON file_cache(folder);

-- Queue of changed files awaiting nightly processing
CREATE TABLE IF NOT EXISTS change_queue (
    id          INTEGER PRIMARY KEY,
    file_path   TEXT    NOT NULL,
    ext         TEXT    NOT NULL,
    change_type TEXT    NOT NULL,     -- "new" | "modified" | "deleted"
    detected_at TEXT    NOT NULL,
    stable_at   TEXT,                 -- NULL = still changing
    processed   INTEGER NOT NULL DEFAULT 0,  -- 0=pending, 1=done, 2=skipped
    processed_at TEXT,
    UNIQUE(file_path, detected_at)
);
CREATE INDEX IF NOT EXISTS idx_change_queue_pending ON change_queue(processed, ext);
```

---

## 2. `config/watcher.yaml`

```yaml
server_root: /ICFO/groups/NOE
db_path: /home/yzamir/qnoe_server_data/episodic.db

supported_extensions:
  docs: [".py", ".ipynb", ".md", ".txt", ".rst", ".pdf", ".pptx", ".docx"]
  dbs: [".db"]

# Files must be unchanged for this long before the nightly processor touches them
stationary_seconds: 1800  # 30 min

# Watch at top level (one thread each)
watch_toplevel:
  - Lab_Instruments
  - Manuscripts
  - Meetings
  - Notebooks
  - "Papers & Books"
  - Posters
  - Presentation
  - Presentations
  - Spectromag
  - "Theses & reports"
  - "Data Backup"
  - Fabrication
  - Personal
  - Setups
  - "Python scripts"
  - QCoDeS

# Watch at subfolder level (one thread per immediate child)
watch_subfolder_level:
  - Notebook
  - Projects

# Excluded from watching entirely (stale/archived, too large, not worth syncing)
exclude_subfolders:
  - Projects/QDphotodetector

# Seconds to wait after notification before scanning (batch rapid changes)
scan_cooldown_seconds: 5

# Safety net: full cache rebuild interval (catches missed notifications)
full_rebuild_interval_hours: 24
```

---

## 3. `agent/watcher/file_cache.py` (~200 lines)

Reuses: nothing external — pure SQLite operations.

### Key functions

```python
def init_schema(conn) -> None
    # Create file_cache + change_queue tables

def get_cached_files(conn, folder: str) -> dict[str, tuple[int, int]]
    # Return {file_path: (mtime_ns, size)} for folder

def update_cache_and_queue(conn, folder: str, current_files: dict) -> dict
    # Diff current vs cached. Update cache. Enqueue new/modified/deleted.
    # Returns {new: int, modified: int, deleted: int}
    # IMPORTANT: on first run with empty cache, populate cache but do NOT enqueue
    # (files were already indexed by initial bulk ingestion)

def mark_stable_files(conn, stationary_seconds: int) -> int
    # Re-stat each pending file. If mtime matches cache and detected_at
    # is older than stationary_seconds, set stable_at = now().
    # If mtime changed since detection -> update cache, reset detected_at.

def get_pending_queue(conn, ext_filter: set[str] | None, only_stable: bool) -> list[dict]
    # Return pending entries. If only_stable=True, require stable_at IS NOT NULL.

def mark_processed(conn, queue_ids: list[int], status: int = 1) -> None

def cleanup_old_entries(conn, days: int = 30) -> int
```

---

## 4. `agent/watcher/smb_watcher.py` (~350 lines)

### Architecture

```
Main thread
 |-- MountMonitor thread       (every 60s: detect mount drop/restore → trigger rebuild)
 |-- FolderWatcher thread x N  (one per watched folder/subfolder)
 |-- SubfolderManager thread x M  (one per watch_subfolder_level entry → spawns/stops FolderWatchers)
 |-- StabilityChecker thread   (every 10 min: re-stat queued files)
 +-- CacheRebuilder thread     (every 24h OR on remount: full find as safety net)
```

### FolderWatcher

```python
CIFS_IOC_NOTIFY = 0x4005cf09
CF_ALL = 0x17F  # all change types

class FolderWatcher(threading.Thread):
    # daemon=True -- dies with main thread

    def run(self):
        # 1. Initial scan: populate cache for this folder (seed mode -- no enqueue)
        # 2. Loop:
        #    a. os.open(folder, O_RDONLY | O_DIRECTORY)
        #    b. fcntl.ioctl(fd, CIFS_IOC_NOTIFY, pack("=IB", CF_ALL, 1))  # blocks
        #    c. On return: sleep(cooldown) to batch rapid changes
        #    d. Run targeted find on this folder only
        #    e. Filter by supported extensions, stat each file
        #    f. update_cache_and_queue() -- diff + enqueue
        #    g. Re-arm (loop back to b)
        #
        # Error handling:
        #   - os.open fails (mount down): log, sleep 60s, retry
        #   - ioctl EINTR: check stop event, re-issue
        #   - ioctl OSError: log, close fd, sleep 30s, reopen

    def _targeted_find(self) -> dict[str, tuple[int, int, str]]:
        # subprocess.run(["find", folder, "-type", "f", ...]) -- no timeout
        # Filter by extensions, stat each result
        # Returns {path: (mtime_ns, size, ext)}
```

### Notification depth — what does the ioctl see?

**The ioctl watches at the directory you open, with `watch_tree=True` covering the entire subtree.** The notification fires for changes at ANY depth below the watched folder. For example:

- Watcher opens `/ICFO/groups/NOE/Setups/`
- A file changes at `/ICFO/groups/NOE/Setups/QTM/2026/data/experiment.db`
- The ioctl returns (unblocks)
- But it does NOT tell you which file — just "something changed under Setups/"
- We then run `find /ICFO/groups/NOE/Setups/` to discover what changed

**This is why folder granularity matters:**
- Small folders (Setups, 17 .db files): watch at top → `find` after notification is fast
- Huge folders (Notebook, 32k files): watch at **subfolder level** → `find` scoped to e.g. `Notebook/2024/` only

For `watch_subfolder_level` folders, the daemon enumerates immediate children and creates one FolderWatcher per child. So `Projects/` with 20 subdirs gets 20 watchers, each scoped to one subdirectory.

### MountMonitor (item 1: mount drop resilience)

**Problem:** When the CIFS mount drops, FolderWatchers retry on `os.open` failure. But changes happening on the server while unmounted are invisible. The 24h CacheRebuilder eventually catches them, but that's too slow.

**Solution:** Detect remount and immediately trigger a full cache rebuild.

```python
class MountMonitor(threading.Thread):
    """Polls mount availability every 60s. On remount, triggers CacheRebuilder."""

    def __init__(self, server_root: Path, cache_rebuilder: CacheRebuilder,
                 stop_event: threading.Event):
        self._root = server_root
        self._rebuilder = cache_rebuilder
        self._stop = stop_event
        self._was_mounted = True

    def run(self):
        while not self._stop.wait(60):
            is_mounted = self._check_mount()
            if not self._was_mounted and is_mounted:
                # Mount just came back — trigger immediate rebuild
                logger.warning("Mount restored at %s — triggering full cache rebuild", self._root)
                self._rebuilder.trigger_now()
            elif self._was_mounted and not is_mounted:
                logger.warning("Mount lost at %s — watchers will retry", self._root)
            self._was_mounted = is_mounted

    def _check_mount(self) -> bool:
        # os.path.ismount() returns False for stale CIFS.
        # Instead, try to stat a known path (e.g. server_root itself).
        try:
            os.stat(self._root)
            return True
        except OSError:
            return False
```

The `CacheRebuilder` gains a `trigger_now()` method that sets an internal event, breaking
its 24h sleep early. It rebuilds **one folder at a time**, saving progress between each,
so a CIFS failure mid-rebuild doesn't lose all work.

```python
class CacheRebuilder(threading.Thread):
    def __init__(self, watched_folders: list[Path], config: dict,
                 stop_event: threading.Event):
        self._folders = watched_folders  # all leaf folders (expanded from config)
        self._config = config
        self._stop = stop_event
        self._trigger = threading.Event()
        self._progress_db = config["db_path"]  # tracks last successful rebuild per folder

    def trigger_now(self):
        """Called by MountMonitor on remount."""
        self._trigger.set()

    def run(self):
        while not self._stop.is_set():
            # Wait up to 24h OR until triggered
            self._trigger.wait(timeout=self._config["full_rebuild_interval_hours"] * 3600)
            self._trigger.clear()
            self._rebuild_incremental()

    def _rebuild_incremental(self):
        """Rebuild one folder at a time. Save progress after each.

        If interrupted (CIFS drop, process restart), resumes from where it left off.
        Folders that completed within the last 24h are skipped.
        """
        conn = sqlite3.connect(self._progress_db)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS rebuild_progress (
                folder      TEXT PRIMARY KEY,
                completed_at TEXT NOT NULL
            )
        """)
        conn.commit()

        cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()

        for folder in self._folders:
            if self._stop.is_set():
                break

            # Skip if already rebuilt recently
            row = conn.execute(
                "SELECT completed_at FROM rebuild_progress WHERE folder = ?",
                (str(folder),)
            ).fetchone()
            if row and row[0] > cutoff:
                continue

            # Rebuild this one folder
            try:
                logger.info("CacheRebuilder: scanning %s", folder)
                current_files = self._targeted_find(folder)
                update_cache_and_queue(conn, str(folder), current_files)
                # Mark success
                conn.execute(
                    "INSERT OR REPLACE INTO rebuild_progress (folder, completed_at) VALUES (?, ?)",
                    (str(folder), datetime.now(timezone.utc).isoformat()),
                )
                conn.commit()
                logger.info("CacheRebuilder: done %s (%d files)", folder, len(current_files))
            except OSError as exc:
                # CIFS failure on this folder — skip, try next
                logger.warning("CacheRebuilder: failed on %s: %s (continuing)", folder, exc)
                continue

        conn.close()
```

**Key properties:**
- Each folder is an independent unit — failure on one doesn't block others
- Progress saved per folder in `rebuild_progress` table
- On restart or remount trigger, only re-scans folders not rebuilt in last 24h
- If CIFS drops mid-scan, the current folder fails but all previously completed folders retain their progress

**Mount drop timeline:**
1. Mount drops → MountMonitor logs warning, `_was_mounted = False`
2. FolderWatchers hit `os.open` errors, log + sleep 60s + retry
3. Mount restored → MountMonitor detects it within 60s
4. MountMonitor calls `trigger_now()` → CacheRebuilder wakes immediately
5. CacheRebuilder runs full `find` + diff on all folders → queues any missed changes
6. FolderWatchers reconnect on their own retry cycle

### SubfolderManager (item 3: dedup + dynamic subfolder discovery)

**Problem:** For `watch_subfolder_level` folders (Projects, Notebook), we create one FolderWatcher per child. But:
- If a new subfolder is created in Projects/, no watcher covers it until daemon restart
- Notifications at the parent level could overlap with child-level watchers, causing duplicate queue entries

**Solution:** A `SubfolderManager` thread per `watch_subfolder_level` entry that:
- Watches only the parent directory for structural changes (new/deleted subdirs)
- Dynamically spawns/stops `FolderWatcher` threads as subdirectories appear/disappear
- Does NOT enqueue file changes itself — only manages child watchers

```python
class SubfolderManager(threading.Thread):
    """Manages FolderWatcher threads for children of a watch_subfolder_level folder."""

    def __init__(self, parent_folder: Path, exclude: set[str],
                 config: dict, stop_event: threading.Event):
        self._parent = parent_folder
        self._exclude = exclude        # e.g. {"Projects/QDphotodetector"}
        self._config = config
        self._stop = stop_event
        self._child_watchers: dict[str, FolderWatcher] = {}

    def run(self):
        # 1. Initial: enumerate children, spawn FolderWatchers (skip excluded)
        self._sync_children()
        # 2. Loop: watch parent dir via ioctl for structural changes
        while not self._stop.is_set():
            try:
                fd = os.open(str(self._parent), os.O_RDONLY | os.O_DIRECTORY)
                # watch_tree=False — only direct children, not subtree
                fcntl.ioctl(fd, CIFS_IOC_NOTIFY, pack("=IB", CF_DIR_CHANGES, 0))
                os.close(fd)
                time.sleep(scan_cooldown)
                self._sync_children()
            except OSError:
                time.sleep(60)  # mount down

    def _sync_children(self):
        """Enumerate current subdirs, start new watchers, stop removed ones."""
        try:
            current = {
                d.name for d in self._parent.iterdir()
                if d.is_dir() and not d.name.startswith(".")
            }
        except OSError:
            return

        # Filter out excluded subfolders
        rel_prefix = self._parent.name  # e.g. "Projects"
        current = {
            d for d in current
            if f"{rel_prefix}/{d}" not in self._exclude
        }

        # Start watchers for new subdirs
        for name in current - set(self._child_watchers):
            path = self._parent / name
            watcher = FolderWatcher(path, self._config, self._stop)
            watcher.start()
            self._child_watchers[name] = watcher
            logger.info("Started watcher for new subfolder: %s/%s", rel_prefix, name)

        # Stop watchers for removed subdirs
        for name in set(self._child_watchers) - current:
            # Watcher will exit on next loop since folder is gone
            del self._child_watchers[name]
            logger.info("Subfolder removed, watcher will exit: %s/%s", rel_prefix, name)
```

**Dedup guarantee:** Only `FolderWatcher` threads (one per leaf subfolder) enqueue file changes. The `SubfolderManager` watches the parent with `watch_tree=False` and only reacts to directory-level structural changes. No file change is ever recorded at two levels.

**Key constant:**

```python
# Directory change filter — only new/renamed/deleted subdirs, NOT file content
CF_DIR_CHANGES = 0x003  # FILE_NOTIFY_CHANGE_DIR_NAME (create + delete + rename)
```

### StabilityChecker

```python
class StabilityChecker(threading.Thread):
    # Every 10 minutes: call mark_stable_files()
    # This determines when a .db file has stopped being written to
```

### Startup / shutdown

```python
def main():
    # Load config, build watch list, start threads:
    #   - MountMonitor (1 thread)
    #   - FolderWatcher per watch_toplevel entry
    #   - SubfolderManager per watch_subfolder_level entry
    #     (each spawns FolderWatchers for its children, minus exclude_subfolders)
    #   - StabilityChecker (1 thread)
    #   - CacheRebuilder (1 thread, also triggered by MountMonitor)
    # Signal handler (SIGTERM, SIGINT) sets stop_event
    # All connections use PRAGMA journal_mode=WAL (concurrent thread writes)
```

### CLI

```
python -m agent.watcher.smb_watcher                 # run daemon
python -m agent.watcher.smb_watcher --rebuild-cache  # one-shot full rebuild
python -m agent.watcher.smb_watcher --dump-queue     # print pending queue
```

---

## 4b. Docling memory safety + monthly oversized file processing

**Problem:** Large PDFs (textbooks, theses >50 MB) can cause Docling to spike to 10+ GB RAM. With vLLM occupying ~70 GB of 128 GB unified memory, this risks OOM.

**Solution:** Cap file size for Docling processing. Files exceeding the limit are logged and deferred to a monthly maintenance window when vLLM is stopped.

### Config addition (`config/watcher.yaml`):

```yaml
# Maximum file size (bytes) for Docling processing during nightly runs.
# Files larger than this are logged to oversized_files.log and skipped.
# Process them monthly with vLLM stopped (frees ~70 GB).
docling_max_file_bytes: 52428800  # 50 MB

# Log of files too large for nightly Docling processing
oversized_files_log: /opt/qnoe-agent/logs/oversized_files.log
```

### Implementation (in `agent/ingest/run_ingest.py`):

```python
DOCLING_MAX_FILE_BYTES = int(os.environ.get("DOCLING_MAX_FILE_BYTES", 52428800))  # 50 MB
OVERSIZED_FILES_LOG = Path(os.environ.get("OVERSIZED_FILES_LOG", "/opt/qnoe-agent/logs/oversized_files.log"))

# In the per-file loop, before calling chunk_file():
if path.stat().st_size > DOCLING_MAX_FILE_BYTES and path.suffix.lower() in {".pdf", ".pptx", ".docx"}:
    logger.info("OVERSIZED (%.1f MB): %s — deferred to monthly run", path.stat().st_size / 1e6, path)
    _log_oversized(path)
    continue

def _log_oversized(path: Path) -> None:
    try:
        with open(OVERSIZED_FILES_LOG, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now(timezone.utc).isoformat()}\t{path}\t{path.stat().st_size}\n")
    except Exception:
        pass
```

### Monthly maintenance procedure

**Schedule:** First Sunday of each month, or whenever convenient.
**Duration:** ~2-4 hours depending on backlog.

```bash
# 1. Stop vLLM to free ~70 GB memory
sudo systemctl stop vllm

# 2. Process oversized files (full memory available for Docling)
PYTHONPATH=/opt/qnoe-agent QDRANT_URL=http://localhost:6333 \
  AGENT_DATA_DIR=/home/yzamir/qnoe_server_data \
  DOCLING_MAX_FILE_BYTES=0 \
  /opt/qnoe-agent/venv/bin/python -m agent.ingest.run_ingest \
  --team group-wide \
  --file-list /opt/qnoe-agent/logs/oversized_files.log \
  --repo-name server/oversized \
  >> /tmp/monthly_oversized.log 2>&1

# 3. Clear the log (processed files are now in manifest DB)
> /opt/qnoe-agent/logs/oversized_files.log

# 4. Restart vLLM + agent
sudo systemctl start vllm
sudo systemctl start qnoe-agent
```

**Note:** The `--file-list` flag expects one path per line. The oversized log has `timestamp\tpath\tsize` format — the `run_ingest.py` file-list parser must be updated to handle this (strip columns after path), or a simple `cut -f2` pre-processing step works:

```bash
cut -f2 /opt/qnoe-agent/logs/oversized_files.log > /tmp/oversized_paths.txt
# Then use --file-list /tmp/oversized_paths.txt
```

---

## 5. Edit `agent/ingest/qcodes_scanner.py`

Add a new function that accepts explicit paths (no `find`):

```python
async def scan_specific_dbs(db_paths: list[Path], dry_run: bool = False) -> dict:
    """Scan specific .db files from the change queue. No directory walk."""
    # Same logic as scan_roots but:
    # - Takes explicit paths instead of roots
    # - Skips _find_db_files entirely
    # - Runs _is_qcodes_db, _extract_runs, embed, upsert as usual
    # - Returns same stats dict
```

Extract shared logic from `scan_roots` into a helper `_process_single_db()` used by both.

---

## 6. Edit `agent/indexing/nightly_run.py`

### New task: `task_process_change_queue`

```python
def task_process_change_queue() -> None:
    """Process watcher change queue -- ingest changed docs + scan changed QCoDeS DBs."""
    from agent.watcher.file_cache import get_pending_queue, mark_processed, cleanup_old_entries

    db_path = str(SERVER_DATA_DIR / "episodic.db")
    conn = sqlite3.connect(db_path)

    # 1. Process document files (non-.db, stable only)
    doc_exts = {".py", ".ipynb", ".md", ".txt", ".rst", ".pdf", ".pptx", ".docx"}
    doc_queue = get_pending_queue(conn, ext_filter=doc_exts, only_stable=True)
    if doc_queue:
        new_or_mod = [e for e in doc_queue if e["change_type"] != "deleted"]
        file_list = [Path(e["file_path"]) for e in new_or_mod if Path(e["file_path"]).exists()]
        if file_list:
            ingest_directory(
                team="group-wide", repo_path=SERVER_ROOT,
                repo_name="server", force=True,
                file_list=file_list, manifest_db=db_path,
            )
        mark_processed(conn, [e["id"] for e in doc_queue])

    # 2. Process QCoDeS .db files (stable only)
    db_queue = get_pending_queue(conn, ext_filter={".db"}, only_stable=True)
    if db_queue:
        db_paths = [Path(e["file_path"]) for e in db_queue
                    if e["change_type"] != "deleted" and Path(e["file_path"]).exists()]
        if db_paths:
            from agent.ingest.qcodes_scanner import scan_specific_dbs
            stats = asyncio.run(scan_specific_dbs(db_paths))
            logger.info("QCoDeS queue: %s", stats)
        mark_processed(conn, [e["id"] for e in db_queue])

    # 3. Cleanup old entries
    cleanup_old_entries(conn, days=30)
    conn.close()
```

### Updated TASKS

```python
TASKS: list = [
    task_qdrant_snapshot,
    task_index_repos,           # unchanged -- local disk, fast
    task_process_change_queue,  # REPLACES task_index_server + task_scan_qcodes
    task_orphan_cleanup,
]
```

Keep `task_index_server` and `task_scan_qcodes` functions for manual `--task` use, just remove from default TASKS list.

---

## 7. Active measurement safety

**Problem:** A QCoDeS `.db` file being written to during an ongoing measurement should not be indexed — the data is incomplete and the file hash will change.

**Solution — stationary file check (3 layers):**

1. **StabilityChecker thread** (every 10 min): re-stats each pending queue entry. If `mtime_ns` hasn't changed in `stationary_seconds` (30 min), marks `stable_at = now()`. If mtime changed -> updates cache, resets the clock.

2. **Nightly processor**: only processes entries where `stable_at IS NOT NULL`. Files still being written remain in the queue.

3. **QCoDeS-specific**: `_extract_runs` already filters on `completed_timestamp IS NOT NULL` implicitly (joins on `runs` table rows that exist). Incomplete runs that haven't been committed to the DB yet won't appear.

**Timing:** Nightly run at 02:00. Most measurements finish before midnight. 30-min stationary threshold means a measurement finishing at 01:29 would be processed; one finishing at 01:31 would wait until the next night.

---

## 8. Systemd service

```ini
[Unit]
Description=QNOE SMB3 file change watcher
After=network-online.target

[Service]
Type=simple
User=yzamir
Environment=WATCHER_CONFIG=/opt/qnoe-agent/config/watcher.yaml
ExecStart=/opt/qnoe-agent/venv/bin/python -m agent.watcher.smb_watcher
Restart=on-failure
RestartSec=30
StandardOutput=append:/opt/qnoe-agent/logs/smb_watcher.log
StandardError=append:/opt/qnoe-agent/logs/smb_watcher.log

[Install]
WantedBy=multi-user.target
```

Runs as `yzamir` (only yzamir can read CIFS mount).

---

## 9. Verification

1. **Deploy watcher + create test file on CIFS:**
   ```bash
   touch /ICFO/groups/NOE/Lab_Instruments/test_watcher.txt
   # Check watcher log -- should see change detected
   sqlite3 episodic.db "SELECT * FROM change_queue ORDER BY id DESC LIMIT 5"
   ```

2. **Stability check:** Create a file, verify it appears in queue with `stable_at IS NULL`. Wait 30+ min, verify `stable_at` gets set.

3. **Nightly queue processing:**
   ```bash
   python -m agent.indexing.nightly_run --task process_change_queue
   ```

4. **Active .db safety:** Open a QCoDeS DB, keep writing. Verify it stays in queue with `stable_at IS NULL` and is NOT processed by nightly run.

5. **Mount drop resilience:** Unmount CIFS, verify watcher logs warning and retries. Remount, verify watchers reconnect.

6. **Idempotency:** Run nightly processor twice. Second run should find 0 pending entries.
