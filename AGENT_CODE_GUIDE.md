# Agent Code Guide
*How the Hermes Agent system works — architecture, plugins, routing, and profile management*

> Claude Code memory: [[memory/hermes-migration]] · Mistakes: [[memory/mistakes]] · Decisions: [[memory/decisions]]

---

## Message flow — end to end

```
Teams (user sends "What instruments are in the QTM lab?")
  │
  ▼
teams_polling adapter — TeamsPollingAdapter
  polls Graph API every 3–30s
  detects new message
  _resolve_profile(sender_id, display_name) → "qnoe-qtm"
  creates SessionSource(profile="qnoe-qtm", ...)
  creates MessageEvent(text=..., source=...)
  calls handle_message(event)
  │
  ▼
Hermes Gateway
  reads source.profile → "qnoe-qtm"
  enters _profile_runtime_scope("profiles/qnoe-qtm/")
  loads qnoe-qtm/SOUL.md as system prompt
  loads qnoe-qtm/memories/MEMORY.md
  │
  ▼
qnoe_rag plugin — memory provider
  initialize(agent_identity="qnoe-qtm")
  PROFILE_COLLECTIONS["qnoe-qtm"] → ["qtm", "group-wide", "qcodes-runs"]
  prefetch: embed query → nomic-embed (CPU) → Qdrant top-20
           → cross-encoder rerank → top-5 chunks injected as context
  │
  ▼
vLLM inference (localhost:8000/v1)
  system prompt (SOUL.md) + RAG context + conversation history + user message
  → Hermes 3 70B generates response
  │
  ▼
Gateway sends response back via adapter
  adapter calls Graph API to post reply in Teams chat
```

---

## Plugin architecture

All custom plugins live in `/opt/qnoe-agent/hermes/plugins/`. Each profile discovers them via a `plugins/` symlink pointing to this directory.

| Plugin | Type | What it does |
|---|---|---|
| `teams_polling/` | Platform adapter | Polls Microsoft Graph API for Teams messages. MSAL ROPC auth. Per-user profile routing via `user_profiles.yaml`. `bot_token` attribute for credential dedup. |
| `qnoe_rag/` | Memory provider (exclusive) | RAG retrieval: nomic-embed-text-v1.5 → Qdrant dense search → ms-marco cross-encoder reranking. Per-profile collection routing. Provides `rag_search` tool + automatic prefetch. |
| `qnoe_qcodes/` | Standalone tool | Queries QCoDeS experiment registry (75K runs in SQLite). Sample search, date range, free-text. |

### Plugin discovery

Hermes scans `get_hermes_home() / "plugins"` at startup. At runtime, `HERMES_HOME` points to the active **profile** directory (e.g., `profiles/qnoe-orchestrator/`), NOT the hermes root. Each profile needs a `plugins/` symlink:

```
profiles/qnoe-orchestrator/plugins → ../../plugins
profiles/qnoe-qtm/plugins → ../../plugins
profiles/qnoe-photocurrent/plugins → ../../plugins
```

Discovery runs once and is cached — not re-run under `_profile_runtime_scope`.

---

## Per-user profile routing

### How it works

1. `multiplex_profiles: true` at top level of `config.yaml`
2. Adapter loads `config/user_profiles.yaml` mapping (user ID → profile name)
3. For each incoming message, `_resolve_profile()` looks up sender by Azure AD ID, then by display name
4. `source.profile` is set on `SessionSource` → gateway routes to that profile
5. `self.bot_token = self._username` exposes a stable credential for `_adapter_credential_fingerprint()` — prevents the multiplexer from creating duplicate adapters

### Profile structure

```
hermes/
├── config.yaml              # Main config (shared via symlinks or standalone copies)
├── config/
│   └── user_profiles.yaml   # User ID → profile mapping
├── plugins/                  # All custom plugins (shared)
│   ├── teams_polling/
│   ├── qnoe_rag/
│   └── qnoe_qcodes/
└── profiles/
    ├── qnoe-orchestrator/    # Default profile (unmapped users)
    │   ├── SOUL.md
    │   ├── memories/MEMORY.md
    │   ├── config.yaml       # Standalone config
    │   ├── .env              # Symlink → ../../.env
    │   └── plugins           # Symlink → ../../plugins
    ├── qnoe-qtm/
    │   ├── SOUL.md           # QTM-specific personality
    │   ├── memories/MEMORY.md
    │   ├── config.yaml       # teams_polling.enabled: false
    │   ├── .env
    │   └── plugins           # Symlink → ../../plugins
    └── qnoe-photocurrent/
        ├── SOUL.md
        ├── memories/MEMORY.md
        ├── config.yaml
        ├── .env
        └── plugins           # Symlink → ../../plugins
```

### RAG collection routing

The `qnoe_rag` plugin routes queries to profile-specific collections:

| Profile | Collections searched |
|---|---|
| `qnoe-orchestrator` | All 15 collections |
| `qnoe-qtm` | `qtm`, `group-wide`, `qcodes-runs` |
| `qnoe-photocurrent` | `photocurrent`, `group-wide`, `qcodes-runs` |

### user_profiles.yaml format

```yaml
default: qnoe-orchestrator    # Unmapped users get this profile
users:
  "ef6f38c9-...": qnoe-qtm   # Azure AD user ID → profile
users_by_name:
  "Jane Doe": qnoe-qtm       # Fallback: match by Teams display name
```

---

## Configuration

### Key config.yaml settings

```yaml
model:
  default: /opt/qnoe-agent/models/hermes-3-70b-awq
  provider: custom
  base_url: http://localhost:8000/v1
  api_key: no-key-required      # Dummy — vLLM has no auth
  max_tokens: 4096              # Must cap below vLLM's 32K context
multiplex_profiles: true        # MUST be top-level (not under gateway:)
memory:
  provider: qnoe_rag           # Exclusive memory provider
```

### Sub-profile config

Each sub-profile has its own `config.yaml` (NOT symlinked) with:
- `gateway.platforms.teams_polling.enabled: false` — prevents duplicate adapters
- `memory.provider: qnoe_rag` — enables RAG for that profile

---

## Services

| Service | What | Status |
|---|---|---|
| `qnoe-hermes.service` | Hermes gateway (agent + Teams) | ACTIVE |
| `vllm.service` | vLLM model server | ACTIVE |
| `qdrant.service` | Qdrant vector DB | ACTIVE (Docker) |
| `qnoe-watcher.service` | SMB3 file change watcher | ACTIVE |
| `qnoe-agent.service` | Old LangGraph agent | DISABLED |

---

## The ingest module — only for building the RAG database

`agent/ingest/` is a **batch job**, completely separate from the live agent. It runs offline to populate Qdrant:

```
python -m agent.ingest.run_ingest --team qtm --repo-path /path/to/QTM_CodeBase
```

The live agent only **reads** from Qdrant via the `qnoe_rag` plugin. Nightly cron re-indexes at 02:00.

---

## Key gotchas

See [[memory/mistakes]] for the full list. Critical ones:

- **Two copies of teams_polling** — source (`hermes/plugins/`) and runtime (`hermes-venv/.../site-packages/`). Source (via symlink) takes precedence. Keep both in sync.
- **`HERMES_HOME` is the profile dir** — not the hermes root. Use `split("/profiles/")` to get root.
- **`_profile_runtime_scope` isolates secrets** — sub-profiles need own `.env` or config-level credentials.
- **Plugin auto-enable** — `gateway/config.py` overrides `enabled: false` if env vars are present. Handled by `bot_token` credential dedup, not by patching gateway.
- **Tool calling as text** — Hermes 3 70B sometimes outputs tool calls as plain text. Known issue, under investigation.
