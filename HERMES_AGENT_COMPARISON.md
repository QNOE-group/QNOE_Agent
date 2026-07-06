# Framework Comparison: Current LangGraph Stack vs. Hermes Agent

> Claude Code memory: [[memory/hermes-migration]] · Migration plan: [[MIGRATION_PLAN]] · Decision: [[memory/decisions#D4 — Replace LangGraph with Hermes Agent]]

**Date:** 2026-06-30
**Context:** Evaluating whether to migrate the QNOE lab agent from our custom LangGraph framework to Nous Research's Hermes Agent (v0.17.0, MIT license).

---

## 1. Feature-by-Feature Comparison

| Capability | Current (LangGraph) | Hermes Agent | Notes |
|---|---|---|---|
| **Core loop** | Custom async graph: route → subagent → END | Full conversation loop with tool dispatch, streaming, retry, context compression | Hermes is far more mature (~150K lines vs ~2K) |
| **LLM backend** | vLLM only (OpenAI-compat) | Any OpenAI-compat endpoint (vLLM, Ollama, OpenRouter, Anthropic, 20+ providers). Uses `OPENAI_BASE_URL` for local models | Works with our vLLM setup out of the box |
| **Tool calling** | 3 tools (read_file, list_directory, search_files) | 90+ built-in tools (file ops, terminal, browser, memory, skills, delegation, cron, kanban, vision, code execution…) | We keep our tools as custom additions |
| **Memory** | Checkpoint DB (conversation only). No cross-session facts | MEMORY.md + USER.md (bounded, agent-managed). SQLite FTS for long-term recall. Pluggable backends (Mem0, Honcho) | **This is the main gap in our stack** |
| **Skills** | Not implemented (planned L4) | Built-in: agent creates/edits/patches Markdown skill files. Self-improving — skills are refined during use. Security scanning | **Second major gap** |
| **Multi-agent** | Orchestrator → conditional routing to sub-agent nodes. Shared state via LangGraph | Profiles (separate persona/memory/skills per agent) + `delegate_task` (isolated child agents) + Kanban (multi-agent task board with decomposition) | Similar capability, different mechanism. Hermes children are isolated; our sub-agents share state |
| **Teams integration** | Custom 343-line polling connector (Graph API + MSAL ROPC) | 1,444-line adapter using official `microsoft-teams-apps` SDK + webhook server + Adaptive Cards + meetings pipeline | Hermes Teams adapter is more complete (webhooks > polling, Adaptive Cards, typing indicators) |
| **RAG / Qdrant** | Qdrant dense search + cross-encoder reranker, 8 collections, nomic-embed | **Not built-in.** No vector store integration | We'd need to add this as a custom tool or context engine plugin |
| **QCoDeS integration** | Scanner (74K+ points), registry, run cards in Qdrant | **Not built-in** | Custom addition either way |
| **Episodic DB** | SQLite events table + audit log | SQLite session search (built-in `session_search` tool) | Similar. Hermes has richer session search |
| **Watcher daemon** | Custom CIFS watcher service, change queue, nightly indexing | Not built-in (could use cron system for periodic tasks) | Custom addition either way |
| **Conversation management** | Rolling window (60 turns / 14K tokens), auto-summarization | Built-in context compression, trajectory compressor, conversation compression | Hermes is more sophisticated |
| **Permission tiers** | T0–T4 designed (T0/T1 active). Approval flow planned | Tool approval system (auto-approve/deny/ask), write_approval for memory, security scanning for skills | Different model but covers similar ground |
| **Cron / scheduled tasks** | Nightly cron (external, via system crontab) | Built-in cron system: agent can create/manage scheduled jobs via tool | More flexible — agent manages its own schedule |
| **System prompt** | Static templates with variable substitution | 3-tier assembly (stable → context → volatile). SOUL.md identity. Context files auto-discovered. Platform hints | Much more sophisticated |
| **Deployment** | Docker container, systemd service | Docker, bare metal, CLI. Has Dockerfile and docker-compose | Similar |
| **Codebase size** | ~2,000 lines Python (agent/) | ~150K lines Python (2,694 files) | 75x larger. Much more to understand and maintain |

---

## 2. What We Keep Either Way

These are custom to our lab and don't exist in Hermes Agent:

| Component | Lines | Effort to port |
|---|---|---|
| **Qdrant RAG** (`retrieval.py`) | ~150 | Medium — wrap as Hermes tool or context engine plugin |
| **QCoDeS scanner** (`qcodes_scanner.py`) | ~300 | Low — standalone script, runs as cron |
| **Watcher daemon** (`smb_watcher.py`) | ~800 | None — independent systemd service, unchanged |
| **Nightly indexing** (`nightly_run.py`) | ~200 | Low — standalone, use Hermes cron or keep external |
| **Ingestion pipeline** (`run_ingest.py`, `splitter.py`) | ~400 | None — standalone, unchanged |
| **Repo collection mapping** (`repo_collections.yaml`) | Config | None — config file |
| **Sub-team system prompts** | ~200 | Medium — convert to Hermes Profiles with SOUL.md per sub-team |

---

## 3. What We Gain by Migrating

1. **Persistent memory** — agent remembers facts across sessions without hardcoding
2. **Self-improving skills** — agent writes reusable procedures from experience
3. **Better Teams adapter** — webhook-based (faster than polling), Adaptive Cards, typing indicators, official SDK
4. **Robust tool calling** — 90+ tools, approval system, security scanning
5. **Context compression** — battle-tested conversation management
6. **Cron from inside the agent** — no external crontab management
7. **Active community + maintenance** — Nous Research actively develops it (v0.17.0, frequent releases)
8. **Model flexibility** — easy to swap models if we upgrade hardware or want to test others

---

## 4. What We Lose or Risk

1. **LangGraph's graph structure** — our orchestrator routing is explicit and debuggable. Hermes uses delegation which is less structured
2. **Sub-agent state sharing** — LangGraph sub-agents share state; Hermes children are isolated (by design)
3. **Qdrant RAG integration** — must be re-implemented as a Hermes tool/plugin
4. **Complexity** — 150K-line framework vs 2K. More to learn, more that can break
5. **Dependency weight** — Hermes pulls many more packages (OpenAI, httpx, pydantic, prompt_toolkit, croniter, etc.)
6. **Our existing checkpoint data** — conversation history would need migration or reset

---

## 5. Migration Effort Estimate

### Phase A: Core migration (replace LangGraph with Hermes Agent)

| Task | Effort | Description |
|---|---|---|
| Install Hermes Agent in venv | 2h | `pip install hermes-agent`, configure for vLLM |
| Configure for local vLLM | 2h | Set `OPENAI_BASE_URL=http://localhost:8000/v1`, model name, context window |
| Create QTM Profile (SOUL.md) | 2h | Convert system prompt to SOUL.md + MEMORY.md for QTM sub-team |
| Create Photocurrent Profile | 1h | Same pattern as QTM |
| Create Orchestrator Profile | 2h | Convert routing logic to coordinator profile |
| Port RAG as custom tool | 4h | Wrap `retrieval.py` as a Hermes tool (tool schema + function). Register in toolsets |
| Port file tools | 2h | Adapt read_file/list_directory/search_files to Hermes tool format (or use built-in file_tools) |
| Configure Teams adapter | 4h | Set up the Teams plugin. May need webhook endpoint (requires port exposure) vs our polling approach. Evaluate if polling fallback works with the msgraph_webhook adapter |
| Test end-to-end | 4h | Verify: Teams → Hermes → vLLM → tools → response |
| Update systemd service | 1h | Change ExecStart to run Hermes instead of `python -m agent.main` |
| **Subtotal Phase A** | **~24h (3 days)** | |

### Phase B: Leverage Hermes features (memory, skills, multi-agent)

| Task | Effort | Description |
|---|---|---|
| Enable memory system | 2h | Configure MEMORY.md/USER.md paths, test persistence |
| Enable skills system | 2h | Configure skills directory, test skill creation |
| Set up multi-agent profiles | 4h | Create remaining 4 sub-team profiles (QED, Superconductivity, QSIM, XCHIRAL) |
| Configure delegation | 4h | Set up orchestrator → sub-agent delegation with appropriate toolset restrictions |
| Port QCoDeS as tool | 3h | Wrap qcodes registry query as a Hermes tool |
| Set up cron integration | 2h | Move nightly indexing to Hermes cron system |
| **Subtotal Phase B** | **~17h (2 days)** | |

### Phase C: Cleanup and validation

| Task | Effort | Description |
|---|---|---|
| Remove old LangGraph code | 2h | Clean up `graph.py`, `state.py`, old `main.py` |
| Update documentation | 3h | Update HANDOFF.md, DGX_SETUP.md, AGENT_CODE_GUIDE.md |
| Regression testing | 4h | Full test suite across Teams, file tools, RAG, memory |
| **Subtotal Phase C** | **~9h (1 day)** | |

### **Total: ~50 hours (6-7 working days)**

---

## 6. Hybrid Option: Cherry-Pick Hermes Patterns

Instead of full migration, add Hermes-style memory and skills to our LangGraph stack:

| Task | Effort |
|---|---|
| Add `memory` tool (MEMORY.md + USER.md, bounded, § delimited) | 6h |
| Add `skill_manage` tool (create/edit/delete Markdown skills) | 8h |
| Inject memory + skills into system prompt assembly | 4h |
| Add write approval flow | 4h |
| **Total** | **~22h (3 days)** |

**Pro:** Less disruption, keep working code.
**Con:** We maintain both. No Teams upgrade. No community maintenance. We'd be reimplementing what Hermes already built and tested.

---

## 7. Recommendation

**Migrate to Hermes Agent (Option 1).**

Reasons:
- Memory and skills are the #1 gap and Hermes has them battle-tested
- Teams adapter is superior (webhook + Adaptive Cards vs polling)
- Active maintenance means bugs are fixed upstream, not by us
- The model (Hermes 3 70B) was literally designed for this framework
- Our custom components (RAG, QCoDeS, watcher) are standalone and port easily
- The hybrid option saves 3 days but creates permanent maintenance debt

The migration is ~1 week of focused work. The watcher, ingestion pipeline, and Qdrant infrastructure stay untouched — only the agent conversation layer changes.

---

## 8. Key Risk: Teams Webhook vs Polling

Our current Teams connector uses **polling** (Graph API, no inbound port needed). The Hermes Teams adapter uses **webhooks** (requires an inbound HTTP endpoint reachable by Microsoft).

On the DGX (internal network, no public IP), webhooks may not work without:
- A reverse proxy / tunnel (ngrok, Cloudflare Tunnel)
- Azure Bot Framework relay

**Mitigation:** Keep our polling connector as a Hermes platform plugin, using their plugin system. The `ADDING_A_PLATFORM.md` guide shows exactly how. This is ~4h of work and avoids the webhook problem entirely.

---

## 9. Decision Needed

- [ ] **Option 1:** Full migration to Hermes Agent (~50h / 1 week)
- [ ] **Option 2:** Cherry-pick memory + skills into LangGraph (~22h / 3 days)
- [ ] **Option 3:** Stay as-is, hardcode knowledge in prompts (0h, accumulates debt)
