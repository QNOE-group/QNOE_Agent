# Agent Code
*Last updated: 2026-07-03*

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

- Model: nomic-embed-text-v1.5 (768 dim)
- Device: CPU (GPU occupied by vLLM)
- Custom code: `.py` files must exist in model dir, `auto_map` in config.json uses local paths — see [[memory/mistakes#M3 — nomic-embed custom code in Docker]]
- **Caching:** `_load_embed_model()` and `_load_reranker()` use `@lru_cache(maxsize=1)` — singleton per process. Models reload only after service restart. Memory pressure from concurrent processes (e.g. SharePoint digest) can evict tensors to swap, making it appear to reload.

## RAG Plugin (qnoe_rag)

- **File:** `/opt/qnoe-agent/hermes/plugins/qnoe_rag/__init__.py`
- **TOP_K = 3** (changed from 5 on 2026-07-03) — final chunks injected into context after reranking
- **TOP_K_PER_COLLECTION = 20** — candidates fetched per collection before reranking
- **RERANK_POOL = 20** — pool size passed to cross-encoder
- **RERANK_THRESHOLD = 0.5** — minimum score; chunks below this are dropped
- **Flow:** embed query → search each collection (up to 20 candidates each) → deduplicate → cross-encoder reranks top 20 → return top 3 across ALL collections combined
- **Savings from TOP_K 5→3:** ~1,200 tokens per turn

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
