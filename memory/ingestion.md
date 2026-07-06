# Ingestion & RAG Pipeline
*Last updated: 2026-07-03 (SharePoint pipeline added)*

> File discovery, chunking, embedding, Qdrant indexing, watcher daemon, QCoDeS scanner.
> Watcher design: [[WATCHER_PLAN]] · Repo mapping: [[REPO_MAPPING]] · Memory design: [[INFERENCE_MEMORY]]

## Ingestion CLI

`agent/ingest/run_ingest.py` — hash-based dedup via `index_manifest` SQLite table.

Key options: `--team`, `--repo-path`, `--force`, `--file-list`, `--dry-run`

Server ingestion uses separate manifest: `AGENT_DATA_DIR=/home/yzamir/qnoe_server_data`

## Supported Extensions

`.py`, `.ipynb`, `.md`, `.txt`, `.rst`, `.pdf`, `.pptx`, `.docx`

Docling used for PDF/DOCX/PPTX (50MB cap). Oversized files logged to `/tmp/oversized_files.log`.

## Exclusions — Single Source of Truth

`agent/ingest/excluded.py` reads `config/watcher.yaml` → `find_prune_args()`.
All `find` commands (run_ingest, qcodes_scanner) use this function.

Excluded folders: QDphotodetector, TopoNanop, HighQuality_Plamons, Low_temperature_polaritons, mid-IR_Plasmonic_detector_Seb, Graphene Optomechanics.

## Qdrant Collections

8 collections: `group-wide`, `qtm`, `photocurrent`, `qed`, `superconductivity`, `qsim`, `xchiral`, `qcodes-runs`

Mapping rules: `config/repo_collections.yaml`

## QCoDeS Scanner

`agent/ingest/qcodes_scanner.py` — async, incremental, stat-based fingerprint (size + mtime).

- 75 DBs, 75,477 runs indexed (as of 2026-06-30)
- No timeout on `find` (CIFS scan takes 2h+)
- Column name: `run_description` (not `description`) — see [[memory/mistakes#M6 — QCoDeS column name]]

## Watcher Daemon

`agent/watcher/smb_watcher.py` — 14 tests pass.

- `watch_subfolder_level`: Projects, Notebook, Notebooks, Setups, Personal, Fabrication
- `Notebook/Antenna+graphene` intentionally KEPT
- Cache: ~37K files, full rebuild ~44 min
- Change queue processed by nightly `task_process_change_queue()`

## SharePoint Pipeline

**New source added 2026-07-03.** Two Teams sites indexed via Microsoft Graph API.

Files: `agent/ingest/sharepoint_client.py` (Graph API wrapper), `agent/ingest/sharepoint_sync.py` (full + delta sync).

**Key design decisions:**
- No local file cache — each file streamed to `/tmp/qnoe-sharepoint/`, chunked, embedded, temp deleted immediately (even on failure via `try/finally`)
- **Dedup:** etag from Graph API (not SHA-256) stored in `sp_manifest` table in `/opt/qnoe-agent/memory/sharepoint.db`
- **Delta sync:** Graph delta API, delta links stored in `sharepoint_delta` table in watcher DB
- **Token refresh:** auto-refreshes every 45 min mid-sync (MSAL tokens expire at 60 min — critical for large syncs)
- **Exclusions:** checked per-item at processing time (not during listing); `list_drive_items()` always walks full tree
- **Source field** in Qdrant chunks: set to SharePoint web URL (not temp path)
- **`repo` field:** set to site name (`twisted-materials` or `noe-group`)

**Flow:** `SharePointPoller` thread (every 30 min) → `delta_sync()` → if no baseline → `full_sync()` → `list_drive_items()` → per-item: download → `chunk_file()` → `embed_documents()` → `_upsert_chunks()` → `_record_item()` → `dest.unlink()`

**First run timing:** Full listing of 2429-item drive takes ~2.5 min. Docling PDFs 30s–3min each. NOE-Group is larger — expect 2–4h total first sync.

**Orphan cleanup:** `sweep_orphans()` in `run_ingest.py` only covers `index_manifest`. SP chunks tracked via `sp_manifest` — no orphan sweep yet (future work).

## Nightly Tasks

1. `task_qdrant_snapshot` — snapshot all collections, prune >7 days
2. `task_index_repos` — incremental re-index of 41 GitHub repos
3. `task_sync_sharepoint` — full sync of both SP sites (safety net for missed deltas)
4. `task_process_change_queue` — process watcher's stable entries
5. `task_orphan_cleanup` — remove chunks for files missing 7+ days

## Ingestion Stats

- 41 GitHub repos → 7 Qdrant collections
- Server: all 12 folders indexed
- QCoDeS: 75 DBs, 75,477 runs
- RAG eval: 17/20 queries relevant (85%)
- BM25 hybrid search planned: [[PHASE2_BACKLOG#B1 — BM25 hybrid search (L2)]]
