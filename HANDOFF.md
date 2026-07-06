# QNOE Lab Agent — Project Handoff
*Last updated: 2026-07-03 — Hermes Agent migration complete (M1–M7.5), per-user profile routing live*

> Claude Code memory: [[HOME]] · Mistakes & pitfalls: [[memory/mistakes]] · Decisions: [[memory/decisions]]

This document is the single entry point for resuming this project in a
new conversation. Read this first, then open the specific file you need.

---

## What this project is

A fully local, proactive AI agent system for the QNOE group (ICFO Barcelona,
PI: Frank Koppens). It runs on a NVIDIA DGX Spark on-premises and acts as a
virtual lab student — answering questions, monitoring repos, summarising
papers, and eventually making code changes with human approval.

**The agent never sends data outside the lab network.**

---

## File map

| File | Contents |
|---|---|
| `lab_agent_brief.md` | Full project brief — group context, hardware, decisions, permission tiers, sub-agent architecture |
| `TODO.md` | Master task list, all design gaps resolved, milestone plan |
| `DGX_SETUP.md` | Complete step-by-step DGX setup: OS, vLLM, models, Qdrant, SQLite, network mounts, shell environment, cron jobs |
| `AGENT_FRAMEWORK.md` | LangGraph design: AgentState schema, persistence, Teams threading, proactive triggers, system prompts, MVP scope, onboarding, failure/recovery |
| `INFERENCE_MEMORY.md` | Full memory system (L1–L5), Mem0 config, turn loop integration, context window budget |
| `QNOE_Agent_Architecture.pptx` | 7-slide PI presentation |
| `PHASE2_BACKLOG.md` | Post-MVP feature backlog: B1 BM25, B2 overnight analysis, B3 QCoDeS data access skill, B4 frontier model access |
| `WATCHER_PLAN.md` | SMB3 file watcher daemon plan — replaces nightly `find`-based CIFS scans with continuous change detection + queue-based processing. **Deployed.** |
| `HERMES_AGENT_COMPARISON.md` | Feature comparison: LangGraph vs Hermes Agent, migration effort estimate |
| `MIGRATION_PLAN.md` | Migration plan from LangGraph to Hermes Agent v0.17.0. M1–M7.5 complete. M8 (cleanup) remaining. |
| `HOME.md` | Claude Code memory index — links to topic-specific memory files in `memory/` |

---

## Architecture in one paragraph

**Current (Hermes Agent v0.17.0):** A single Teams bot connects via a custom `teams_polling` adapter plugin. Each user is automatically routed to their sub-team's Hermes profile (QTM, Photocurrent, etc.) based on a user-ID mapping in `user_profiles.yaml`. Each profile has its own SOUL.md, MEMORY.md, and RAG collection scope. All profiles share one Hermes 3 70B model (INT8 AWQ, 32K context) served locally by vLLM. Knowledge lives in Qdrant RAG (15 collections) with nomic-embed + cross-encoder reranking. The agent runs natively (no Docker) as `qnoe-hermes.service`. Infrastructure: vLLM, Qdrant, SMB3 file watcher, nightly indexing cron — all on the DGX Spark.

**Previous (LangGraph — archived):** The original agent used a custom LangGraph orchestrator with SqliteSaver checkpointer. Replaced by Hermes Agent for persistent memory, self-improving skills, 90+ built-in tools, and context compression. Old code in `/opt/qnoe-agent/agent/`, service `qnoe-agent.service` disabled.

---

## Memory system — what each layer answers

| Layer | Store | Question answered |
|---|---|---|
| L1/L2 | Qdrant RAG | What does the group know about this topic? |
| L1 | Qdrant `qcodes-runs` | What measurements exist for this device/sample? |
| L3.5 | Mem0 → Qdrant `episodic_memory` | Who is this user and what do I know about them? |
| L3 | SQLite episodic | What has the agent done with this user before? |
| Checkpointer | SQLite | What happened in this conversation so far? |

All three feed into `episodic_context` + `rag_chunks` in `AgentState`
before Hermes sees the assembled context each turn.

---

## Context assembly per turn

```
SQLite checkpointer     → rolling window + conversation summary   (session state)
Mem0 search             → distilled user facts                    (episodic_context)
SQLite events query     → recent task history                     (episodic_context)
Qdrant RAG              → relevant documents, code, papers        (rag_chunks)
         ↓
    assembled context window (~23,500 tokens)
         ↓
         Hermes
```

---

## All design decisions — summary

### Hardware & model
- **DGX Spark**: GB10 Grace Blackwell, 128 GB unified memory, 4 TB NVMe
- **Model**: Hermes 3 70B, INT8 AWQ (~70 GB), served by vLLM at `localhost:8000`
- **Context window**: `max_model_len=32768`
- **Embedding model**: nomic-embed-text-v1.5 (all content — prose and code)

### Memory system
- **L1**: Qdrant dense vectors — 7 RAG collections (one per sub-team + group-wide)
- **L2**: BM25 sparse vectors — exact-term matching upgrade to L1
- **L3**: SQLite episodic — events, task outcomes, audit log
- **L3.5**: Mem0 — per-user distilled facts, stored in `episodic_memory` Qdrant collection
- **L4**: Skill registry — versioned Python tools
- **L5**: KùzuDB knowledge graph — Phase 2, deferred

### Retrieval pipeline (per turn)
1. Mem0 search by `user_id` → user facts into `episodic_context`
2. SQLite query → task history into `episodic_context`
3. Embed query (prose + code) → Qdrant RAG top-20
4. Metadata filter if available
5. Cross-encoder rerank → top-5
6. Anti-lost-in-middle ordering → inject into `rag_chunks`

### Context window budget (32K)
| Slot | Tokens |
|---|---|
| System prompt + skills | 1,500 |
| Rolling window | 15,000 |
| Conversation summary | 800 |
| Episodic — Mem0 user facts | 700 |
| Episodic — task history | 500 |
| RAG chunks (top 5) | 2,500 |
| Current message | 500 |
| Tool outputs | 2,000 |
| **Total** | **23,500** (72% of 32K) |

### Agent architecture
- One Teams bot (service account `qnoe-ai@icfo.net`), per-user profile routing via `user_profiles.yaml`
- Hermes Agent v0.17.0 gateway with profiles: orchestrator + sub-team profiles (QTM, Photocurrent)
- Agent runs natively as `qnoe-hermes.service` (User=qnoe-ai, Restart=on-failure)
- Hermes built-in session persistence, context compression, MEMORY.md per profile
- Inference: direct to vLLM at `localhost:8000/v1` (provider: custom)
- Teams integration: `teams_polling` adapter plugin, Graph API polling (3s active / 30s idle)
- RAG: `qnoe_rag` memory provider plugin (Qdrant + nomic-embed + cross-encoder reranking)
- QCoDeS: `qnoe_qcodes` standalone plugin (75K runs, SQLite registry)

### Permission tiers
| Tier | Action | Approval |
|---|---|---|
| T0 | Read, analyse | Autonomous |
| T1 | Draft, suggest | Autonomous |
| T2 | Write own repo | User confirms in Teams |
| T3 | Write shared resources | Designated approvers |
| T4 | Destructive | 4-layer safety stack |

### Milestone plan
| Phase | Deliverable | Status |
|---|---|---|
| 0 | DGX configured, Hermes 3 70B serving | DONE |
| 1 | MVP: Orchestrator + QTM + Photocurrent, T0/T1 (LangGraph) | DONE |
| M1-M7.5 | Migrate to Hermes Agent v0.17.0 + per-user profile routing | DONE |
| M8 | Cleanup & documentation | IN PROGRESS |
| 2 | Write access T2-T4 | Planned |
| 3 | All 6 sub-agents | Planned |
| 4 | BM25 hybrid search | Planned |
| 5 | Knowledge graph | Planned |

---

## Small open items (not yet in files)

- XCHIRAL repo list not yet populated in sub-agent config
- Gantt in PPTX reflects old phase order — update before presenting
- Commit trigger batching rule (avoid alert storms on bulk commits) not yet in triggers.yaml spec
- **Tool calling as text** — Hermes 3 70B sometimes outputs tool calls as plain text instead of structured JSON. Investigate system prompt guidance or `tool_use_enforcement` setting.
- M8 cleanup remaining: archive old LangGraph code, update AGENT_CODE_GUIDE.md for Hermes architecture
