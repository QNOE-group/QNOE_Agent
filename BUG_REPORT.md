# Bug Report — QNOE Agent Codebase

Full audit completed in 4 sweeps (June 2026). All 15 bugs were fixed in-place.

---

## Sweep 1 — Major architectural bugs

### B1 · Multi-turn memory wipe (`agent/main.py`)

**Severity:** Critical
**Symptom:** Every incoming message started a fresh conversation. The agent had no memory between turns.
**Root cause:** `handle_message` always passed `"messages": [user_msg]` and `"turns_since_summary": 0` to `graph.ainvoke`, discarding everything in the LangGraph checkpoint. LangGraph's `TypedDict` state has no `add_messages` reducer — the messages field is *replaced*, not appended.
**Fix:** Load the existing state snapshot before invoking the graph and carry forward `messages`, `turns_since_summary`, and `conversation_summary`:

```python
snapshot = await graph.aget_state(config)
existing_messages = snapshot.values.get("messages", []) if snapshot and snapshot.values else []
existing_turns = snapshot.values.get("turns_since_summary", 0) if snapshot and snapshot.values else 0
existing_summary = snapshot.values.get("conversation_summary") if snapshot and snapshot.values else None

input_state = {
    ...
    "messages": existing_messages + [user_msg],
    "turns_since_summary": existing_turns,
    "conversation_summary": existing_summary,
}
```

---

### B2 · Blocking sync calls in async graph nodes (`agent/retrieval.py`, `agent/episodic.py`, `agent/graph.py`)

**Severity:** High
**Symptom:** `retrieve()`, `get_episodic_context()`, and `log_event()` were synchronous. Calling them from async LangGraph nodes blocked the asyncio event loop for the entire duration of the Qdrant query and SQLite writes.
**Root cause:** Functions not marked `async`; no executor wrapping.
**Fix:**
- `retrieval.py`: Changed `QdrantClient` → `AsyncQdrantClient`; made `retrieve()` async; wrapped `model.encode()` in `run_in_executor`; parallelized per-collection queries with `asyncio.gather`.
- `episodic.py`: Made `log_event()` and `get_episodic_context()` async wrappers; moved SQLite I/O into sync inner functions called via `run_in_executor`.
- `graph.py`: Added `await` to all three calls.

---

### B3 · Manifest DB path confusion (`agent/ingest/run_ingest.py`, `agent/indexing/nightly_run.py`, `agent/ingest/ingest_server.py`)

**Severity:** High
**Symptom:** Server ingestion (which runs as `yzamir` and writes to `/home/yzamir/qnoe_server_data/`) was using the same manifest DB as repo ingestion (`/opt/qnoe-agent/memory/episodic.db`, owned by `qnoe-ai`). Either a permissions error at runtime or silent DB sharing causing incorrect deduplication.
**Root cause:** `ingest_directory()` hard-coded `MANIFEST_DB` with no way to override it.
**Fix:** Added `manifest_db: str | None` parameter to `_get_manifest_conn()` and `ingest_directory()`. `nightly_run.py` now passes `manifest_db=str(AGENT_DATA_DIR / "episodic.db")` for repos and `manifest_db=str(SERVER_DATA_DIR / "episodic.db")` for server docs. `ingest_server.py` passes the env-var-resolved path explicitly.

---

### B4 · Self-chat test unreliable (`agent/teams_check.py`)

**Severity:** Medium
**Symptom:** Step 4 of the Teams connectivity check attempted to send a message to the bot's own chat, which is not a meaningful permission test and can create noise or fail for unrelated reasons.
**Root cause:** Wrong choice of verification method.
**Fix:** Replaced with JWT payload inspection — base64-decode the access token, extract the `scp` claim, and assert that `Chat.Read`, `Chat.ReadWrite`, and `ChatMessage.Send` are all present.

---

## Sweep 2 — Correctness and blocking bugs

### B5 · Timezone-aware vs naive datetime crash (`agent/indexing/nightly_run.py`)

**Severity:** High
**Symptom:** `task_qdrant_snapshot` would crash at runtime with `TypeError: can't compare offset-naive and offset-aware datetimes` when pruning old snapshots.
**Root cause:** `cutoff = datetime.now(timezone.utc) - timedelta(days=...)` is timezone-aware. The snapshot timestamp was parsed as `datetime.fromisoformat(raw)` after stripping only `"Z"` — leaving the string without a UTC offset, producing a naive datetime.
**Fix:** Changed to `datetime.fromisoformat(raw.replace("Z", "+00:00"))` for a properly aware datetime.

---

### B6 · Duplicate system messages rejected by some LLM backends (`agent/graph.py`)

**Severity:** Medium
**Symptom:** The conversation summary was injected as a second `{"role": "system", ...}` message. Some OpenAI-compatible backends (including vLLM with certain model configs) reject or mishandle multiple system messages.
**Root cause:** `_state_messages_to_openai` prepended the summary as a separate system dict when building the message list.
**Fix:** Removed the second system message. Added `_summary_block()` helper that appends the summary as a section of text in the main system prompt:

```python
def _summary_block(state: AgentState) -> str:
    summary = state.get("conversation_summary")
    if not summary:
        return ""
    return f"\n\n[Earlier conversation summary]\n{summary}"
```

---

### B7 · Blocking MSAL token acquisition (`agent/teams.py`)

**Severity:** High
**Symptom:** `acquire_token_silent` and `acquire_token_by_username_password` are synchronous MSAL calls that could take 1–5 seconds. Called directly inside an async method, they blocked the asyncio event loop on every poll cycle.
**Root cause:** MSAL has no async API.
**Fix:** Extracted the acquisition logic into `_acquire_token_sync()` and wrapped it:

```python
async def _get_token(self) -> str:
    if self._token and time.time() < self._token_expires - 60:
        return self._token
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(None, self._acquire_token_sync)
    ...
```

---

### B8 · ISO timestamp comparison fragility (`agent/teams.py`)

**Severity:** Medium
**Symptom:** Messages with timestamps using a different UTC notation (e.g. `+00:00` vs `Z`) or missing timezone info could be incorrectly ordered vs. the startup timestamp, causing pre-startup messages to be replayed after restart.
**Root cause:** Startup timestamp stored as `_startup_iso: str` and compared with string comparison (`msg_ts < self._startup_iso`). String ordering is only valid when formats are identical.
**Fix:** Changed `_startup_ts` to `datetime` type. Added `_after_startup()` helper that parses the ISO string with `.replace("Z", "+00:00")` and does a proper datetime comparison.

---

### B9 · Orphaned Qdrant points on collection migration (`agent/ingest/run_ingest.py`)

**Severity:** Medium
**Symptom:** If a file was re-ingested into a different Qdrant collection (e.g., a repo moved from `group-wide` to `qtm`), `_delete_old_chunks` deleted from the *new* collection (where the chunks hadn't been written yet) instead of the *old* one. Old chunks were never cleaned up, causing duplicates.
**Root cause:** `_delete_old_chunks` used the `collection` parameter (current target) rather than reading the collection stored in the manifest.
**Fix:** Read `collection` and `point_ids` together from the manifest row and delete from the stored collection:

```python
row = conn.execute(
    "SELECT collection, point_ids FROM index_manifest WHERE file_path = ?", (str(path),)
).fetchone()
old_collection = row[0]
old_ids = json.loads(row[1])
client.delete(collection_name=old_collection, points_selector=old_ids)
```

---

### B10 · Blocking `input()` in async REPL (`agent/main.py`)

**Severity:** Low
**Symptom:** `input("You: ")` in `run_dev_repl` blocks the entire asyncio event loop while waiting for user input.
**Root cause:** `input()` is a blocking stdlib call.
**Fix:** Wrapped in `run_in_executor`:
```python
text = await loop.run_in_executor(None, lambda: input("You: "))
```

---

## Sweep 3 — Deprecation, resource, and security bugs

### B11 · `datetime.utcnow()` deprecated and returns naive datetime (`agent/indexing/nightly_run.py`)

**Severity:** Low
**Symptom:** Python 3.12 emits `DeprecationWarning` for `datetime.utcnow()`. The returned datetime is naive (no timezone), which would crash if compared with an aware datetime.
**Root cause:** Two uses of `datetime.utcnow()` in `nightly_run.py`.
**Fix:** Replaced both with `datetime.now(timezone.utc)`. Added `timezone` to imports.

---

### B12 · Temp file not deleted on exception (`agent/ingest/splitter.py`)

**Severity:** Low
**Symptom:** `_chunk_pdf_text` wrote a temp `.md` file and called `tmp.unlink()` at the end. If `_chunk_text(tmp, ...)` raised, the temp file was leaked.
**Root cause:** No `try/finally` guard around the temp file usage.
**Fix:** Wrapped in `try/finally`:

```python
with tempfile.NamedTemporaryFile(..., delete=False) as f:
    f.write(text)
    tmp = Path(f.name)
try:
    chunks = _chunk_text(tmp, repo, chunk_type="prose")
finally:
    tmp.unlink(missing_ok=True)
```

---

### B13 · PAT logged in clone error messages (`agent/ingest/clone_org.py`)

**Severity:** Medium
**Symptom:** When `git clone` fails, git may echo the clone URL (which contains the PAT) in the error message. This was sanitized for clone errors but not pull errors.
**Root cause:** Pull error at line 88 logged `result.stderr.strip()` raw; clone error at line 97 had the correct `result.stderr.replace(pat, "***")` guard — but the same issue existed independently for pull failures (added in sweep 3) and was confirmed as a second instance in sweep 4 (B15).
**Fix (sweep 3):** Added `safe_err = result.stderr.replace(pat, "***").strip()` to the clone path.

---

### B14 · Docling import error retried on every PDF (`agent/ingest/splitter.py`)

**Severity:** Low
**Symptom:** If `import docling` fails (Docling not installed), `_chunk_pdf_docling` caught `ImportError` but left `_pdf_converter = None`, so the next PDF call would try importing again — O(N) import attempts for N PDFs.
**Root cause:** The sentinel was only set to `False` on `ImportError` inside the `try` block for `_get_pdf_converter()`, but `_get_pdf_converter()` was called lazily and the `ImportError` path didn't always reach the assignment.
**Fix:** Set `_pdf_converter = False` explicitly in the `except ImportError` branch of `_chunk_pdf_docling`.

---

## Sweep 4 — Resource and security bugs

### B15 · SQLite connection leak in QCoDeS chunker (`agent/ingest/splitter.py`)

**Severity:** Low
**Symptom:** If `sqlite3.connect()` succeeds but the schema-check query (`SELECT name FROM sqlite_master`) raises (e.g., malformed DB file), the `except Exception: return []` exits without closing `conn`, leaking the file descriptor. Over 2,636 QCoDeS databases this could exhaust the process FD limit.
**Root cause:** `conn` was opened before the outer `try` block that handled it, so exceptions from the schema check bypassed `conn.close()`.
**Fix:** Split the `try` block — open `conn` first in its own `try/except`, then validate the schema in a second `try/except` that closes `conn` on failure:

```python
try:
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
except Exception:
    return []

try:
    tables = {r[0] for r in conn.execute(...)}
    if not {"experiments", "runs"}.issubset(tables):
        conn.close()
        return []
except Exception:
    conn.close()
    return []
```

---

### B16 · PAT exposed in `git pull` error logs (`agent/ingest/clone_org.py`)

**Severity:** Medium
**Symptom:** When `git pull --ff-only` fails on an existing repo, the raw stderr is logged. Since the repo was cloned with the PAT embedded in the remote URL (`.git/config`), git may echo the URL — including the PAT — in error output.
**Root cause:** Clone path sanitized the error with `.replace(pat, "***")` (B13 fix), but the pull path (line 88) was missed — these are different code branches.
**Fix:** Applied the same sanitization to the pull error path:

```python
safe_err = result.stderr.replace(pat, "***").strip()
logger.warning("Pull failed for %s: %s", name, safe_err)
```

---

## Summary table

| ID | File | Severity | Category | Status |
|----|------|----------|----------|--------|
| B1 | `agent/main.py` | Critical | Architecture | Fixed |
| B2 | `agent/retrieval.py`, `agent/episodic.py`, `agent/graph.py` | High | Async/blocking | Fixed |
| B3 | `agent/ingest/run_ingest.py`, `agent/indexing/nightly_run.py`, `agent/ingest/ingest_server.py` | High | Config/paths | Fixed |
| B4 | `agent/teams_check.py` | Medium | Correctness | Fixed |
| B5 | `agent/indexing/nightly_run.py` | High | Timezone crash | Fixed |
| B6 | `agent/graph.py` | Medium | Protocol compat | Fixed |
| B7 | `agent/teams.py` | High | Async/blocking | Fixed |
| B8 | `agent/teams.py` | Medium | Correctness | Fixed |
| B9 | `agent/ingest/run_ingest.py` | Medium | Data integrity | Fixed |
| B10 | `agent/main.py` | Low | Async/blocking | Fixed |
| B11 | `agent/indexing/nightly_run.py` | Low | Deprecation | Fixed |
| B12 | `agent/ingest/splitter.py` | Low | Resource leak | Fixed |
| B13 | `agent/ingest/clone_org.py` | Medium | Security | Fixed |
| B14 | `agent/ingest/splitter.py` | Low | Performance | Fixed |
| B15 | `agent/ingest/splitter.py` | Low | Resource leak | Fixed |
| B16 | `agent/ingest/clone_org.py` | Medium | Security | Fixed |
