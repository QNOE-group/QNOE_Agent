# Migration Audit: LangGraph → Hermes Agent
*2026-07-08*

> Systematic comparison of capabilities between the old LangGraph agent (`agent/`) and the current Hermes Agent (`hermes/`). Identifies lost capabilities, config drift, redundant code, and gained capabilities.

---

## 1. Lost or Regressed Capabilities

These features existed in the LangGraph codebase and are missing, broken, or degraded in Hermes.

### L1 — `tool_use_enforcement` not applied to sub-profiles (BUG)

| | Orchestrator | QTM | Photocurrent |
|---|---|---|---|
| **DGX config** | `true` | `auto` | `auto` |
| **Repo config** | `auto` | `auto` | `auto` |

**Impact:** HIGH. Hermes 3 is not in the `TOOL_USE_ENFORCEMENT_MODELS` auto-detection list. When users are routed to QTM or Photocurrent profiles (via `user_profiles.yaml`), the tool-use enforcement guidance is never injected, causing the model to output tool calls as plain text instead of structured JSON — the exact bug we fixed in the orchestrator (issue I3/Tool-calling-as-text).

**Fix:** Set `tool_use_enforcement: true` in all three profile `config.yaml` files on DGX, and commit to repo.

---

### L2 — TOP_K regressed from 3 to 5

The I1 context bloat fix (2026-07-03) changed `TOP_K` from 5 to 3 in the RAG plugin to save ~1,200 tokens/turn. Today's BM25 hybrid search deployment (`qnoe_rag/__init__.py`) overwrote the DGX file, reverting TOP_K to 5. The local repo also has TOP_K=5 — the change was never committed.

**Impact:** MEDIUM. ~1,200 extra tokens per turn. Worsens context bloat (I1).

**Fix:** Change `TOP_K = 5` → `TOP_K = 3` in both `hermes/plugins/qnoe_rag/__init__.py` (repo) and DGX deployment.

---

### L3 — Channel polling not migrated

The old `agent/teams.py` had:
- `_poll_channel(team_agent)` — polls sub-team Teams channels via `TEAMS_CHANNEL_IDS` env var (JSON dict: `{"qtm": "teamId/channelId"}`)
- `send_channel_reply(team_id, channel_id, message_id, text)` — replies in-thread within a channel

The Hermes `teams_polling` adapter only polls DM chats. No channel support.

**Impact:** LOW (currently). Channel polling was never used in production — `ChannelMessage.Read.All` permission hasn't been granted by IT (tracked as I8). But when IT grants it, we'll need to re-implement this in the Hermes adapter.

**Fix:** Defer. When I8 is actioned, add channel polling to `teams_polling/__init__.py`.

---

### L4 — Path validation removed

Old `agent/tools.py` enforced:
```python
ALLOWED_ROOTS = (
    "/ICFO/groups/NOE",
    "/opt/qnoe-agent/repos",
)
```
Every `read_file`, `list_directory`, `search_files` call was validated against these roots. Paths outside were rejected with "Access denied".

Hermes built-in file tools (`read_file`, `list_directory`, `search_files`) have no such restriction. The agent can read anything the `qnoe-ai` OS user can access (e.g. `/opt/qnoe-agent/secrets/`, `/etc/passwd`, other users' home dirs).

**Impact:** MEDIUM. T0/T1 read-only is still the intent, but the enforcement boundary moved from the tool layer to the system prompt (SOUL.md mentions allowed paths, but the model could ignore this). In LangGraph, path validation was code-enforced.

**Fix:** Options:
1. Add path validation to SOUL.md system prompt (soft enforcement — already partially done)
2. Write a Hermes plugin that wraps file tools with ALLOWED_ROOTS validation (hard enforcement)
3. OS-level: restrict `qnoe-ai` filesystem access via ACLs (most robust, but heavy)

Recommendation: Option 2 for Phase 1, Option 3 for Phase 2.

---

### L5 — Episodic context injection removed

Old `agent/graph.py` (`_subagent_respond`, line ~60):
```python
episodic = await get_episodic_context(session_id=..., user_id=..., limit=5)
# → injected as "[Recent task history]" block in system prompt
```

This gave the agent memory of recent interactions: "Yesterday you asked about SLG07-C2 gate sweeps and I found 3 runs."

Hermes has no equivalent wired in. The `episodic.py` module exists but nothing calls it. Hermes's MEMORY.md is persistent but agent-written (it only remembers what it chooses to write).

**Impact:** LOW. Hermes's built-in MEMORY.md + future Mem0 (L3.5) cover this use case better. The old episodic system was basic (last 5 events, no semantic search). Mem0 will provide semantic recall across sessions.

**Fix:** No action needed. Superseded by Mem0 (L3.5, planned).

---

### L6 — Custom conversation summarization replaced by opaque compression

Old `agent/graph.py` (`_summarise_if_needed`):
- Triggered at ≥60 turns or ≥56K chars
- Took oldest 30 turns, summarized to ≤400 tokens via LLM
- Merged with existing summary (summary-of-summaries) to stay ≤800 tokens
- Explicit token budget control

Hermes compression:
- `compression.threshold: 0.75` (triggers at ~24K of 32K context)
- Opaque internal mechanism — no visibility into compression quality or token budget
- No summary-of-summaries merging

**Impact:** LOW. Hermes compression works well in practice (verified in M7.6 smoke test). The old system was more predictable but required maintaining custom code. Hermes handles this as a platform feature.

**Fix:** No action needed. Monitor compression quality via logs if issues arise.

---

### L7 — Dev REPL removed

Old `agent/main.py` had `run_dev_repl()` — an interactive terminal REPL for testing the agent without Teams. Type a message, get a response, see tool calls.

Hermes has `hermes-cli` for interactive testing, but it requires the full Hermes gateway stack. There's no lightweight REPL equivalent.

**Impact:** LOW. `hermes-cli` serves the same purpose, just heavier. SSH + Teams DM is the primary test path.

**Fix:** No action needed.

---

## 2. Config Drift (Repo vs DGX)

Files in the local repo (`Z:\code\AI_Student\`) that don't match what's deployed on the DGX.

| File | Repo State | DGX State | Issue |
|---|---|---|---|
| `hermes/config.yaml` | `tool_use_enforcement: auto` | `true` (orchestrator only) | Fix never committed to repo |
| `hermes/config.yaml` | No `disabled_toolsets` | Has `disabled_toolsets` list | I1 fixes never committed |
| `hermes/config.yaml` | No `compression` section | Has `compression.threshold: 0.75` | I1 fixes never committed |
| `hermes/config.yaml` | No `tools.tool_search` section | Has `tool_search.enabled: 'on'` | I1 fixes never committed |
| `hermes/config.yaml` | No `multiplex_profiles` | Has `multiplex_profiles: true` | M7.5 never committed |
| `hermes/plugins/qnoe_qcodes/__init__.py` | Only `qcodes_search` tool | Has `qcodes_run_details` + `qcodes_run_diff` too | I6 tools never committed |
| `hermes/plugins/qnoe_rag/__init__.py` | `TOP_K = 5`, no BM25 | `TOP_K = 5` (regressed from 3), has BM25 | BM25 committed but overwrote TOP_K fix |
| Per-profile `config.yaml` | Not in repo at all | Exist on DGX with per-profile overrides | Never committed |

**Impact:** HIGH. The repo is significantly behind the DGX. A fresh deploy from repo would break: no `tool_use_enforcement: true`, no disabled toolsets, no compression threshold, no multiplex profiles, missing QCoDeS tools.

**Fix:** Sync repo to match DGX state. This is M8 cleanup work.

---

## 3. Redundant / Dead Code

Files in `agent/` that are no longer used by the running Hermes system. Grouped by status.

### Fully Dead — Safe to Archive

These files are only referenced by other dead files. No infrastructure code imports them. They can be moved to an `archive/langgraph/` directory.

| File | Was | Replaced By |
|---|---|---|
| `agent/graph.py` | LangGraph state machine, routing, response generation | Hermes profiles + `multiplex_profiles` + `user_profiles.yaml` |
| `agent/llm.py` | vLLM client with tool-call loop (max 5 rounds) | Hermes native LLM integration |
| `agent/main.py` | Entry point (Teams init, dev REPL) | `hermes/scripts/gateway_wrapper.py` + `qnoe-hermes.service` |
| `agent/prompts.py` | System prompt templates (orchestrator + 6 sub-agents) | SOUL.md per profile |
| `agent/state.py` | `AgentState` TypedDict for LangGraph | Hermes internal state management |
| `agent/teams.py` | Teams Graph API polling connector | `hermes/plugins/teams_polling/__init__.py` |
| `agent/retrieval.py` | Dense RAG (Qdrant + nomic-embed + cross-encoder) | `hermes/plugins/qnoe_rag/__init__.py` (hybrid dense+BM25) |

### Partially Dead — Keep for Now

| File | Status | Why Keep |
|---|---|---|
| `agent/episodic.py` | Functions unused by Hermes, but same DB file used by `qnoe_qcodes` plugin for `qcodes_registry` table | `ensure_schema()` creates `events` + `audit_log` tables needed for Phase 2. Keep until Mem0 replaces episodic or Phase 2 starts. |
| `agent/teams_check.py` | Standalone diagnostic — works independently | Useful for Teams credential validation. Not replaced by any Hermes equivalent. Keep. |

### Active Infrastructure — Do NOT Touch

These files under `agent/` are actively used by the nightly cron, watcher, and ingestion pipelines. They are NOT part of the LangGraph agent layer and must be preserved.

| Directory | Purpose |
|---|---|
| `agent/ingest/` | Ingestion pipeline (run_ingest, splitter, embed, qcodes_scanner, sharepoint_sync, etc.) |
| `agent/indexing/` | Nightly maintenance (nightly_run.py, backfill_sparse.py) |
| `agent/watcher/` | SMB3 file watcher daemon |
| `agent/reporting/` | Nightly report → Teams DM |
| `agent/ingest/excluded.py` | Shared exclusion patterns (used by multiple scripts) |
| `agent/ingest/embed.py` | Embedding functions (dense + sparse) — used by all ingestion paths |

---

## 4. Gained Capabilities (Hermes over LangGraph)

Features we got from migrating that didn't exist in the old system.

| Capability | Description |
|---|---|
| **Persistent MEMORY.md** | Agent writes notes that survive across sessions. LangGraph had no persistent memory except episodic events table. |
| **Self-improving skills** | `/skill` creates versioned Python tools in `skills/` directory. LangGraph had hardcoded tools only. |
| **90+ built-in tools** | Terminal, web search, code execution, vision analysis, file patch, process management. LangGraph had 3 tools. |
| **Tool Search** | Dynamic tool schema loading — only sends relevant tool schemas per turn, saving context. LangGraph loaded all tools always. |
| **Context compression** | Automatic, threshold-based compression. LangGraph had manual summarization requiring custom code. |
| **Per-user profile routing** | `user_profiles.yaml` maps Azure AD user IDs to profiles. LangGraph routed by message content analysis (slower, less reliable). |
| **Gateway architecture** | Platform-agnostic adapter system. Adding Slack/Discord/etc. only requires a new adapter plugin. LangGraph was Teams-only. |
| **Multiplex profiles** | Single gateway serves multiple profiles simultaneously. LangGraph ran one graph per process. |
| **Plugin ecosystem** | Modular plugin system (memory providers, tools, platforms). LangGraph required modifying core code for any extension. |
| **Session management** | Built-in session archiving, retention policies, auto-pruning. LangGraph had basic SqliteSaver checkpointer. |

---

## 5. Action Items

### Priority: HIGH (bugs / regressions)

| # | Action | Effort |
|---|---|---|
| A1 | Fix `tool_use_enforcement: true` in QTM + Photocurrent profile configs on DGX | 5 min |
| A2 | Change `TOP_K = 5` → `TOP_K = 3` in `qnoe_rag/__init__.py` (repo + DGX) | 5 min |
| A3 | Sync all DGX config changes to repo (config.yaml, per-profile configs, qcodes plugin) | 30 min |

### Priority: MEDIUM (missing enforcement)

| # | Action | Effort |
|---|---|---|
| A4 | Write file-tool path validation plugin (ALLOWED_ROOTS enforcement) | 2 hr |

### Priority: LOW (cleanup)

| # | Action | Effort |
|---|---|---|
| A5 | Archive dead LangGraph files to `archive/langgraph/` | 15 min |
| A6 | Add channel polling to `teams_polling` when IT grants `ChannelMessage.Read.All` (I8) | 2 hr |

### No Action Needed

| Item | Reason |
|---|---|
| Episodic context injection (L5) | Superseded by Mem0 (L3.5) |
| Custom summarization (L6) | Hermes compression works well |
| Dev REPL (L7) | `hermes-cli` serves same purpose |

---

## 6. File Inventory

Complete map of `agent/` files with current status.

| File | Status | Notes |
|---|---|---|
| `agent/__init__.py` | Keep | Package init (empty) |
| `agent/episodic.py` | Keep (partial) | DB schema used by Phase 2; functions unused |
| `agent/graph.py` | **DEAD** | LangGraph orchestrator → archive |
| `agent/llm.py` | **DEAD** | vLLM client → archive |
| `agent/main.py` | **DEAD** | Entry point → archive |
| `agent/prompts.py` | **DEAD** | System prompts → archive |
| `agent/state.py` | **DEAD** | State schema → archive |
| `agent/teams.py` | **DEAD** | Teams connector → archive |
| `agent/teams_check.py` | Keep | Standalone diagnostic, still useful |
| `agent/tools.py` | **DEAD** | File tools → archive (but review L4 path validation) |
| `agent/retrieval.py` | **DEAD** | Dense RAG → archive |
| `agent/ingest/*.py` | **ACTIVE** | Ingestion pipeline — do not touch |
| `agent/indexing/*.py` | **ACTIVE** | Nightly maintenance — do not touch |
| `agent/watcher/*.py` | **ACTIVE** | SMB3 watcher — do not touch |
| `agent/reporting/*.py` | **ACTIVE** | Nightly report — do not touch |
