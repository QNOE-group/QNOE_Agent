# Agent Code
*Last updated: 2026-07-06*

> Agent source files, message flow, tools, and how the pieces connect.
> Full guide: [[AGENT_CODE_GUIDE]] · Framework design: [[AGENT_FRAMEWORK]] · Being replaced by: [[memory/hermes-migration]]

## File Map

| File | Role |
|---|---|
| `agent/main.py` | Entry point — dev REPL + Teams mode |
| `agent/graph.py` | LangGraph orchestrator + sub-agent nodes. Uses `chat_with_tools()` |
| `agent/state.py` | `AgentState` TypedDict |
| `agent/llm.py` | LLM client — `chat()` + `chat_with_tools()` (tool loop, max 5 rounds) |
| `agent/tools.py` | `read_file` + `list_directory` tools with path validation |
| `agent/prompts.py` | System prompts with FILE ACCESS block |
| `agent/teams.py` | Teams connector — MSAL + Graph API polling (idle 10s, active 3s) |
| `agent/retrieval.py` | Qdrant RAG + cross-encoder reranker (ms-marco-MiniLM-L-6-v2) |
| `agent/episodic.py` | SQLite episodic store |

## Message Flow

1. Teams polling picks up new message
2. Orchestrator classifies → routes to sub-agent (QTM or Photocurrent)
3. Sub-agent builds system prompt + RAG context
4. `chat_with_tools()` calls vLLM with tool schemas
5. Tool-call loop: up to 5 rounds of tool execution + re-prompting
6. Final response sent back via Teams

## Tool Definitions

- `read_file(path)` — reads file content, 50KB cap
- `list_directory(path)` — lists entries, max 200
- Allowed roots: `/ICFO/groups/NOE`, `/opt/qnoe-agent/repos`

## vLLM Model ID

Must use full path: `/opt/qnoe-agent/models/hermes-3-70b-awq`

## Embedding

- **Dense:** nomic-embed-text-v1.5 (768 dim), CPU, `@lru_cache(maxsize=1)` singleton
- **Sparse (BM25):** fastembed `Qdrant/bm25`, CPU-only, `@lru_cache(maxsize=1)` singleton. Cached in `~/.cache/fastembed/` (must be pre-downloaded — see [[memory/mistakes#M31]])
- Custom code: `.py` files must exist in model dir, `auto_map` in config.json uses local paths — see [[memory/mistakes#M3 — nomic-embed custom code in Docker]]
- **Caching:** All models use `@lru_cache(maxsize=1)` — singleton per process. Memory pressure from concurrent processes can evict tensors to swap.

## RAG Plugin (qnoe_rag)

- **File:** `/opt/qnoe-agent/hermes/plugins/qnoe_rag/__init__.py`
- **TOP_K = 3** (changed from 5 on 2026-07-03) — final chunks injected into context after reranking
- **TOP_K_PER_COLLECTION = 20** — candidates fetched per collection before reranking
- **RERANK_POOL = 20** — pool size passed to cross-encoder
- **RERANK_THRESHOLD = 0.5** — minimum score; chunks below this are dropped
- **Flow (hybrid, 2026-07-06):** embed query (dense + BM25 sparse) → hybrid Qdrant search per collection (RRF fusion of dense + sparse prefetch) → deduplicate → cross-encoder reranks top 20 → return top 3 across ALL collections combined
- **Savings from TOP_K 5→3:** ~1,200 tokens per turn

### BM25 Sparse Vectors (added 2026-07-06)

- **Why:** Dense-only retrieval fails on exact-term queries (device IDs like `SLG07-C2`, function names, paper titles). BM25 gives high weight to rare, specific tokens.
- **Library:** `fastembed` 0.8.0, model `Qdrant/bm25` (CPU-only, ~1MB, cached in `~/.cache/fastembed/`)
- **Storage:** Each Qdrant point has two vectors: unnamed dense (`""`) + named sparse (`"text-sparse"`)
- **Query:** `Prefetch(dense) + Prefetch(sparse, using="text-sparse")` → `FusionQuery(fusion=Fusion.RRF)` — all in one Qdrant call per collection
- **Schema:** All 8 collections have `text-sparse` field (added 2026-07-06 via `create_vector_name`)
- **Backfill:** `agent/indexing/backfill_sparse.py` — resumable, tracks progress in `sparse_backfill` SQLite table. Run once to populate sparse vectors for existing 638K+ points. **NOT YET RUN** as of 2026-07-06.
- **pip path:** use `pip3` not `pip` in agent venv (`/opt/qnoe-agent/venv/bin/pip3`)

## Active Toolsets & Context Budget (QTM profile, fresh session)

| Component | Tokens |
|---|---|
| Tool schemas (12 active tools) | ~6,905 |
| RAG prefetch (3 chunks) | ~3,600 |
| QTM SOUL.md | ~720 |
| Hermes framing | ~500 |
| **Floor (empty history)** | **~11,725** |

**Disabled toolsets (all profiles):** `tts`, `session_search`, `todo`, `cronjob`, `delegation`, `image_gen`

**Active tools and schema sizes:**
`terminal` 1,410 · `memory` 686 · `execute_code` 668 · `skill_manage` 1,031 · `clarify` 481 · `patch` 473 · `search_files` 438 · `process` 309 · `write_file` 279 · `read_file` 253 · `vision_analyze` 223 · `web_search` 190 · `web_extract` 170 · `skills_list` 71 · `skill_view` 223

**Note:** `process` cannot be individually disabled — shares `terminal` toolset with `terminal`.
