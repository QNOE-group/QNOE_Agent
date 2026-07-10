# Agent Framework Design
*Last updated: 2026-05-27 (v2 — full design)*

> Claude Code memory: [[memory/agent-code]] · Being replaced by Hermes: [[memory/hermes-migration]] · [[MIGRATION_PLAN]]

---

## Overview

The agent framework is built on **LangGraph**. The orchestrator and six
sub-agents are nodes in a directed state graph. The continuous perception
loop, event-driven action gates, and T0–T4 permission tiers are implemented
as graph edges and conditional transitions.

**Key architectural principle:** each active conversation runs as an
independent LangGraph instance with its own `AgentState`. Parallelism is
achieved by running multiple instances concurrently — not by sharing state
between agents. All instances share the same vLLM endpoint, Qdrant, SQLite,
and skill registry, all of which support concurrent access natively.

---

## G4 — `AgentState` schema

### 4.1 Instance model

| Instance type | Lifetime | One per |
|---|---|---|
| **Orchestrator** | Persistent (always running) | System |
| **Sub-agent** | Ephemeral (spawned per conversation) | Active Teams conversation thread |

Sub-agent instances are keyed by Teams `conversation_id`. When a message
arrives in a DM or channel thread, the framework looks up the existing
instance for that conversation ID or creates a new one. This is how two
researchers in different sub-teams can have simultaneous independent
conversations without any state collision.

### 4.2 `AgentState` TypedDict

```python
from typing import TypedDict, Literal, Optional
from datetime import datetime

AgentID = Literal["orchestrator","qed","superconductivity",
                  "photocurrent","qtm","qsim","xchiral"]

class Message(TypedDict):
    role:      Literal["user", "assistant", "tool"]
    content:   str
    timestamp: str          # ISO
    user_id:   Optional[str]  # Teams user ID; None for agent-initiated

class TaskRecord(TypedDict):
    task_id:    str
    task_type:  str          # "code_review" | "analysis" | "pr_open" | ...
    repo:       Optional[str]
    outcome:    str          # "success" | "failed" | "cancelled"
    summary:    str          # 1-2 sentence human-readable result
    timestamp:  str

class ApprovalRequest(TypedDict):
    operation_id:  str
    tier:          int           # T2 | T3 | T4
    description:   str
    manifest:      Optional[str] # JSON string; required for T4
    requested_at:  str
    requested_by:  str           # agent_id that triggered the action
    approve_by:    list[str]     # Teams user IDs authorised to approve

class AgentState(TypedDict):
    # ── Identity ──────────────────────────────────────────────────────
    agent_id:       AgentID
    session_id:     str          # Teams conversation_id
    active_user:    Optional[str]   # Teams user ID of current interlocutor
    active_channel: Optional[str]   # Teams channel or DM thread ID

    # ── Conversation (rolling window + summary fallback) ──────────────
    messages:               list[Message]   # last N full turns (see §4.3)
    conversation_summary:   Optional[str]   # summarised older turns
    turns_since_summary:    int

    # ── Current task ──────────────────────────────────────────────────
    current_task:   Optional[dict]      # free-form task description
    task_history:   list[TaskRecord]    # lightweight log of this session's tasks

    # ── Approval ──────────────────────────────────────────────────────
    pending_approval: Optional[ApprovalRequest]

    # ── Context assembled for this call (rebuilt each turn) ───────────
    rag_chunks:       list[dict]   # top-5 reranked chunks from Qdrant
    episodic_context: list[dict]   # recent events from SQLite

    # ── Proactive loop (orchestrator only) ────────────────────────────
    last_trigger_check: Optional[str]   # ISO timestamp
```

### 4.3 Conversation rolling window + summarisation fallback (G4.2)

Long conversations cannot be preserved in context indefinitely.
The strategy: keep as large a rolling window as the budget allows,
with automatic summarisation when the window fills.

**Context window setting:** `max_model_len=32768` (see DGX_SETUP.md §4 —
update from 8192). At INT8 on 128GB unified memory:

| Component | Memory |
|---|---|
| Hermes 3 70B weights (INT8) | ~70 GB |
| KV cache at 32K context | ~10 GB |
| Embedding models | ~1 GB |
| **Total** | **~81 GB** — 47 GB headroom |

**Revised token budget at 32K:**

| Slot | Tokens | Notes |
|---|---|---|
| System prompt + skills | 1,500 | |
| Conversation rolling window | 15,000 | ~50–60 turns at avg. 250 tokens/turn |
| Conversation summary | 800 | Injected above rolling window when active |
| RAG chunks (top 5) | 2,500 | |
| Episodic context | 1,200 | |
| Current message + task | 500 | |
| Tool outputs (hard cap) | 2,000 | |
| **Usable input total** | **23,500** | 72% of 32K window |
| Output buffer | **9,268** | |

**Summarisation trigger:** when `len(messages)` exceeds 60 turns OR total
token count of `messages` exceeds 14,000:

```
1. Take oldest 30 turns from messages[]
2. Call Hermes with instruction: "Summarise this conversation segment in
   ≤400 tokens, preserving: decisions made, tasks completed, key findings,
   any open questions."
3. Store summary in SQLite (session_id + timestamp)
4. If conversation_summary already exists: prepend new summary to existing,
   re-summarise to ≤800 tokens total (summary-of-summaries)
5. Remove the 30 summarised turns from messages[]
6. Reset turns_since_summary counter
```

On each call, the context is assembled as:
```
[system prompt]
[conversation_summary]  ← if present
[last N messages]       ← rolling window
[episodic_context]
[rag_chunks]            ← rank-1 first, rank-2 last
[current message]
```

### 4.4 Persistence implementation — LangGraph checkpointer

LangGraph has a built-in **checkpointer** that saves the full `AgentState`
to a backing store after every node execution, keyed by a thread ID. This
is the primary persistence mechanism. No custom serialisation is needed.

```python
from langgraph.checkpoint.sqlite import SqliteSaver

checkpointer = SqliteSaver.from_conn_string(
    "/opt/qnoe-agent/memory/checkpoints.db"
)

graph = StateGraph(AgentState)
# ... add nodes and edges ...
compiled = graph.compile(checkpointer=checkpointer)

# Each invocation passes the thread_id (= Teams conversation_id)
config = {"configurable": {"thread_id": teams_conversation_id}}
result = compiled.invoke({"messages": [new_message]}, config=config)
```

On every message the framework automatically:
1. Loads the most recent checkpointed `AgentState` for this `thread_id`
2. Runs the graph from that state
3. Saves the updated state back to the checkpointer

A DGX restart loses nothing. Sessions persist indefinitely.

**Storage layout:**

| Store | Contents | Keyed by |
|---|---|---|
| LangGraph SQLite checkpointer | Full `AgentState` snapshots | `thread_id` (Teams conversation_id or thread_id) |
| Episodic SQLite tables | Events, task outcomes, audit log, approval records | `session_id`, `timestamp` |
| Qdrant | Semantic memory — group knowledge | Collection + vector similarity |

The checkpointer handles the rolling window and summary fields as part of
`AgentState` — they are saved and loaded automatically. The episodic tables
provide richer queryable history for reconstructing `episodic_context`.
Qdrant is stateless from the conversation's perspective — queried fresh
on every turn.

**Channel threads (multi-user):** keyed by `thread_id` (Teams thread ID).
The `active_user` field updates per message. The conversation summary
captures the full thread history across all participants.

---

When the orchestrator receives a query that spans multiple sub-teams, it
fans out to the relevant sub-agents, collects their independent responses,
and synthesises.

### 5.1 Fan-out pattern

```
Orchestrator receives: "Has anyone in QED or QSIM done band structure
                        calculations relevant to the BSCCO device?"

1. Orchestrator identifies relevant sub-agents: [qed, qsim]
2. Fan-out: spawn two independent LangGraph calls in parallel
      qed_response  = await call_subagent("qed",  query, context)
      qsim_response = await call_subagent("qsim", query, context)
3. Collect both responses
4. Orchestrator calls Hermes with synthesis prompt:
      "Given these two sub-team responses, produce a unified answer..."
5. Post synthesised answer to user
```

Sub-agent calls in step 2 run as Python `asyncio` tasks — genuinely
parallel, each using the shared vLLM endpoint (which handles concurrent
requests via batching internally).

### 5.2 Each sub-agent call is a lightweight stateless query

For cross-team synthesis, the sub-agent is called without a full session —
just a focused single-turn query against its own RAG collection. No
conversation state is created or modified. The sub-agent returns a
structured response dict:

```python
{
    "sub_team":  "qed",
    "found":     True,
    "answer":    "...",
    "sources":   ["BLG-QED/notebooks/band_calc.ipynb", "..."]
}
```

The orchestrator's synthesis call receives both dicts and produces the
final user-facing answer.

---

## G6 — Teams message threading model

### 6.1 Single bot architecture

One bot is registered in Teams. Seven separate bot registrations are not
needed. The single bot handles all sub-agents and the orchestrator,
routing internally based on the user's declared sub-team.

**On the first message in any new conversation** (no existing session found),
the bot sends a one-time disambiguation card before doing anything else:

```
Hello! I'm the QNOE lab agent.
Which sub-team are you working with?

[ QED ]  [ Superconductivity ]  [ Photocurrent ]
[ QTM ]  [ QSIM ]  [ XCHIRAL ]  [ Full lab / unsure ]
```

The user's choice is stored in their session permanently. All subsequent
messages are routed to the corresponding sub-agent without asking again.

### 6.2 The `/switch` command

Users can change their active sub-agent at any time by typing `/switch`.
The bot responds with the same disambiguation card.

**Every sub-agent knows about this command.** It is injected into every
sub-agent's system prompt:

```
If a user asks how to talk to a different sub-agent, or mentions they are
working on something outside your sub-team's scope, tell them:
"You can switch to a different sub-agent at any time by typing /switch."
```

This means users never need external documentation to discover the command —
they can simply ask the agent they are already talking to.

### 6.3 Interaction modes

| Mode | How it works | Routing | Session keyed to |
|---|---|---|---|
| **DM (new user)** | Bot sends disambiguation card | User picks sub-team | `conversation_id` (permanent) |
| **DM (returning user)** | Routes directly to stored sub-agent | Sub-agent for their team | `conversation_id` |
| **Channel @mention** | Bot responds in thread | Sub-agent for that team's channel | `thread_id` |
| **DM orchestrator** | User picks "Full lab / unsure" | Orchestrator | `conversation_id` |
| **Proactive post** | Agent initiates | Sub-agent or orchestrator | No incoming session |

### 6.4 Proactive posting rules

Each sub-agent posts only to its own sub-team channel. The orchestrator
posts only to the group-wide channel. Neither posts to another team's
channel.

```
QED-Agent             → #qed
Superconductivity-Agent → #superconductivity
Photocurrent-Agent    → #photocurrent
QTM-Agent             → #qtm
QSIM-Agent            → #qsim
XCHIRAL-Agent         → #xchiral
Orchestrator          → #lab-general
```

### 6.6 User commands — full list

| Command | Where | Behaviour |
|---|---|---|
| `/switch` | DM + channel | Sends disambiguation card; user picks new sub-team |
| `/help` | DM + channel | Returns sub-team-specific capability list with one example per item |
| `/new` | DM only | Resets conversational context; preserves sub-team and all group knowledge |

#### `/new` — fresh conversation start

The user types `/new` when they want to start a completely new conversation
without prior context bleeding in. The agent:

1. Archives current session state to SQLite (nothing deleted — audit trail preserved)
2. Clears from `AgentState`: `messages[]`, `conversation_summary`, `current_task`, `pending_approval`
3. Creates a new checkpoint entry (new internal session ID, same `conversation_id`)
4. Confirms: *"Starting fresh. I still know your sub-team is [X] and have full access to group knowledge — I just won't carry forward our previous conversation. What are you working on?"*

**What `/new` clears vs. preserves:**

| Cleared | Preserved |
|---|---|
| Message rolling window | Sub-team selection |
| Conversation summary | All of Qdrant (group knowledge) |
| Current task | Episodic task history in SQLite |
| Pending approvals | Agent skills and tools |

`/new` resets *conversational context*, not *knowledge*. The distinction:
the agent no longer remembers what you discussed, but still knows the
group's full codebase, papers, and past task history.

**Natural language variants:** if a user says "forget everything we talked
about" or "let's start over," the agent replies: *"Type `/new` for a clean
conversation start."* It does not attempt to self-edit memory in-context.

**In channel threads:** not needed. Each thread is already a separate
session keyed to `thread_id`. Starting a new thread = new session automatically.

**Proactive suggestion:** agents surface `/new` when the conversation has
clearly drifted to a new unrelated topic: *"This seems like a different
topic from our earlier discussion — type `/new` if you'd like a clean start."*

This line is injected into every sub-agent system prompt.

### 6.7 Teams connector — service account and polling

**Integration method: Graph API polling via dedicated service account**

The agent connects to Teams as a dedicated user account (`qnoe-ai@icfo.net` or
equivalent — IT has been asked to create this). It is not a registered bot
application. Rationale:

- No Azure Bot Service registration required
- No inbound webhook endpoint required (works on private campus network)
- All communication is outbound HTTPS to `graph.microsoft.com` — already
  covered by the OpenShell network policy
- The account appears as a regular Teams user; researchers DM it or @mention
  it in sub-team channels
- Credentials managed as an OpenShell provider (injected as env var,
  never on container filesystem)

**Polling strategy: adaptive two-mode**

| Mode | Poll interval | Trigger |
|---|---|---|
| Active | 3 s | Any message received; stays active for 5 min after last message |
| Idle | 30 s | Default; no messages in last 5 min |

**Endpoints polled (Graph API delta queries):**
- DM inbox: `GET /me/chats?$filter=chatType eq 'oneOnOne'` + per-chat delta
- Sub-team channels (7): `GET /teams/{id}/channels/{id}/messages/delta`
- Delta tokens are persisted in SQLite episodic store between restarts

**Why delta queries:** each poll returns only messages newer than the last
delta token — zero overhead when channels are quiet.

**API usage:** ~960 calls/hour (idle) → ~5,500 calls/day — well within
Graph API throttling limits (100 req/s per application per tenant).

**Responding:** POST to the same Graph API endpoint (`/replies` for channel
threads, `/messages` for DMs). No inbound connections needed.

---

## G7 — Proactive trigger list

The orchestrator's background loop checks these triggers on each sweep
(suggested interval: every 30 minutes). All triggers are T0 (read-only);
any resulting action goes through the normal T0–T4 permission system.

### 7.1 Repository triggers

| Trigger | Condition | Default threshold | Action |
|---|---|---|---|
| Stale PR | PR open with no activity | > 48 hours | Notify PR author in DM + tag in thread |
| New commit | Any commit pushed to a watched repo | Immediate (detected on next sweep) | Post to sub-team channel: repo, author, commit message |
| Failing notebook | `.ipynb` has cells with error outputs | Any | Notify repo owner in DM with cell reference |

*Stale repo (no commits > N weeks) was considered and rejected: measurement
repos legitimately go quiet for weeks while experiments run. Too many false
alarms.*

*Missing analysis output was considered and rejected: too ambiguous to
define reliably across the group's varied notebook conventions.*

### 7.2 Literature triggers

| Trigger | Condition | Action |
|---|---|---|
| New paper indexed | PDF newly added to literature store and indexed overnight | Sub-agent generates 3-sentence summary + relevance note; posts to sub-team channel |

### 7.3 Data triggers

| Trigger | Condition | Action |
|---|---|---|
| Unusually large new file | Any non-DB file appearing on data server > N GB | Notify sub-team channel; offer preliminary analysis |

*New measurement completed (DB trigger) was considered and rejected:
QCoDeS databases write continuously for extended periods with no clean
"done" signal. Reliable detection is not possible.*

### 7.4 Configurable thresholds

All thresholds are stored in `/opt/qnoe-agent/config/triggers.yaml`,
editable by the maintainer without touching code:

```yaml
triggers:
  stale_pr_hours: 48
  large_file_gb: 5.0
  sweep_interval_minutes: 30
```

---

## QCoDeS measurement data — registry + summary cards

### Problem

QCoDeS `.db` files are SQLite databases containing structured measurement metadata (experiment name, sample, parameters, timestamps, station snapshots). The current ingestion pipeline (`splitter.py:_chunk_qcodes_db`) extracts this metadata and generates summary-card chunks, but they are stored in `group-wide` alongside ~588k other points — where they are effectively buried. Semantic search for "Hall measurement on BLG device 7" will rarely surface a QCoDeS summary card competing against hundreds of thousands of prose and code chunks.

Additionally, semantic search alone cannot answer structured queries like "runs between March and May with B > 1T" or "all measurements on device SLG07 sorted by date." These require a queryable registry.

### Design — two complementary layers (Phase 1)

#### Layer A: `qcodes-runs` Qdrant collection (semantic discovery)

A dedicated Qdrant collection containing one summary card per measurement run. Each card is a natural-language description generated from QCoDeS metadata:

```
QCoDeS measurement run
Experiment: Hall_effect_BLG
Sample: BLG-07
Run 42: gate_sweep_2T
Completed: 2025-03-14 14:23:00
Parameters: gate_voltage, Rxy, B_field
Database: experiments.db
Path: /ICFO/groups/NOE/Projects/QED/data/experiments.db
```

This text is embedded with nomic-embed and stored in `qcodes-runs`. Because the collection contains only measurement metadata (~thousands of points, not hundreds of thousands), relevant cards rank highly when a user asks about measurements.

**Surfacing into agent context:** `qcodes-runs` is added to `AGENT_COLLECTIONS` for every agent (all sub-teams may need measurement data). The existing `retrieval.py` automatically queries all collections in the agent's list and merges results by score. No changes to the retrieval logic are needed — the collection is simply included in the query fan-out.

#### Layer B: `qcodes_registry` SQLite table (structured queries)

A relational table cataloging every run across all QCoDeS databases:

```sql
CREATE TABLE qcodes_registry (
    id          INTEGER PRIMARY KEY,
    db_path     TEXT NOT NULL,
    run_id      INTEGER NOT NULL,
    experiment  TEXT,
    sample      TEXT,
    parameters  TEXT,       -- JSON list of parameter names
    instruments TEXT,       -- JSON from station snapshot (if available)
    start_time  TEXT,
    end_time    TEXT,
    num_points  INTEGER,
    notes       TEXT,
    UNIQUE(db_path, run_id)
);
```

In Phase 1, this table exists and is populated but is not directly queryable by the agent (no SQL tool). Its primary consumers are:
- The nightly scanner (reads it to know what's already cataloged)
- B3 skill in Phase 2 (`list_recent_runs()` queries this table)
- B2 overnight analysis (finds databases with new data by comparing against this table)

### Keeping it up to date

A new nightly task (`task_scan_qcodes`) is added to `nightly_run.py` and runs as part of the 02:00 cron job, after `task_index_server`:

1. **Discovery:** Query the `index_manifest` table for all files with `.db` extension. These are already tracked by the existing ingestion pipeline — no extra filesystem scan needed.
2. **QCoDeS check:** Open each `.db` read-only, check for the `experiments` and `runs` tables. Non-QCoDeS databases (configs, manifests) are skipped.
3. **Diff against registry:** For each QCoDeS database, compare runs in the DB against `qcodes_registry`. New runs (not yet in the registry) are inserted.
4. **Generate summary cards:** For each new run, generate a summary card (same logic as `splitter.py:_chunk_qcodes_db`) and upsert to the `qcodes-runs` Qdrant collection.
5. **Hash-based skip:** If the `.db` file's SHA-256 hasn't changed since the last scan (tracked in `index_manifest`), skip it entirely. QCoDeS databases only grow when new measurements are taken.

**Cost:** The scanner only opens databases that have changed. For unchanged databases (the vast majority on any given night), the cost is one SHA-256 hash comparison per file — negligible.

**Registry location:** Same manifest database used by the server ingestion (`/home/yzamir/qnoe_server_data/episodic.db`), in a new `qcodes_registry` table.

### What changes in the agent code

| File | Change |
|---|---|
| `prompts.py` | Add `qcodes-runs` to `AGENT_COLLECTIONS` for all agents |
| `nightly_run.py` | Add `task_scan_qcodes` to the TASKS list |
| `splitter.py` | No change — `_chunk_qcodes_db()` already generates the right format |
| `run_ingest.py` | No change — the scanner uses its own upsert logic for the dedicated collection |
| New: `agent/ingest/qcodes_scanner.py` | The scanner script: walks manifest, opens QCoDeS DBs, writes to registry + Qdrant |

### Phase 2 evolution (B3)

In Phase 2, the B3 skill (`PHASE2_BACKLOG.md §B3`) gives the agent a live query tool:
- `list_recent_runs()` queries `qcodes_registry` — the registry becomes the discovery index
- `load_dataset()` opens a database on-the-fly and extracts actual measurement data
- `get_run_metadata()` retrieves station config and parameter details

The Phase 1 registry and summary cards remain — B3 adds active access on top of passive discovery.

---

## Task list

### G4 tasks
- [ ] Update `max_model_len` to 32768 in vLLM launch config (DGX_SETUP.md §4)
- [ ] Define `AgentState` TypedDict in `agent/state.py`
- [ ] Implement session manager: look up or create instance by `conversation_id`
- [ ] Implement rolling window enforcer: cap at 60 turns / 14,000 tokens
- [ ] Implement summarisation trigger and summary-of-summaries compression
- [ ] Implement context assembly function (summary + window + episodic + RAG + message)
- [ ] Test parallel session isolation: two simultaneous conversations, verify no state bleed

### G5 tasks
- [ ] Implement `call_subagent()` as async function returning structured response dict
- [ ] Implement orchestrator fan-out: `asyncio.gather()` over relevant sub-agents
- [ ] Implement synthesis prompt template
- [ ] Test cross-team query end-to-end

### G6 tasks
- [ ] Register single Teams bot
- [ ] Implement disambiguation card (one-time on new session)
- [ ] Implement `/switch` command handler (resends disambiguation card)
- [ ] Inject `/switch` knowledge into every sub-agent system prompt
- [ ] Implement session keying by `conversation_id` (DM) and `thread_id` (channel)
- [ ] Implement proactive post router: each agent → its own channel only

### G7 tasks
- [ ] Create `/opt/qnoe-agent/config/triggers.yaml` with default thresholds
- [ ] Implement stale PR checker (GitHub API)
- [ ] Implement new commit detector (GitHub API — poll or webhook)
- [ ] Implement failing notebook detector (scan cell outputs for error metadata)
- [ ] Implement large file detector (scan data server for new files > threshold)
- [ ] Implement new paper notifier + summary generator
- [ ] Wire all triggers into orchestrator background loop
- [ ] Test each trigger in isolation before enabling all

---

## G10 — Researcher onboarding plan

### 10.1 Design principles

Researchers don't read documentation. Onboarding must be:
- **Self-contained** — the agent explains itself in the conversation
- **Low friction** — no setup steps, no accounts to create beyond Teams
- **Gradual** — read-only helpful features first, write access built on trust
- **Discoverable** — the agent surfaces its own capabilities contextually

### 10.2 First contact flow

When a researcher messages the bot for the first time:

```
Step 1 — Disambiguation card (G6)
  Bot: "Hello! I'm the QNOE lab agent. Which sub-team are you in?"
  User clicks their team.

Step 2 — Personalised introduction (sent immediately after sub-team selection)
  Bot: "I'm your [QED] sub-agent. Here's what I can help with:

  • Answer questions about your group's code, papers, and notebooks
  • Review and summarise recent changes in your repos
  • Find relevant analysis examples from the group's work
  • Notify you about failing notebooks and new papers
  • Help write or debug analysis scripts

  Type /help at any time for a command list.
  Type /switch to change sub-team.

  What are you working on?"
```

The introduction is sub-team specific — the QED agent mentions QED repos
and papers, not generic capabilities. This is controlled by the system
prompt template (G8).

### 10.3 `/help` command

Any agent responds to `/help` with a concise, sub-team-specific capability
list. Not a wall of text — a scannable list of what it can actually do
right now, with one example for each item.

### 10.4 Channel announcement

When the system first goes live, the maintainer posts a brief announcement
to each sub-team channel and to #lab-general. The agent itself does not
spam every researcher with a cold DM — it waits to be addressed. The
announcement template:

```
The QNOE lab agent is now live.

DM @QNOE-Agent to talk to your sub-team's agent.
It can answer questions about group code, papers, and notebooks,
notify you about repo activity, and help with analysis.

It will also post updates to this channel when new papers are indexed
or notable repo events happen.
```

### 10.5 Trust-building rollout sequence

Do not enable all capabilities on day one. Researchers need to build
confidence in the agent before trusting it with write actions.

| Week | Capabilities active | Goal |
|---|---|---|
| 1–2 | RAG Q&A only (T0) | Researchers discover it knows their codebase |
| 3–4 | + Proactive triggers (new papers, failing notebooks) | Researchers see it noticing things |
| 5–6 | + T2 write (own repo PRs, notebook runs) | First write actions, low stakes |
| 7+ | + T3/T4 with approval gates | Full capability with safety rails |

This sequence is enforced by a `phase` field in `triggers.yaml`:
```yaml
rollout_phase: 1   # increment manually to unlock next tier
```

---

## G11 — Failure and recovery procedures

### 11.1 Failure taxonomy

| Class | Examples | Detection |
|---|---|---|
| **Infrastructure** | vLLM crash, Qdrant unreachable, data server mount dropped | Health check ping at startup + on each loop tick |
| **Credential** | GitHub PAT expired, Teams bot token revoked | API call returns 401 |
| **Logic** | Agent loops, bad action before gate, wrong tool call | Watchdog timer + audit log anomaly |
| **Data** | Qdrant index corruption, SQLite locked | Exception on read/write |

### 11.2 Health check service

A lightweight health check runs every 5 minutes as a separate process,
independent of the main agent. If any component is unreachable, it sends
a DM to the maintainer via Teams immediately.

```python
HEALTH_CHECKS = [
    ("vLLM",    "GET http://localhost:8000/health"),
    ("Qdrant",  "GET http://localhost:6333/healthz"),
    ("SQLite",  "SELECT 1 FROM events LIMIT 1"),
    ("DataSrv", "os.path.exists('/mnt/qnoe-data')"),
    ("GitHub",  "GET https://api.github.com/orgs/QNOE-group"),
]
```

Health check failures alert the maintainer directly. The agent does not
attempt self-repair — it stops and waits for human intervention.

### 11.3 Recovery procedures per failure class

#### Infrastructure — vLLM or Qdrant crash
```
1. systemd auto-restarts the service (RestartSec=10)
2. Health check detects recovery and sends "back online" DM to maintainer
3. In-flight requests at time of crash are lost — no retry
4. Active sessions resume normally on next user message
   (state is in SQLite; context is rebuilt from scratch)
```

#### Infrastructure — data server mount dropped
```
1. Health check alerts maintainer
2. Agent continues operating in degraded mode:
   - RAG queries still work (Qdrant is local)
   - Analysis tasks that require live data are refused with clear message
   - Index re-run is skipped at next 02:00 job with logged warning
3. Maintainer remounts; health check confirms; normal operation resumes
```

#### Credential — GitHub PAT or Teams token expired
```
1. API call returns 401 → agent catches, logs to SQLite as credential_failure
2. Agent posts DM to maintainer: "GitHub PAT has expired. Repo operations
   suspended until renewed. Renew at /opt/qnoe-agent/secrets/github_pat"
3. Agent continues operating without GitHub access (RAG, Teams, analysis)
4. Maintainer renews credential; agent resumes on next API call attempt
```

#### Logic — runaway loop detected
A watchdog timer enforces a hard limit on consecutive tool calls within
one agent turn. If the agent calls more than 10 tools without returning
a response to the user, the turn is forcibly terminated:

```python
MAX_TOOL_CALLS_PER_TURN = 10

if state["tool_call_count"] > MAX_TOOL_CALLS_PER_TURN:
    return {
        "response": "I reached the tool call limit for this turn without "
                    "completing the task. Please rephrase or provide more "
                    "context.",
        "outcome": "watchdog_terminated"
    }
```

The terminated turn is logged to the audit trail with full tool call
history so the maintainer can inspect what the agent was attempting.

#### Data — Qdrant index corruption
```
1. Exception on Qdrant read/write → log to SQLite, alert maintainer
2. Check: is the collection accessible at all?
   - Yes → single point corruption; delete and re-index the affected file
   - No  → full collection rebuild required
3. Full rebuild: stop agent, delete collection, re-run initial indexing script
   Expect 2–4 hours. Agent is offline during rebuild.
4. Prevention: Qdrant snapshots run nightly (add to 02:00 cron job)
```

### 11.4 Qdrant nightly snapshot

Added to the 02:00 cron job, before the indexing run:

```bash
# Snapshot all collections before re-indexing
curl -X POST "http://localhost:6333/collections/{collection}/snapshots"
# Snapshots stored at /opt/qnoe-agent/qdrant_snapshots/
# Keep last 7 days, delete older
find /opt/qnoe-agent/qdrant_snapshots/ -mtime +7 -delete
```

### 11.5 Escalation path

All failures escalate to the maintainer only. No other person is on-call.
The maintainer's Teams user ID is stored in `config/maintainer.yaml`.

```yaml
maintainer:
  teams_user_id: "YOUR_TEAMS_USER_ID"
  alert_on: [infrastructure, credential, logic, data]
```

If the maintainer is unreachable (e.g. on holiday), the agent operates in
degraded read-only mode — no write actions, no proactive posts — until the
maintainer responds.

### 11.6 What the agent tells users during outages

The bot always responds to incoming Teams messages, even during partial
outages. If the vLLM endpoint is down, a fallback handler (not using the
model) replies:

```
"I'm currently offline for maintenance. @[maintainer] has been notified.
I'll be back shortly."
```

This prevents the bot from going silent, which would be more alarming to
users than an honest status message.

---

## G9 — MVP scope

*To be defined. Awaiting decision on:*
- Which sub-team to build first (user's primary sub-team)
- Agent name / persona style (for system prompt design — G8)

*Once decided, this section will define: which repos are indexed in v1,
which three capabilities are demonstrated, and the acceptance criteria
for "working."*

---

## G8 — System prompt design

### 8.1 Agent names

| Agent | Name |
|---|---|
| Lab-wide orchestrator | `QNOE-Agent` |
| QED sub-agent | `QED-Agent` |
| Superconductivity sub-agent | `Superconductivity-Agent` |
| Photocurrent sub-agent | `Photocurrent-Agent` |
| QTM sub-agent | `QTM-Agent` |
| QSIM sub-agent | `QSIM-Agent` |
| XCHIRAL sub-agent | `XCHIRAL-Agent` |

### 8.2 Communication style (all agents)

These rules apply to every agent without exception. They are injected
into every system prompt as a shared style block.

```
STYLE:
- Your users are expert physicists. Be concise and technical.
- Cite sources explicitly: file path, function name, paper section, or
  run ID. Never assert something from the knowledge base without saying
  where it came from.
- Use inline LaTeX notation when relevant (e.g. $\hbar\omega$, $k_BT$,
  $\nu = 2$ filling factor).
- Push back if a request is methodologically questionable. State your
  concern once, briefly, then do what was asked if the user confirms.
- Admit uncertainty directly: say "I don't know" or "not in my knowledge
  base." Never apologise for it.
- Do not start responses with "Certainly!", "Great!", "Of course!",
  "Absolutely!", or any similar filler.
- Do not pad answers. If the answer is one sentence, write one sentence.
```

### 8.3 Orchestrator system prompt

```
You are QNOE-Agent, the lab-wide AI assistant for the QNOE group
(ICFO, Barcelona). PI: Frank Koppens. Lab manager: David Alcaraz.

ROLE:
You are the orchestrator. You route incoming messages to the correct
sub-agent based on sub-team context. You handle cross-team queries by
consulting multiple sub-agents in parallel and synthesising their
answers. You post group-wide updates to #lab-general only.

SUB-TEAMS AND SCOPE:
- QED-Agent:               cavity QED, BLG devices, polaritons,
                           light-matter coupling
- Superconductivity-Agent: BSCCO, MoO3-hBN-MoO3, hyperbolic materials
- Photocurrent-Agent:      quantum Hall photocurrents, graphene
                           transport, GRASP sensing platform
- QTM-Agent:               quantum tunnelling microscopy, cryogenic
                           measurements, Opticool system
- QSIM-Agent:              simulations, Kagome lattice, MEEP FDTD,
                           condensed matter theory
- XCHIRAL-Agent:           chirality experiments and analysis

ROUTING RULES:
1. Message clearly belongs to one sub-team → route to that agent.
2. Message spans multiple sub-teams → consult relevant agents in
   parallel, synthesise.
3. Sub-team ambiguous → ask which team the user is working on.
4. User says /switch → send disambiguation card.

TOOLS: {SKILL_DEFINITIONS}

PERMISSIONS:
T0 read/analyse — always permitted.
T1 draft/suggest — always permitted.
T2 write own repo — requires confirmation from repo owner.
T3 write shared resources — requires designated approver.
T4 destructive — full safety stack: scope lock → dry-run manifest →
  typed confirmation → 5-minute snapshot window.

FAILURE HANDLING:
If retrieval returns no results above threshold, state this explicitly,
name the collections searched, and return to the user. Do not retry
automatically. Do not loop. Do not fabricate.

USER COMMANDS:
/switch — send disambiguation card.
/help   — list your routing capabilities with one example each.

{STYLE_BLOCK}
```

### 8.4 Sub-agent system prompt template

One template, parameterised per sub-agent. Variables in `{BRACES}`.

```
You are {AGENT_NAME}, the AI assistant for the {SUBTEAM_NAME} sub-team
of the QNOE group (ICFO, Barcelona).

You have deep expertise in {SUBTEAM_DESCRIPTION}. Behave like a
competent postdoc embedded in the {SUBTEAM_NAME} sub-team.

SCOPE — PRIMARY REPOSITORIES:
{REPO_LIST}

You also have access to group-wide literature and shared tools.
For topics clearly outside {SUBTEAM_NAME}, tell the user:
"This looks like a question for a different sub-team. Type /switch
to connect to the right agent."

PROACTIVE CHANNEL:
Post updates and notifications to {CHANNEL} only. Never post to
other sub-team channels or to #lab-general.

TOOLS: {SKILL_DEFINITIONS}

PERMISSIONS:
T0 read/analyse — always permitted.
T1 draft/suggest — always permitted.
T2 write to repos within {SUBTEAM_NAME} scope — requires confirmation
  from the repo owner.
T3 write to shared group resources — requires designated approver.
T4 destructive operations — full safety stack required.

FAILURE HANDLING:
If retrieval returns no results above threshold, say:
"I could not find relevant information in the {SUBTEAM_NAME} knowledge
base for this query. Sources checked: {COLLECTIONS_SEARCHED}. You may
need to provide the context directly, or this information may not yet
be indexed."
Do not retry. Do not loop. Do not fall back to general knowledge
without explicitly saying you are doing so.

USER COMMANDS:
/switch — tell the user: "You can switch to a different sub-agent at
  any time by typing /switch." Then send the disambiguation card.
/help   — respond with a concise, {SUBTEAM_NAME}-specific capability
  list. One example per item. Keep it under 10 lines.

{STYLE_BLOCK}
```

### 8.5 Per-sub-agent variable values

| Variable | QTM-Agent | Photocurrent-Agent |
|---|---|---|
| `{AGENT_NAME}` | QTM-Agent | Photocurrent-Agent |
| `{SUBTEAM_NAME}` | QTM | Photocurrent |
| `{SUBTEAM_DESCRIPTION}` | quantum tunnelling microscopy, cryogenic measurement systems, and the Opticool platform | quantum Hall photocurrents, graphene transport, and the GRASP sensing platform |
| `{REPO_LIST}` | QTM_CodeBase, L208_Opticool | SLG04/05/07/09-PhQH, SLG09-C2-PhQH, Elisa-codes, GRASP-Acquisition, GRASP-Analysis, GRASP-TWINS |
| `{CHANNEL}` | #qtm | #photocurrent |
| `{COLLECTIONS_SEARCHED}` | qtm-prose, qtm-code, group-wide-prose, group-wide-code | photocurrent-prose, photocurrent-code, group-wide-prose, group-wide-code |

*Remaining four agents (QED, Superconductivity, QSIM, XCHIRAL) to be
filled in during Phase 2 rollout.*

---

## G9 — MVP scope

### 9.1 Agents in scope for MVP

| Agent | In MVP | Reason |
|---|---|---|
| QNOE-Agent (orchestrator) | ✅ | Required for routing and Teams integration |
| QTM-Agent | ✅ | Maintainer's own sub-team — primary for evaluation |
| Photocurrent-Agent | ✅ | Largest sub-team — broadest early test |
| QED-Agent | ❌ Phase 2 | |
| Superconductivity-Agent | ❌ Phase 2 | |
| QSIM-Agent | ❌ Phase 2 | |
| XCHIRAL-Agent | ❌ Phase 2 | |

### 9.2 Capabilities in scope per phase for MVP agents

**Phase 1 — T0/T1 only (read, suggest)**

| Capability | Description |
|---|---|
| RAG Q&A | Answer questions about QTM + Photocurrent repos, notebooks, and literature |
| Routing | Orchestrator correctly routes between QTM-Agent and Photocurrent-Agent |
| Failing notebook trigger | Detect error outputs; DM repo owner |
| New paper trigger | Summarise newly indexed PDFs; post to sub-team channel |
| /help and /switch | Working in all DM and channel contexts |
| Cross-team synthesis | Orchestrator queries both sub-agents in parallel |

**Phase 2 — Add T2–T4 (write access for QTM + Photocurrent only)**

| Capability | Description |
|---|---|
| T2 PR / commits | Open PRs, suggest edits on own repos; user confirmation required |
| T3 shared writes | Write to shared tool repos; named approver required |
| T4 destructive | Soft-delete with full 4-layer safety stack |
| Approval gate | Teams-based approval flow, audit log, watchdog timer |
| Stale PR trigger | Now actionable — agent can comment or ping rather than just notify |

*Rationale: T2–T4 infrastructure is the same work for 2 agents as for 6.
Proving it on QTM + Photocurrent first gives a validated, debugged permission
system before it reaches 4 additional teams.*

### 9.3 Initial corpus for MVP indexing

Only QTM and Photocurrent repos are indexed in the first run, plus
group-wide shared literature. This keeps the initial indexing time
short and keeps the RAG scope tight for evaluation.

| Source | Included in MVP |
|---|---|
| QTM_CodeBase | ✅ |
| L208_Opticool | ✅ |
| SLG04/05/07/09-PhQH repos | ✅ |
| GRASP-Acquisition / Analysis / TWINS | ✅ |
| Elisa-codes | ✅ |
| Group-wide literature (all PDFs) | ✅ |
| All other sub-team repos | ❌ Phase 2 |

### 9.4 Acceptance criteria

> **Rescoped 2026-07-10 (user decision):** MVP-1 = the *interactive read-only assistant* — criteria 1-4 and 7-9.
> Criteria **5, 6, 10** (proactive triggers + cross-team fan-out) were never implemented and are deferred to
> Phase 2 as [[PHASE2_BACKLOG]] **B8 / B9 / B10**. Status at rescope: #2, #4, #9 verified live (see
> [[SETUP_LOG]] 2026-07-10 verification round — on gpt-oss-120b, exceeding this spec: per-user Mem0 memory,
> deterministic QCoDeS registry grounding, 4×64K multi-user serving); #1, #3, #7, #8 pending the
> [[MVP_VERIFICATION_PLAN]] tests.

The MVP is considered working when all of the following pass:

| # | Test | Pass condition |
|---|---|---|
| 1 | Routing | Message from QTM context → QTM-Agent handles it, not orchestrator directly |
| 2 | RAG — code | Question about QTM_CodeBase returns relevant function with correct file path |
| 3 | RAG — paper | Question about a photocurrent paper returns correct section with citation |
| 4 | RAG — failure | Query with no indexed results returns explicit failure message, no hallucination |
| 5 | Failing notebook | Error cell in QTM repo → DM to repo owner within one sweep cycle |
| 6 | New paper | New PDF in literature store → summary posted to correct channel next morning |
| 7 | /switch | Works from both DM and channel context |
| 8 | /help | Returns sub-team-specific list, not generic response |
| 9 | Parallelism | Two simultaneous conversations (QTM + Photocurrent) complete without state bleed |
| 10 | Cross-team | Orchestrator queries both sub-agents for a cross-team question; synthesised answer mentions both |
