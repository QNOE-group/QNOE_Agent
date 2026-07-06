# Migration Plan: LangGraph → Hermes Agent

> Claude Code memory: [[memory/hermes-migration]] · Comparison: [[HERMES_AGENT_COMPARISON]] · Decision: [[memory/decisions#D4 — Replace LangGraph with Hermes Agent]]

**Date:** 2026-06-30
**Author:** Claude (with Yonatan)
**Status:** APPROVED — ready for implementation

---

## 1. Goal

Replace the custom LangGraph agent layer with Hermes Agent (v0.17.0) while preserving all existing infrastructure: Qdrant RAG, QCoDeS registry, CIFS watcher, ingestion pipeline, nightly indexing.

### What changes
- Agent conversation loop, tool dispatch, memory, skills, system prompt assembly
- Teams connector (replaced by Hermes Teams polling adapter)

### What stays untouched
- vLLM (Hermes 3 70B AWQ) at `localhost:8000`
- Qdrant at `localhost:6333` (8 collections)
- Watcher daemon (`qnoe-watcher.service`)
- Ingestion pipeline (`run_ingest.py`, `splitter.py`)
- Nightly cron (`nightly_run.py`)
- QCoDeS scanner (`qcodes_scanner.py`)
- All config files (`repo_collections.yaml`, `watcher.yaml`)
- All data on the CIFS mount (`/ICFO/groups/NOE/`)

---

## 2. Architecture After Migration

```
┌──────────────────────────────────────────────────┐
│  Hermes 3 70B (INT8 AWQ) via vLLM                │  localhost:8000
├──────────────────────────────────────────────────┤
│  Hermes Agent (v0.17.0)                          │
│    ├── SOUL.md (identity per profile)             │
│    ├── Memory (MEMORY.md + USER.md per profile)   │
│    ├── Skills (self-created, /opt/qnoe-agent/     │
│    │          hermes/skills/)                      │
│    ├── Tools: built-in + custom QNOE tools        │
│    └── Gateway: Teams polling adapter (plugin)    │
├──────────────────────────────────────────────────┤
│  Custom QNOE Plugins                             │
│    ├── qnoe-rag (Qdrant retrieval tool)           │
│    ├── qnoe-qcodes (QCoDeS registry query tool)  │
│    └── qnoe-teams-polling (Teams Graph API)       │
├──────────────────────────────────────────────────┤
│  Existing Infrastructure (unchanged)              │
│    ├── Qdrant (8 collections, port 6333)          │
│    ├── Watcher daemon (qnoe-watcher.service)      │
│    ├── Nightly indexer (cron 02:00)               │
│    └── CIFS mount (/ICFO/groups/NOE)              │
└──────────────────────────────────────────────────┘
```

---

## 3. Integration Points

### 3.1 RAG — as a Hermes Tool (not context engine)

**Why tool, not context engine?** Context engines in Hermes manage context *compression* (summarization when the window fills). Our RAG is a *retrieval* layer — it fetches relevant chunks before each turn. The correct integration is as a **tool** that the agent calls, plus we inject top-K results into the system prompt via a **memory provider plugin** that does `prefetch()`.

**Implementation: `qnoe-rag` memory provider plugin**

```
plugins/memory/qnoe_rag/
├── __init__.py          # register(ctx) → QnoeRagProvider
└── retrieval.py         # Symlink or copy of existing agent/retrieval.py
```

The provider implements:
- `prefetch(query)` → calls Qdrant retrieval, returns formatted context block
- `queue_prefetch(query)` → starts background retrieval for next turn
- `system_prompt_block()` → returns static text about available collections
- `get_tool_schemas()` → exposes `rag_search` tool for explicit queries
- `handle_tool_call("rag_search", args)` → explicit search with collection/query args

This way RAG works TWO ways:
1. **Automatic** — `prefetch()` runs before every turn, injecting relevant context
2. **Explicit** — agent can call `rag_search` tool with specific collection + query

### 3.2 QCoDeS Registry — as a Hermes Tool

**Implementation: custom tool registered via `tools/registry.py`**

```
tools/qcodes_tool.py     # register() in Hermes tool registry
```

Tool schema:
- `qcodes_search(query, sample=None, experiment=None, date_from=None, date_to=None)`
- Queries the `qcodes_registry` SQLite table
- Returns formatted run cards (experiment, sample, parameters, timestamp)

### 3.3 File Access — use Hermes built-in tools

Hermes has built-in `read_file`, `write_file`, `patch`, `search_files` tools. We configure them to work with our allowed paths via path security settings. **No custom tool needed** — just configure `tools/path_security.py` to allow:
- `/ICFO/groups/NOE/` (read-only)
- `/opt/qnoe-agent/repos/` (read-only)

### 3.4 Teams — Polling Adapter Plugin

The existing Hermes Teams adapter uses webhooks (requires inbound HTTP from Microsoft). Our DGX has no public IP. We write a **polling adapter** that reuses Hermes's sophisticated gateway infrastructure but polls Graph API instead of listening for webhooks.

**Implementation: `plugins/platforms/teams_polling/`**

```
plugins/platforms/teams_polling/
├── plugin.yaml
├── __init__.py
└── adapter.py           # TeamsPollingAdapter(BasePlatformAdapter)
```

The adapter:
- Subclasses `BasePlatformAdapter` (same as all Hermes platform adapters)
- Uses our existing Graph API polling logic (proven, working)
- Adds Hermes gateway features: `handle_message()` dispatch, `send()`, `send_typing()`
- Uses MSAL ROPC auth (same as current connector)
- Supports DM chats + channel polling
- Registers as `Platform("teams_polling")`

**Why not modify the existing webhook adapter?** The webhook adapter depends on `microsoft-teams-apps` SDK which requires a Bot Framework registration and inbound HTTP. Our polling approach is fundamentally different (no SDK, no webhook endpoint). A clean plugin is better than patching.

### 3.5 Multi-Agent — Hermes Profiles

Each sub-team becomes a Hermes **profile** with its own:
- `SOUL.md` — identity, expertise, scope (replaces our system prompt templates)
- `MEMORY.md` — agent's learned facts about this sub-team
- `USER.md` — per-user preferences within this sub-team
- Skills directory — sub-team-specific skills

Profile structure:
```
/opt/qnoe-agent/hermes/
├── profiles/
│   ├── qnoe-orchestrator/
│   │   ├── SOUL.md
│   │   ├── memories/MEMORY.md
│   │   └── memories/USER.md
│   ├── qnoe-qtm/
│   │   ├── SOUL.md
│   │   ├── memories/MEMORY.md
│   │   └── memories/USER.md
│   └── qnoe-photocurrent/
│       ├── SOUL.md
│       ├── memories/MEMORY.md
│       └── memories/USER.md
├── skills/           # Shared + agent-created skills
└── config.yaml       # Global Hermes config
```

**Routing:** The orchestrator profile uses `delegate_task` to route to sub-team profiles when the topic is clear. For Phase 1, we keep the same 2 active sub-teams (QTM + Photocurrent) with the orchestrator handling everything else.

---

## 4. Implementation Phases

### Phase M1: Install & Configure Hermes (Day 1)

| Step | Task | Details |
|------|------|---------|
| M1.1 | Install Hermes Agent in venv | `pip install hermes-agent` in `/opt/qnoe-agent/venv/` |
| M1.2 | Create Hermes home directory | `/opt/qnoe-agent/hermes/` with profiles, skills, config |
| M1.3 | Configure for local vLLM | `config.yaml`: `OPENAI_BASE_URL=http://localhost:8000/v1`, model name, 32K context |
| M1.4 | Verify basic operation | Run `hermes` CLI, send a test message, confirm vLLM responds |
| M1.5 | Configure path security | Allow `/ICFO/groups/NOE/` and `/opt/qnoe-agent/repos/` as read-only |

### Phase M2: Create Profiles (Day 1-2)

| Step | Task | Details |
|------|------|---------|
| M2.1 | Write orchestrator SOUL.md | Convert `ORCHESTRATOR_PROMPT` from `prompts.py` |
| M2.2 | Write QTM SOUL.md | Convert QTM subagent prompt + data paths |
| M2.3 | Write Photocurrent SOUL.md | Convert Photocurrent subagent prompt |
| M2.4 | Seed initial MEMORY.md files | Populate with known facts (data paths, conventions, team members) |
| M2.5 | Test each profile standalone | Run in CLI mode, verify persona and tool access |

### Phase M3: RAG Plugin (Day 2-3)

| Step | Task | Details |
|------|------|---------|
| M3.1 | Create `plugins/memory/qnoe_rag/` | Directory structure + `plugin.yaml` |
| M3.2 | Port `retrieval.py` | Copy retrieval logic (Qdrant client, nomic-embed, cross-encoder) |
| M3.3 | Implement `QnoeRagProvider` | `prefetch()`, `queue_prefetch()`, `system_prompt_block()`, `get_tool_schemas()` |
| M3.4 | Configure collection routing | Per-profile config: which Qdrant collections to query |
| M3.5 | Test RAG integration | Query from CLI, verify chunks are injected + reranked |

### Phase M4: QCoDeS Tool (Day 3)

| Step | Task | Details |
|------|------|---------|
| M4.1 | Create `tools/qcodes_tool.py` | Register via `registry.register()` |
| M4.2 | Port query logic | SQLite query against `qcodes_registry` table |
| M4.3 | Test tool calling | Ask about measurements, verify structured results |

### Phase M5: Teams Polling Adapter (Day 3-4)

| Step | Task | Details |
|------|------|---------|
| M5.1 | Create `plugins/platforms/teams_polling/` | Directory + `plugin.yaml` + `adapter.py` |
| M5.2 | Port polling logic from `teams.py` | MSAL auth, Graph API polling, dedup, rate limiting |
| M5.3 | Implement `BasePlatformAdapter` interface | `connect()`, `disconnect()`, `send()`, `send_typing()`, `get_chat_info()` |
| M5.4 | Wire into Hermes gateway | Register platform, configure in `config.yaml` |
| M5.5 | Test end-to-end | Send message in Teams → Hermes processes → replies in Teams |

### Phase M6: Multi-Agent Routing (Day 4-5)

| Step | Task | Details |
|------|------|---------|
| M6.1 | Configure delegation | Orchestrator profile uses `delegate_task` for sub-team routing |
| M6.2 | Set up toolset restrictions | Sub-agents get RAG + file tools; orchestrator gets delegation + RAG |
| M6.3 | Test routing | Send QTM question → routes to QTM profile → responds with QTM context |
| M6.4 | Test cross-team queries | Send ambiguous question → orchestrator handles |

### Phase M7: Deployment & Cutover (Day 5-6)

| Step | Task | Details |
|------|------|---------|
| M7.1 | Update Docker image | New Dockerfile with Hermes Agent + QNOE plugins |
| M7.2 | Update `start_agent.sh` | Launch Hermes gateway instead of `python -m agent.main` |
| M7.3 | Update systemd service | New `ExecStart`, env vars for Hermes |
| M7.4 | Parallel run | Run new agent alongside old (different Teams bot? or same bot, swap) |
| M7.5 | Cutover | Stop old agent, start new. Verify Teams, RAG, file access, memory |
| M7.6 | Smoke test all features | File read, directory list, search, RAG, QCoDeS, memory save, skills |

### Phase M8: Cleanup & Documentation (Day 6-7)

| Step | Task | Details |
|------|------|---------|
| M8.1 | Archive old agent code | Move `agent/graph.py`, `agent/state.py`, `agent/llm.py`, old `agent/main.py` to `archive/` |
| M8.2 | Update HANDOFF.md | New architecture, file map, deployment instructions |
| M8.3 | Update DGX_SETUP.md | New install steps, Hermes config paths |
| M8.4 | Update AGENT_CODE_GUIDE.md | New message flow, plugin structure |
| M8.5 | Update SETUP_LOG.md | Record migration completion |

---

## 5. File Map After Migration

| Path (on DGX) | Role |
|---|---|
| `/opt/qnoe-agent/venv/` | Python venv (now includes `hermes-agent` package) |
| `/opt/qnoe-agent/hermes/` | `HERMES_HOME` — profiles, memory, skills, config |
| `/opt/qnoe-agent/hermes/config.yaml` | Global Hermes config (model, context, toolsets, gateway) |
| `/opt/qnoe-agent/hermes/profiles/qnoe-*/` | Per-sub-team profiles (SOUL.md, MEMORY.md, USER.md) |
| `/opt/qnoe-agent/hermes/skills/` | Agent-created + custom skills |
| `/opt/qnoe-agent/hermes/plugins/memory/qnoe_rag/` | RAG memory provider plugin |
| `/opt/qnoe-agent/hermes/plugins/platforms/teams_polling/` | Teams polling adapter plugin |
| `/opt/qnoe-agent/agent/tools/qcodes_tool.py` | QCoDeS registry tool (registered in Hermes) |
| `/opt/qnoe-agent/agent/retrieval.py` | Qdrant retrieval (used by qnoe_rag plugin) |
| `/opt/qnoe-agent/agent/watcher/` | Watcher daemon (unchanged) |
| `/opt/qnoe-agent/agent/ingest/` | Ingestion pipeline (unchanged) |
| `/opt/qnoe-agent/agent/indexing/` | Nightly indexer (unchanged) |
| `/opt/qnoe-agent/config/` | Repo collections, watcher config (unchanged) |
| `/opt/qnoe-agent/models/` | vLLM model, nomic-embed, cross-encoder (unchanged) |
| `/opt/qnoe-agent/memory/` | Qdrant data, episodic DB, watcher DB (unchanged) |

---

## 6. Hermes `config.yaml` (Draft)

```yaml
# Model configuration
model: /opt/qnoe-agent/models/hermes-3-70b-awq
provider: openai  # OpenAI-compatible (vLLM)
api_base: http://localhost:8000/v1
context_length: 32768
max_output_tokens: 2048
temperature: 0.2

# Memory
memory:
  provider: qnoe_rag  # Our custom RAG provider
  # Built-in memory (MEMORY.md, USER.md) is always active

# Skills
skills:
  enabled: true
  guard_agent_created: false  # Phase 1: trust the agent

# Gateway (Teams polling)
platforms:
  teams_polling:
    enabled: true
    extra:
      tenant_id: "${TEAMS_TENANT_ID}"
      client_id: "${TEAMS_CLIENT_ID}"
      username: "${TEAMS_USERNAME}"
      password: "${TEAMS_PASSWORD}"
      poll_interval_active: 3
      poll_interval_idle: 10
      active_window: 300

# Context compression
context:
  engine: compressor  # Built-in (default)
  threshold_percent: 0.75

# Toolsets
toolset: qnoe-lab  # Custom toolset defined below

# Profile (default)
profile: qnoe-orchestrator
```

---

## 7. Key Decisions

| Decision | Choice | Rationale |
|---|---|---|
| RAG integration method | Memory provider plugin with `prefetch()` + exposed tool | Automatic injection per-turn + explicit search capability |
| Teams integration method | Custom polling adapter plugin | No public IP on DGX; polling is proven; Hermes plugin system supports it cleanly |
| Multi-agent method | Profiles + `delegate_task` | Matches Hermes design; each sub-team gets isolated memory/skills |
| Context engine | Built-in compressor (default) | Our RAG is retrieval, not compression. No need for custom context engine |
| File access | Hermes built-in `read_file` / `search_files` | Already handles line ranges, large files, search. Configure path security |
| Skill creation | Enabled from day 1 | Core motivation for migration — let the agent learn |
| Memory | Built-in MEMORY.md + USER.md | Core motivation for migration — cross-session persistence |

---

## 8. Rollback Plan

If migration fails:
1. Old agent code stays in `archive/` — can be restored
2. Old systemd service unit saved as `qnoe-agent.service.bak`
3. Checkpoint DB is separate (old agent's checkpoints don't conflict)
4. All infrastructure (vLLM, Qdrant, watcher, ingestion) is untouched
5. Rollback = restore old service unit + restart

---

## 9. Acceptance Criteria

Migration is complete when:
- [ ] Agent responds to Teams DM messages via polling
- [ ] Agent uses correct sub-team persona (QTM / Photocurrent / orchestrator)
- [ ] RAG retrieval works: query returns relevant Qdrant chunks
- [ ] File tools work: read_file, list_directory, search_files on CIFS mount
- [ ] QCoDeS tool works: query measurements by sample/experiment
- [ ] Memory persists: agent saves a fact, restarts, recalls it
- [ ] Skills work: agent creates a skill after solving a complex task
- [ ] Delegation works: orchestrator routes to QTM/Photocurrent profiles
- [ ] Context compression works: long conversations don't crash
- [ ] Watcher + nightly indexing continue functioning independently
