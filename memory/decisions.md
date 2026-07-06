# Decisions Log
*Last updated: 2026-07-03*

> Architectural and design decisions with reasoning. Append new entries at the bottom.
> Related: [[memory/mistakes]] · [[HANDOFF#All design decisions — summary]]

## D1 — Hermes 3 70B AWQ as base model

**Date:** 2026-06-08
**Context:** Need local LLM for lab agent on DGX Spark (128GB unified memory).
**Decision:** Hermes 3 70B, AWQ INT8 quantization (~70GB). Serves via vLLM at 32K context.
**Reasoning:** Best open-weight model at 70B for tool calling and instruction following. AWQ fits in memory with room for embedding models.

## D2 — nomic-embed-text-v1.5 for all embeddings

**Date:** 2026-06-10
**Context:** Needed embedding model for RAG. Initially considered CodeBERT for code.
**Decision:** Single model (nomic-embed) for both prose and code. Dropped prose/code collection split.
**Reasoning:** nomic-embed handles code well enough. Simpler architecture, one model to maintain.

## D3 — Unified exclusion list via watcher.yaml

**Date:** 2026-06-30
**Context:** Three separate exclusion lists (env var, constant, watcher config) caused scan gaps.
**Decision:** `excluded.py` reads `watcher.yaml` as single source of truth. All `find` commands use `find_prune_args()`.
**Reasoning:** Missed 18 QCoDeS databases because of inconsistent exclusions.

## D4 — Replace LangGraph with Hermes Agent

**Date:** 2026-06-30
**Context:** Custom LangGraph agent works but lacks persistent memory, skills, context compression.
**Decision:** Migrate to Hermes Agent v0.17.0. Infrastructure unchanged. Only conversation loop changes.
**Reasoning:** Built-in MEMORY.md/USER.md, self-improving skills, 90+ tools, active maintenance. See [[HERMES_AGENT_COMPARISON]].

## D5 — Separate venvs for agent and Hermes

**Date:** 2026-06-30
**Context:** Hermes requires `openai>=1.30` but agent code pins an older version.
**Decision:** `/opt/qnoe-agent/hermes-venv/` separate from `/opt/qnoe-agent/venv/`.
**Reasoning:** Avoids dependency conflicts. Both can coexist during migration.

## D6 — Server ingestion uses separate manifest DB

**Date:** 2026-06-18
**Context:** Repo ingestion and server ingestion were sharing manifest DB, causing conflicts.
**Decision:** Server uses `/home/yzamir/qnoe_server_data/episodic.db`, repos use `/opt/qnoe-agent/memory/episodic.db`.
**Reasoning:** Different data directories, different ownership, different update cadences.

## D7 — Per-user profile routing via adapter-side stamping

**Date:** 2026-07-02
**Context:** Need each Teams user to get their sub-team's SOUL.md, RAG collections, and memories automatically.
**Decision:** Adapter stamps `source.profile` on `SessionSource` based on user ID mapping in `user_profiles.yaml`. Gateway's `_profile_runtime_scope` handles the rest. Do NOT use `multiplex_profiles: true`.
**Reasoning:** Single Teams bot credential (no per-profile tokens needed). Multiplexer creates duplicate handlers when sub-profiles share config. `source.profile` alone triggers profile scope correctly.

## D8 — Config inheritance via symlinks

**Date:** 2026-07-02
**Context:** Hermes profiles don't inherit config from parent. Sub-profiles need identical model/provider/plugin config.
**Decision:** Sub-profile `config.yaml` and `.env` are symlinks to the main config. Only `SOUL.md` and `memories/` differ per profile.
**Reasoning:** Single source of truth. Edit main config once, all profiles pick it up. `hermes profile create --clone` would also work but profiles already exist with custom SOUL.md.

## D9 — Provider config: custom + explicit base_url + api_key

**Date:** 2026-07-02
**Context:** vLLM local server needs no auth, but Hermes `custom` provider requires `api_key` for auth resolver.
**Decision:** Set `provider: custom`, `base_url: http://localhost:8000/v1`, `api_key: no-key-required`, `max_tokens: 4096` in config.yaml model section.
**Reasoning:** Auth resolver requires api_key to detect provider. Dummy value works for keyless vLLM. max_tokens must be capped below vLLM's 32K context.

## D10 — Per-user profile routing: adapter-side stamping with multiplex_profiles

**Date:** 2026-07-02
**Context:** Need each Teams user routed to their sub-team's profile (SOUL.md, RAG, memory) via a single Teams bot.
**Decision:** `multiplex_profiles: true` (top-level config) + adapter stamps `source.profile` from `user_profiles.yaml` mapping. Sub-profile configs have `gateway.platforms.teams_polling.enabled: false`. Two patches to gateway internals prevent duplicate adapter creation.
**Reasoning:** Single bot credential, no per-profile tokens. Profile routing happens at adapter level, gateway's `_profile_runtime_scope` handles the rest. Required patching `config.py` and `run.py` — patches will need re-applying after hermes-agent upgrades.

## D11 — tool_use_enforcement: true for Hermes 3

**Date:** 2026-07-03
**Context:** Hermes 3 70B outputs tool calls as plain text (e.g., `read_file(path="...")`) instead of structured JSON tool_calls. This makes the agent unable to use any tools (file read, RAG search, QCoDeS query). vLLM's `--tool-call-parser hermes` works perfectly with minimal context (359 tokens → structured tool call) but fails at 19.5K tokens.
**Decision:** Set `agent.tool_use_enforcement: true` in config.yaml (was `auto`).
**Reasoning:** The `auto` setting only injects tool-use guidance for GPT/Codex/Gemini/Qwen/DeepSeek/Grok — Hermes 3 is not in the list (`TOOL_USE_ENFORCEMENT_MODELS` in `prompt_builder.py:275`). Setting `true` forces the guidance for all models. This is safe — the guidance just tells the model to use tools instead of describing actions.
