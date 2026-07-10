# Changelog — QNOE Lab Agent

## 0.1.0 — "MVP-1" (2026-07-10)

First declared version: the interactive read-only lab assistant (T0/T1), verified live over Teams.
Evidence: [[SETUP_LOG]] "MVP-1 VERIFICATION + DECLARATION". Scope decisions: [[AGENT_FRAMEWORK]] §9.4.

**Stack**
- Generation: **gpt-oss-120b MXFP4 via llama.cpp** (4×64K KV slots, ~47 tok/s, native tool calls, `reasoning_effort: low`); Hermes-3-70B retained on disk as 2-minute rollback (D15)
- Orchestration: Hermes Agent gateway, per-user profile routing (orchestrator / QTM / Photocurrent), slimmed toolsets (7 resident tools)
- Retrieval: Qdrant hybrid dense+BM25 RAG (10 collections, ~1.1M points incl. SharePoint), cross-encoder rerank, content-dedup, TOP_K=5
- Memory: Mem0 per-user facts (user-messages-only writes — see M46), per-turn injection logging
- Grounding: deterministic QCoDeS registry hook (honest counts, "does not exist"), `qcodes_search` swept-parameter/path filters over both registries, SOUL grounding + attribution + memory-context guards, domain primers (QTM momentum-resolved tunneling, photocurrent)

**Deferred to 0.2+ (Phase 2):** proactive triggers (B8 failing notebooks, B9 new-paper summaries), cross-team synthesis (B10), T2-T4 write tiers, L5 knowledge graph (group-visible entities / scoped documents).

**Hard-won lessons this cycle:** memory/mistakes.md M37-M46 — including the "19.5K cliff" debunk (M40), the vLLM Marlin double-copy (M41), and Mem0 memory poisoning (M46).
