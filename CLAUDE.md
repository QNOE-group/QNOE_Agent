# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Obsidian Memory System

**This project has a persistent Obsidian-based memory system.** `HOME.md` is the master index linking to all topic-specific memory files in `memory/`. It is automatically loaded at session start via a `SessionStart` hook.

**Rules:**
- **Search memory first.** When looking for project knowledge (infrastructure, agent code, ingestion, decisions, pitfalls, deploy patterns, migration state), check the relevant `memory/*.md` file BEFORE traversing documentation or grepping the codebase. The memory files are curated summaries — faster and more reliable than re-reading raw docs.
- **Document as you go.** When you fix a bug, add it to `memory/mistakes.md`. When you make an architectural decision, add it to `memory/decisions.md`. When you learn something new about infrastructure, update `memory/infrastructure.md`. Keep the memory system current — it is your primary knowledge base across sessions.
- **Use wikilinks.** All files use Obsidian `[[wikilink]]` syntax. Follow links to navigate. When adding new knowledge, link back to related files.
- **Update dates.** When modifying a memory file, update its `*Last updated:*` line.

**Memory files:**

| File | Contents |
|---|---|
| `HOME.md` | Master index — start here every session |
| `memory/infrastructure.md` | DGX, vLLM, Qdrant, Docker, systemd, CIFS, cron |
| `memory/agent-code.md` | Agent files, message flow, tools, LLM client |
| `memory/ingestion.md` | RAG pipeline, scanners, watcher daemon, nightly jobs |
| `memory/decisions.md` | Architectural decisions log |
| `memory/mistakes.md` | Bugs fixed, pitfalls, hard-won technical fixes |
| `memory/hermes-migration.md` | Migration from LangGraph to Hermes Agent |
| `memory/deploy-patterns.md` | DGX file ownership, deployment procedures |
| `memory/user-preferences.md` | How the user works, communication style |

---

## What this project is

A fully local, proactive AI agent system for the QNOE group (ICFO Barcelona, PI: Frank Koppens). The agent runs on a NVIDIA DGX Spark on-premises and acts as a virtual lab student — answering questions about group code and papers, monitoring repos, and making code changes with human approval. **No data leaves the lab network.**

**Status: Phase 1 in progress.** Infrastructure complete (Phase 0). Agent code being written. Entry point: `/opt/qnoe-agent/venv/bin/python -m agent.main` per DGX_SETUP.md §12.

---

## File map

| File | Role |
|---|---|
| `HANDOFF.md` | **Start here** — single-page summary of all decisions, context window budget, and milestone plan |
| `lab_agent_brief.md` | Full project brief — group context, hardware, permission tiers (T0–T4), sub-agent structure |
| `AGENT_FRAMEWORK.md` | LangGraph design: `AgentState` schema, Teams threading, proactive triggers, system prompts (G8), MVP scope (G9), onboarding (G10), failure/recovery (G11) |
| `INFERENCE_MEMORY.md` | Memory layers L1–L5, Mem0 config, turn loop integration, full context window budget |
| `DGX_SETUP.md` | Step-by-step DGX setup: vLLM, models, Qdrant, SQLite, network mounts, shell environment, systemd, cron |
| `MEMORY_ALTERNATIVES.md` | Evaluated alternatives (Zep, Mem0, Cognee, LangMem) with recommendation |
| `TODO.md` | Master task list — all design gaps are resolved; implementation tasks tracked here |
| `PHASE2_BACKLOG.md` | Backlog of features planned after MVP: B1 BM25 hybrid search, B2 overnight measurement analysis, B3 QCoDeS data access skill, B4 frontier model access |
| `AGENT_CODE_GUIDE.md` | How the agent code works — message flow diagram, file roles, routing logic, what's missing |

---

## Architecture

```
┌──────────────────────────────────────────┐
│  Hermes 3 70B (INT8 AWQ) via vLLM        │  localhost:8000, 32K context
├──────────────────────────────────────────┤
│  LangGraph — orchestrator + 6 sub-agents │  SqliteSaver checkpointer
├──────────────────────────────────────────┤
│  Open shell — universal execution layer  │  all permissions enforced here
├──────────────────────────────────────────┤
│  Memory: Qdrant (15 collections) +       │
│           Mem0 + SQLite episodic         │
├──────────────────────────────────────────┤
│  Lab data server · QNOE GitHub · Teams   │
└──────────────────────────────────────────┘
```

**One Teams bot** routes messages to one of six sub-agents (QED, Superconductivity, Photocurrent, QTM, QSIM, XCHIRAL) via the orchestrator (QNOE-Agent). Sub-agents share one vLLM endpoint; persona and scope are controlled by system prompts.

---

## Key design decisions (all resolved)

**Inference:** Hermes 3 70B, AWQ INT8, ~70 GB on 128 GB unified DGX memory. vLLM at `localhost:8000`.

**Memory layers (build in order):**
- **L1** — Qdrant dense RAG: 7 collections (one per sub-team + group-wide), all embedded with nomic-embed-text-v1.5
- **L2** — BM25 sparse vectors added to Qdrant (exact-term matching)
- **L3** — SQLite: episodic events table + audit log
- **L3.5** — Mem0: per-user distilled facts in an 8th Qdrant collection (`episodic_memory`)
- **L4** — Skill registry: versioned Python tools in `/opt/qnoe-agent/skills/`
- **L5** — KùzuDB knowledge graph (Phase 2, deferred)

**Context window budget (32K):** system prompt 1,500 + rolling window 15,000 + summary 800 + Mem0 facts 700 + task history 500 + RAG chunks 2,500 + current message 500 + tool outputs 2,000 = 23,500 tokens input (72% of 32K).

**Permission tiers:**
- T0/T1 — read, analyse, draft — fully autonomous
- T2 — write own repo — single Teams confirmation from repo owner
- T3 — write shared resources — named approver from designated list
- T4 — destructive — 4-layer stack: scope lock → dry-run manifest → typed confirmation → 5-minute snapshot window with soft-delete only (`safe_delete()`, never `rm`)

**Execution model:** Continuous loop for perception, event-driven gates before any write action, scheduled sweeps (nightly 02:00) for re-indexing.

**Session persistence:** LangGraph `SqliteSaver` checkpointer keyed to Teams `conversation_id` (DM) or `thread_id` (channel). Rolling window: 60 turns / 14,000 tokens → auto-summarisation to ≤800 tokens.

---

## MVP scope (Phase 1)

Orchestrator + QTM-Agent + Photocurrent-Agent only, T0/T1 (read-only). See `AGENT_FRAMEWORK.md §9` for the 10 acceptance criteria. Phase 2 adds T2–T4 write access for those two agents before expanding to all six.

---

## Infrastructure paths (DGX)

| Resource | Path |
|---|---|
| Agent venv | `/opt/qnoe-agent/venv/` |
| Models | `/opt/qnoe-agent/models/` |
| Config | `/opt/qnoe-agent/config/triggers.yaml`, `config/maintainer.yaml` |
| Sandbox policy | `/opt/qnoe-agent/config/sandbox-policy.yaml` |
| Agent Dockerfile | `/opt/qnoe-agent/Dockerfile` |
| Secrets | `/opt/qnoe-agent/secrets/github_pat` (chmod 600) |
| Memory DB | `/opt/qnoe-agent/memory/checkpoints.db`, `memory/episodic.db` |
| Qdrant data | `/opt/qnoe-agent/qdrant_data/` |
| Skill registry | `/opt/qnoe-agent/skills/<skill_name>/v<N>/skill.py` |
| Lab data mount | `/ICFO/groups/NOE` (pre-mounted on host; bind-mounted into sandbox) |
| Soft-delete trash | `/ICFO/groups/NOE/.agent_trash/` |
| Logs | `/opt/qnoe-agent/logs/` (startup, audit via `openshell logs`) |

---

## DGX access

Claude CAN SSH into the DGX directly via the Bash tool:
```
ssh -i "/c/Users/yzamir/.ssh/id_ed25519_dgx" -o StrictHostKeyChecking=no yzamir@10.3.8.21 "command"
```

**Per-session rule:** Ask the user once at the start of each new session before using SSH. Once approved for a session, use it freely within that session without asking again. Never ask mid-task.

**sudo limitation:** Commands requiring `sudo` cannot be run non-interactively via SSH. Give those to the user to run manually and ask them to paste back the output.

---

## Open items (not yet in any file)

- XCHIRAL repo list not yet populated in sub-agent config
- `/new` command injection not yet added to system prompt templates
- Commit trigger batching rule (avoid alert storms on bulk pushes) not yet in `triggers.yaml`
- PPTX Gantt reflects old phase order — update before next PI presentation
