# Inference + Memory Model
*Last updated: 2026-05-29 — Mem0 added as user-memory layer*

> Claude Code memory: [[memory/ingestion]] · Decisions: [[memory/decisions#D1 — Hermes 3 70B AWQ as base model]] · [[memory/decisions#D2 — nomic-embed-text-v1.5 for all embeddings]]

---

## Overview

**Inference:** Hermes 3 70B (AWQ INT8) served via vLLM on the DGX Spark,
exposing an OpenAI-compatible endpoint at `localhost:8000`. All agents —
orchestrator and sub-agents — call the same endpoint; persona and scope are
controlled by system prompts.

**Memory:** Four-layer system — Qdrant RAG (semantic knowledge), Mem0
(user-level persistent facts), SQLite (episodic/audit), flat skill registry
(procedural). All local, no cloud dependencies.

---

## Memory layers — build in order

| Layer | Store | What it holds | Answers |
|---|---|---|---|
| L1 | Qdrant (dense vectors) | Documents, code, papers, notebooks | What does the group know about this topic? |
| L2 | Qdrant + BM25 sparse | Same as L1, adds exact-term matching | Device IDs, function names, paper titles |
| L3 | SQLite episodic | Conversation events, task outcomes, audit log | What has the agent done in this session? |
| L3.5 | Mem0 → Qdrant | Distilled per-user facts across all conversations | Who is this user and what do I know about them? |
| L4 | Skill registry | Versioned Python tool packages | What tools can the agent call? |
| L5 | KùzuDB knowledge graph | Entities and relationships (Phase 2, deferred) | How are things connected? |

---

## L1 — Qdrant dense vector RAG

### 1.1 Collections schema

7 collections total: one per sub-team plus group-wide. All use
nomic-embed-text-v1.5 (768-dim) for both prose and code content.

| Collection | Content |
|---|---|
| `group-wide` | Group papers, shared docs, READMEs, shared tool repos |
| `qed` | QED papers, notebooks, Python files |
| `superconductivity` | — |
| `photocurrent` | — |
| `qtm` | — |
| `qsim` | — |
| `xchiral` | — |

*Earlier designs proposed a prose/code split (7 + 7 collections with CodeBERT
for code). Dropped — nomic-embed handles code well, CodeBERT is old (2020,
512-token limit), and the split doubled storage and retrieval complexity
for no demonstrated benefit.*

### 1.2 Ingestion tools

| Content type | Tool | Install |
|---|---|---|
| Papers, books, presentations (PDFs) | Docling + DoclingNodeParser | `pip install docling llama-index-readers-docling` |
| Python files | LlamaIndex CodeSplitter (tree-sitter) | `pip install tree-sitter tree-sitter-language-pack` |
| Jupyter notebooks | LlamaIndex IPYNBReader | built into llama-index-core |
| QCoDeS metadata | ~15 lines custom extractor | write once |

### 1.3 Chunking strategy

| Content | Strategy |
|---|---|
| Papers | Section-level: abstract / methods / results / conclusions |
| Books | Paragraph-level with chapter → section hierarchy auto-prefixed |
| Python | Function/class-level via AST (CodeSplitter) |
| Notebooks | Cell-level; all cells embedded with nomic-embed |
| QCoDeS `.db` | Metadata only: device, experiment parameters, date, linked analysis repo |

### 1.4 Retrieval pipeline

```
1. Embed query with nomic-embed
2. Query sub-team collection + group-wide collection, top-20 each
3. Apply metadata filters if available (content_type, repo, date range)
4. Cross-encoder rerank → top-5
5. Anti-lost-in-middle ordering: rank-1 first, rank-2 last, ranks 3–5 in middle
6. Inject into context with source attribution
```

**Retrieval failure:** if all reranked chunks score < 0.3, declare failure
explicitly — name collections searched, return to user. No silent fallback
to parametric knowledge.

### 1.5 Scheduled re-indexing (G3)

| Source | Extensions | Schedule |
|---|---|---|
| GitHub repos | `.py`, `.ipynb`, `.md` | Daily at 02:00 |
| QCoDeS databases | `.db` | Daily at 02:30 (+ 24h stationary check) |
| Word / Office docs | `.docx`, `.pptx`, `.xlsx` | Weekly, Sunday 03:00 |
| Literature PDFs | `.pdf` | Weekly, Sunday 04:00 |

Change detection is hash-based (SHA-256), not timestamp-based. Hashes and
Qdrant point IDs are stored in SQLite `index_manifest` table. Unchanged
files are never re-processed.

---

## L2 — BM25 hybrid search

Add sparse vector support to Qdrant after L1 is working. Enables exact-term
matching for device IDs (`SLG07-C2`), function names (`load_by_id`), paper
titles. Qdrant supports this natively — it's an upgrade to L1, not a new system.

---

## L3 — SQLite episodic store

Stores structured, queryable records of what the agent has done. Separate
from the LangGraph checkpointer (which stores full `AgentState` for session
continuity). Used to reconstruct `episodic_context` at the start of each turn.

### Tables

```sql
-- One row per significant agent action or task outcome
CREATE TABLE events (
    id          INTEGER PRIMARY KEY,
    session_id  TEXT NOT NULL,        -- Teams conversation_id
    user_id     TEXT,                 -- Teams user ID
    agent_id    TEXT NOT NULL,        -- qed | qtm | photocurrent | ...
    task_type   TEXT NOT NULL,        -- code_review | analysis | pr_open | ...
    repo        TEXT,
    outcome     TEXT NOT NULL,        -- success | failed | cancelled
    summary     TEXT NOT NULL,        -- 1-2 sentence human-readable result
    timestamp   TEXT NOT NULL         -- ISO 8601
);

-- Audit trail for all T2–T4 actions
CREATE TABLE audit_log (
    id           INTEGER PRIMARY KEY,
    operation_id TEXT NOT NULL,
    tier         INTEGER NOT NULL,    -- 2 | 3 | 4
    description  TEXT NOT NULL,
    manifest     TEXT,                -- JSON; required for T4
    approved_by  TEXT,
    timestamp    TEXT NOT NULL
);
```

---

## L3.5 — Mem0 user memory

### What it does

Mem0 extracts and persists **distilled facts about individual users across
all conversations**. Unlike the SQLite episodic store (which records what
the agent *did*), Mem0 records what the agent has *learned about a person*:
their preferences, working style, recurring context, and past decisions.

Examples of what Mem0 stores:
- "Prefers Python over MATLAB for data analysis"
- "Works primarily on BLG devices in QED sub-team"
- "Decided in April 2026 to switch from QCoDeS to custom DAQ pipeline"
- "Wants verbose explanations for signal processing topics"

This is the layer that enables the agent to feel like it *knows* a researcher
over time — not just within a single conversation thread, but across months
of interaction.

### Configuration (fully local, no cloud)

```python
from mem0 import Memory
import qdrant_client

# One-time setup: create keyword index on user_id in Qdrant
# (required by Mem0 for per-user filtering)
client = qdrant_client.QdrantClient(host="localhost", port=6333)
client.create_payload_index(
    collection_name="episodic_memory",
    field_name="user_id",
    field_schema="keyword"
)

# Mem0 config — points at existing DGX infrastructure
mem0_config = {
    "vector_store": {
        "provider": "qdrant",
        "config": {
            "collection_name": "episodic_memory",   # dedicated collection, separate from RAG
            "host": "localhost",
            "port": 6333,
            "embedding_model_dims": 768,            # nomic-embed-text-v1.5 dims
        },
    },
    "llm": {
        "provider": "openai",                       # vLLM exposes OpenAI-compatible endpoint
        "config": {
            "model": "hermes-3-70b",
            "openai_base_url": "http://localhost:8000/v1",
            "api_key": "not-needed",
        },
    },
    "embedder": {
        "provider": "huggingface",
        "config": {
            "model": "nomic-ai/nomic-embed-text-v1.5",
        },
    },
}

memory = Memory.from_config(mem0_config)
```

### How it integrates into the turn loop

```
Message arrives from user (user_id = "frank@icfo.eu")
    ↓
[L3.5] memory.search(query=message, user_id=active_user, limit=5)
       → top-5 user-fact memories injected into episodic_context
    ↓
[L3]   SQLite query: recent task events for this user
       → appended to episodic_context
    ↓
[L1/L2] Qdrant RAG: semantic retrieval for current message
       → rag_chunks
    ↓
Assemble context → call Hermes
    ↓
Generate response
    ↓
[L3.5] memory.add(messages=[user_turn, assistant_turn], user_id=active_user)
       → Mem0 distils exchange into facts, stores in Qdrant episodic_memory
    ↓
Save AgentState to SQLite checkpointer
    ↓
Log task event to SQLite audit (if applicable)
```

### episodic_context structure

Both sources are tagged so Hermes can reason about them differently:

```python
# From Mem0 — cross-conversation user facts
{
    "source": "mem0",
    "memory": "User prefers Python over MATLAB for data analysis",
    "user_id": "frank@icfo.eu",
    "score": 0.87,
    "created_at": "2026-04-12T14:22:00"
}

# From SQLite — structured task history (unchanged)
{
    "source": "sqlite",
    "task_type": "code_review",
    "repo": "qed/blg-transport",
    "outcome": "success",
    "summary": "Fixed off-by-one in sweep range loop",
    "timestamp": "2026-04-12T14:22:00"
}
```

### Qdrant collection summary (updated)

| Collection | Purpose |
|---|---|
| `group-wide-prose` | Group knowledge RAG |
| `group-wide-code` | Group code RAG |
| `{subteam}-prose` × 6 | Sub-team knowledge RAG |
| `{subteam}-code` × 6 | Sub-team code RAG |
| `episodic_memory` | **Mem0 user facts — new** |

Total: 15 collections (up from 14).

---

## L4 — Skill registry

Versioned Python tool packages. Each skill is a callable module injected
into the agent's system prompt and available as a tool call. Skills are
loaded at agent startup and updated via the registry.

Format: `/opt/qnoe-agent/skills/<skill_name>/v<N>/skill.py`

---

## L5 — Knowledge graph (Phase 2, deferred)

KùzuDB. Entities and relationships: papers cite papers, code files import
each other, experiments use specific devices. Enables provenance tracing
and cross-sub-team relational queries. Not in scope for MVP.

---

## Context window budget

**Hermes 3 70B at `max_model_len=32768`:**

| Slot | Tokens | Source |
|---|---|---|
| System prompt + skill definitions | 1,500 | Skill registry |
| Conversation rolling window | 15,000 | SQLite checkpointer |
| Conversation summary | 800 | Auto-generated |
| Episodic — Mem0 user facts | 700 | Mem0 → Qdrant `episodic_memory` |
| Episodic — task history | 500 | SQLite events table |
| RAG chunks (top 5 after reranking) | 2,500 | Qdrant RAG collections |
| Current message | 500 | — |
| Tool outputs (hard cap per turn) | 2,000 | — |
| **Total input** | **23,500** | 72% of 32K window |
| Output buffer | 9,268 | Reserved for generation |

---

## Task list

### L1 tasks
- [ ] Install Docling: `pip install docling llama-index-readers-docling`
- [ ] Install tree-sitter: `pip install tree-sitter tree-sitter-language-pack`
- [ ] Verify `IPYNBReader` on a sample notebook
- [ ] Verify `CodeSplitter` on a sample repo file
- [ ] Deploy nomic-embed-text-v1.5 as persistent embedding service
- [x] ~~Deploy CodeBERT~~ — dropped; nomic-embed handles code well enough
- [x] 7 Qdrant RAG collections created ✅ *(prose/code split dropped)*
- [ ] Build unified ingestion pipeline (routes each file type to correct tool)
- [ ] Write QCoDeS metadata extractor (~15 lines)
- [ ] Implement scheduled re-indexing jobs (cron, hash-based)
- [ ] Deploy cross-encoder reranker (`cross-encoder/ms-marco-MiniLM-L-6-v2`)
- [ ] Write retrieval function with metadata filter + anti-lost-in-middle ordering
- [ ] RAG evaluation: 20 test queries, score retrieval accuracy

### L2 tasks
- [ ] Enable BM25 sparse vectors in Qdrant collections
- [ ] Update ingestion pipeline to generate sparse vectors alongside dense
- [ ] Update retrieval function to combine dense + sparse scores
- [ ] Evaluate exact-term recall improvement vs L1 baseline

### L3 tasks
- [ ] Create SQLite `events` table (schema above)
- [ ] Create SQLite `audit_log` table
- [ ] Implement event logger (called after each agent action)
- [ ] Implement episodic context query (last N events for user + session)

### L3.5 tasks — Mem0
- [ ] `pip install mem0ai`
- [ ] Create `episodic_memory` Qdrant collection
- [ ] Create `user_id` keyword index on `episodic_memory` collection (required)
- [ ] Configure Mem0 with local Qdrant + vLLM + nomic-embed (config above)
- [ ] Integrate `memory.search()` into turn loop (before RAG, after state load)
- [ ] Integrate `memory.add()` into turn loop (after response generation)
- [ ] Test per-user isolation: two users, verify no memory bleed
- [ ] Test cross-session recall: fact from session A surfaced in session B

### L4 tasks
- [ ] Define skill format spec and Python loader
- [ ] Port Nbandstructure as first skill
- [ ] Port GRASP-TWINS as second skill
- [ ] Inject skill definitions into system prompt at agent startup

### L5 tasks (Phase 2 — deferred)
- [ ] Deploy KùzuDB
- [ ] Entity extraction pipeline
- [ ] Graph-augmented retrieval
