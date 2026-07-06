![[benchmark_scores]]# DGX Setup
*Last updated: 2026-07-03*

> Claude Code memory: [[memory/infrastructure]] · Deploy patterns: [[memory/deploy-patterns]] · Mistakes: [[memory/mistakes]]

---

## Overview

The DGX Spark is the sole compute node. Everything — inference, agent logic, vector DB, episodic store, skill registry — runs on this machine. Nothing leaves the lab network. This file tracks every concrete step to get the hardware from bare metal to a fully operational inference + storage platform ready for the agent framework.

---

## Hardware spec (reference)

| Component | Spec |
|---|---|
| GPU | NVIDIA GB10 Grace Blackwell Superchip |
| Unified memory | 128 GB LPDDR5x (CPU + GPU shared) |
| Storage | 4 TB NVMe |
| OS | Ubuntu 22.04 LTS (expected) |
| Network | 10 GbE (lab network) |

---

## Task list

### 1. Hardware + OS readiness

- [ ] Confirm OS version: `cat /etc/os-release`
- [ ] Confirm NVIDIA driver version: `nvidia-smi` — target ≥ 570
- [ ] Confirm CUDA version: `nvcc --version` — target ≥ 12.4
- [ ] Check NVMe free space: `df -h` — need ≥ 2 TB free for models + data
- [ ] Confirm Python version: `python3 --version` — target 3.11+
- [ ] Verify lab network connectivity (ping data server, ping GitHub)
- [ ] Create dedicated agent OS user account: `sudo useradd -m qnoe-ai` *(IT created `qnoe-ai` on 2026-06-09)*
- [ ] Assign account to appropriate Unix groups (data server mounts, docker if used)

---

### 2. Python environment

- [ ] Install `uv` for fast env management: `curl -Lsf https://astral.sh/uv/install.sh | sh`
- [ ] Create agent venv: `uv venv /opt/qnoe-agent/venv --python 3.11`
- [ ] Add venv activation to agent account `.bashrc`

---

### 3. vLLM installation

- [ ] Install vLLM (Grace Blackwell build):
  ```bash
  uv pip install vllm
  # or NVIDIA's pre-built wheel if available for GB10:
  # pip install https://github.com/vllm-project/vllm/releases/...
  ```
- [ ] Validate GPU is visible to vLLM:
  ```bash
  python -c "from vllm import LLM; print('ok')"
  ```
- [ ] Confirm unified memory is addressable (GB10-specific — check vLLM docs for `--device` flag)

---

### 4. Model: Hermes 3 70B

- [ ] Install Hugging Face CLI: `uv pip install huggingface_hub`
- [ ] Authenticate: `huggingface-cli login`
- [ ] Download model weights (INT8 AWQ quantized, ~70 GB):
  ```bash
  huggingface-cli download \
    NousResearch/Hermes-3-Llama-3.1-70B-AWQ \
    --local-dir /opt/qnoe-agent/models/hermes-3-70b-awq
  ```
  > **Note:** If the AWQ variant underperforms on reasoning tasks during benchmarking (step 5), pull the BF16 version and use `--cpu-offload` in vLLM.
- [ ] Launch vLLM server:
  ```bash
  vllm serve /opt/qnoe-agent/models/hermes-3-70b-awq \
    --host 127.0.0.1 \
    --port 8000 \
    --quantization awq \
    --max-model-len 32768
  ```
  > **Note:** 32K context requires ~10 GB KV cache. Total memory (weights + KV + embeddings) ≈ 81 GB — within the 128 GB envelope. If memory pressure appears at runtime, reduce to 16384 first.
- [ ] Verify OpenAI-compatible endpoint responds:
  ```bash
  curl http://127.0.0.1:8000/v1/models
  ```

---

### 5. Inference benchmark

Run before committing to this model + quantization combo. Use representative QNOE tasks.

- [ ] **Task set (design these prompts):**
  - Python code review: give it a QCoDeS data loading script with 3 introduced bugs
  - Data analysis reasoning: describe a measurement dataset, ask for analysis plan
  - Literature question: ask a QED/polariton physics question answerable from a paper
  - Multi-step plan: ask it to outline how to add a new analysis notebook to a repo
  - Tool call: ask it to call a mock function with the right JSON arguments
- [ ] Run each task 3× and score manually (1–5): correctness, reasoning quality, hallucination rate
- [ ] Record time-to-first-token and total latency per task
- [ ] **Decision gate:** if mean score < 3.5 → evaluate BF16 with cpu-offload OR Hermes 3 8B for sub-agents

---

### 6. Embedding model

Needed for Qdrant RAG (separate from the main LLM).

- [ ] Download a lightweight embedding model (suggested: `nomic-ai/nomic-embed-text-v1.5`, 137M params):
  ```bash
  huggingface-cli download nomic-ai/nomic-embed-text-v1.5 \
    --local-dir /opt/qnoe-agent/models/nomic-embed
  ```
- [ ] Serve via a simple FastAPI wrapper or use `sentence-transformers` directly in the agent process
- [ ] Benchmark embedding throughput on a 500-doc corpus (target: < 60 s)

---

### 7. Qdrant deployment

- [ ] Install Qdrant (Docker recommended):
  ```bash
  docker run -d --name qdrant \
    -p 6333:6333 \
    -v /opt/qnoe-agent/qdrant_data:/qdrant/storage \
    qdrant/qdrant
  ```
  > If Docker is not available: `pip install qdrant-client` + use in-process mode for dev, then migrate to server mode for production.
- [ ] Verify Qdrant is up: `curl http://localhost:6333/collections`
- [ ] Create collections (one per memory scope):
  ```
  group-wide
  qed
  superconductivity
  photocurrent
  qtm
  qsim
  xchiral
  ```
  Each with `vectors: { size: 768, distance: Cosine }` (matches nomic-embed-v1.5 output dim)

---

### 8. SQLite episodic store

No installation needed — stdlib. Define schema here for reference.

- [ ] Create database file at `/opt/qnoe-agent/memory/episodic.db`
- [ ] Schema:
  ```sql
  CREATE TABLE events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   TEXT NOT NULL,
    agent       TEXT NOT NULL,       -- orchestrator | qed | supercon | ...
    user        TEXT,                -- Teams user ID, nullable for autonomous events
    event_type  TEXT NOT NULL,       -- message | task_start | task_end | action | approval
    content     TEXT NOT NULL,       -- JSON payload
    tier        INTEGER,             -- T0-T4 for actions
    outcome     TEXT                 -- success | cancelled | failed | pending
  );

  CREATE TABLE audit_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp       TEXT NOT NULL,
    operation_id    TEXT NOT NULL,
    requesting_user TEXT NOT NULL,
    approving_user  TEXT,
    action_type     TEXT NOT NULL,
    scope           TEXT NOT NULL,   -- JSON describing affected resources
    outcome         TEXT NOT NULL,
    snapshot_path   TEXT             -- nullable; path to .agent_trash snapshot
  );
  ```
- [ ] Write and test a minimal Python `EpisodicStore` class with `log_event()` and `query_recent()` methods

---

### 9. Network mounts

**SSH access (from Windows workstation):**
```bash
ssh -i "/c/Users/yzamir/.ssh/id_ed25519_dgx" -o StrictHostKeyChecking=no yzamir@10.3.8.21 "command"
```

**CIFS mount (lab data server → DGX):**
```bash
sudo mount -t cifs "//files/groups/NOE" /ICFO/groups/NOE -o username=yzamir,domain=ICFONET
```
> The mount does not persist across reboots — re-run after each restart (or add to `/etc/fstab`).

- [x] Identify data server mount point and protocol with IT — CIFS, `//files/groups/NOE`
- [x] Mount data server under `/ICFO/groups/NOE` (read + write for agent account)
- [ ] Mount literature store under `/mnt/qnoe-literature` (read-only for agent account)
- [ ] Add mount to `/etc/fstab` for persistence across reboots
- [ ] Verify agent account can read a test QCoDeS `.db` file from `/ICFO/groups/NOE`
- [ ] Create `.agent_trash/` directory on data server (for soft-delete architecture): `mkdir /ICFO/groups/NOE/.agent_trash`
- [ ] Confirm agent account can write to `.agent_trash/`

---

### 10. GitHub agent account

- [ ] Create GitHub account: `qnoe-agent` (or similar)
- [ ] PI invites `qnoe-agent` to the QNOE-group GitHub org
- [ ] Configure permissions per tier system (see `AGENT_FRAMEWORK.md §permissions`)
- [ ] Generate a fine-grained Personal Access Token (PAT) with:
  - Contents: read + write
  - Pull requests: read + write
  - Issues: read + write
  - Metadata: read
- [ ] Store PAT in `/opt/qnoe-agent/secrets/github_pat` with `chmod 600`
- [ ] Configure git on DGX: `git config --global user.name "QNOE Agent"`, set email

---

### 11. OpenShell sandbox environment

**Decision (2026-06-09):** Manual PATH whitelist, bash command blocking, and shell audit hook are superseded by NVIDIA OpenShell — a policy-governed container with kernel-level (Landlock + seccomp) enforcement. See `OPENSHELL_DESIGN_PROPOSAL.md` for full rationale and policy design.

The agent runs inside an OpenShell sandbox (Docker container). The `qnoe-ai` account owns and manages the gateway and sandbox. All security enforcement is declarative YAML — not shell scripts.

- [x] Add `yzamir` and `qnoe-ai` to docker group ✅ *(2026-06-09)*
- [x] Configure NVIDIA container runtime ✅ *(2026-06-09)*: `sudo nvidia-ctk runtime configure --runtime=docker`
- [ ] Install OpenShell as `qnoe-ai`: `sudo -u qnoe-ai uv tool install -U openshell`
- [ ] Start gateway: `sudo -u qnoe-ai openshell gateway start` → verify with `openshell status`
- [ ] Register vLLM inference provider (see §11.1)
- [ ] Write `/opt/qnoe-agent/Dockerfile` (see §11.2)
- [ ] Write `/opt/qnoe-agent/config/sandbox-policy.yaml` (see §11.3)
- [ ] Confirm Docker bridge IP: `ip addr show docker0 | grep inet` — update Qdrant policy entry
- [ ] Test sandbox launch and verify deny-all network default
- [ ] Implement `safe_delete()` Python wrapper in agent code — OpenShell filesystem policy is a second enforcement layer, not a replacement for the soft-delete semantics

#### 11.0 Gateway restart procedure

The gateway requires TLS with a key pair that includes `127.0.0.1`, `172.18.0.1` (Docker bridge), **and `host.openshell.internal`** as SANs. The supervisor inside the container connects to `https://host.openshell.internal:17670/` and performs strict hostname verification — the cert must include that DNS SAN or TLS fails with `BadCertificate`.

Use this script whenever the gateway needs to be restarted or reconfigured:

```bash
# Script lives at ~/restart_gateway.sh
sudo bash ~/restart_gateway.sh
```

Script contents (`~/restart_gateway.sh`):
```bash
#!/bin/bash
set -e

echo '1. Deleting any existing sandboxes...'
sudo -u qnoe-ai bash -c 'source /home/qnoe-ai/.profile && OPENSHELL_LOCAL_TLS_DIR=/home/qnoe-ai/.local/state/openshell/tls openshell sandbox delete qnoe-agent 2>/dev/null || true'

echo '2. Killing gateway...'
pkill -f openshell-gateway || true
sleep 2

echo '3. Generating fresh certs...'
rm -rf /home/qnoe-ai/.local/state/openshell/tls/
sudo -u qnoe-ai mkdir -p /home/qnoe-ai/.local/state/openshell/tls
sudo -u qnoe-ai /usr/bin/openshell-gateway generate-certs \
  --output-dir /home/qnoe-ai/.local/state/openshell/tls \
  --server-san 127.0.0.1 \
  --server-san 172.18.0.1 \
  --server-san host.openshell.internal

echo '4. Starting gateway...'
sudo -u qnoe-ai bash -c 'OPENSHELL_LOCAL_TLS_DIR=/home/qnoe-ai/.local/state/openshell/tls setsid /usr/bin/openshell-gateway --drivers docker > /opt/qnoe-agent/logs/gateway.log 2>&1 &'
sleep 3

echo '5. Re-registering CLI...'
sudo -u qnoe-ai bash -c 'source /home/qnoe-ai/.profile && OPENSHELL_LOCAL_TLS_DIR=/home/qnoe-ai/.local/state/openshell/tls openshell gateway remove openshell 2>/dev/null || true'
sudo -u qnoe-ai bash -c 'source /home/qnoe-ai/.profile && OPENSHELL_LOCAL_TLS_DIR=/home/qnoe-ai/.local/state/openshell/tls openshell gateway add --local https://127.0.0.1:17670'
sudo -u qnoe-ai bash -c 'source /home/qnoe-ai/.profile && OPENSHELL_LOCAL_TLS_DIR=/home/qnoe-ai/.local/state/openshell/tls openshell status'
echo Done.
```

**Notes:**
- Must delete existing sandbox BEFORE killing gateway — stale containers pick up the new gateway and fail with mismatched certs
- Certs are fully regenerated on every restart (delete TLS dir first — `generate-certs` won't overwrite existing files)
- `OPENSHELL_LOCAL_TLS_DIR` must be set for all `openshell` CLI calls
- `host.openshell.internal` SAN is critical — the supervisor uses this hostname and does strict verification
- `openssl s_client` doesn't check hostnames by default and will show OK even without this SAN — do not use it as a proxy for supervisor compatibility

---

#### 11.1 Inference provider (vLLM)

```bash
# Get the host LAN IP (NOT localhost — container sees a different namespace)
hostname -I | awk '{print $1}'   # note this IP

sudo -u qnoe-ai bash -c 'source /home/qnoe-ai/.profile && OPENSHELL_LOCAL_TLS_DIR=/home/qnoe-ai/.local/state/openshell/tls openshell provider create \
  --name local-vllm \
  --type openai \
  --credential OPENAI_API_KEY=none \
  --config OPENAI_BASE_URL=http://<HOST_LAN_IP>:8000/v1'

# Model ID is the full local path as reported by vLLM (check with: curl http://127.0.0.1:8000/v1/models)
sudo -u qnoe-ai bash -c 'source /home/qnoe-ai/.profile && OPENSHELL_LOCAL_TLS_DIR=/home/qnoe-ai/.local/state/openshell/tls openshell inference set \
  --provider local-vllm \
  --model /opt/qnoe-agent/models/hermes-3-70b-awq'
```

Agent code must use `base_url="https://inference.local/v1"` — the proxy intercepts and forwards to vLLM.

#### 11.2 Agent container Dockerfile

```dockerfile
# /opt/qnoe-agent/Dockerfile
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl iproute2 git \
    && rm -rf /var/lib/apt/lists/*

# Non-root sandbox user required by OpenShell (uid/gid 1000660000)
RUN groupadd -g 1000660000 sandbox && \
    useradd -m -u 1000660000 -g sandbox sandbox

RUN install -d -o sandbox -g sandbox /sandbox
WORKDIR /sandbox
USER sandbox

# Agent code, venv, models, and data are bind-mounted from host at runtime.
# Nothing to COPY here — rebuild only if base OS packages change.
```

#### 11.3 Sandbox policy

```yaml
# /opt/qnoe-agent/config/sandbox-policy.yaml
version: 1

filesystem_policy:
  read_only:
    - /opt/qnoe-agent/models
    - /opt/qnoe-agent/config
    - /opt/qnoe-agent/secrets
    - /opt/qnoe-agent/venv
    - /opt/qnoe-agent/agent
    - /ICFO/groups/NOE          # lab data server — read-only for T0/T1
    - /ICFO/smbhome/yzamir
  read_write:
    - /opt/qnoe-agent/memory    # SQLite DBs
    - /opt/qnoe-agent/logs      # audit + startup logs
    - /opt/qnoe-agent/skills    # skill registry
    - /ICFO/groups/NOE/ai_agent # agent write area inside NOE share

landlock:
  compatibility: best_effort

process:
  run_as_user: sandbox
  run_as_group: sandbox

network_policies:
  qdrant:
    name: qdrant-local
    endpoints:
      - host: 172.18.0.1        # Docker bridge IP — confirm with ip addr show docker0
        port: 6333
        protocol: rest
        enforcement: enforce
        access: read-write
        allowed_ips: ["172.16.0.0/12"]
    binaries:
      - path: /opt/qnoe-agent/venv/bin/python

  github:
    name: github-api
    endpoints:
      - host: api.github.com
        port: 443
        protocol: rest
        enforcement: enforce
        access: read-only       # T2+: hot-reload to read-write per approved repo
    binaries:
      - path: /opt/qnoe-agent/venv/bin/python
      - path: /usr/bin/git

  github_objects:
    name: github-objects
    endpoints:
      - host: github.com
        port: 443
      - host: objects.githubusercontent.com
        port: 443
    binaries:
      - path: /usr/bin/git

  teams:
    name: microsoft-teams
    endpoints:
      - host: graph.microsoft.com
        port: 443
        protocol: rest
        enforcement: enforce
        access: read-write
    binaries:
      - path: /opt/qnoe-agent/venv/bin/python
```

> **T2+ NOE write access:** the NOE bind-mount and filesystem policy are static (locked at sandbox creation). Promoting to write requires sandbox delete + recreate with `read_only: false` mount. Design the T2 approval gate to include this recreate step.

#### 11.4 Docker image build

The `.dockerignore` prevents Docker from sending large data directories as build context (avoids OOM and multi-minute hangs):

```
# /opt/qnoe-agent/.dockerignore
models/
qdrant_data/
memory/
logs/
skills/
secrets/
```

Build the image once and reuse it. Rebuild only if the base OS packages in the Dockerfile change:

```bash
cd /opt/qnoe-agent
docker build -t qnoe-agent:latest .
```

Always use `--from qnoe-agent:latest` (the pre-built tag) when creating sandboxes — **never** pass the Dockerfile path directly to `--from`. Passing the Dockerfile path sends the entire build context to the gateway and risks OOM with the 70B model loaded.

#### 11.5 Sandbox launch script

`/opt/qnoe-agent/launch_sandbox.sh` — used for manual launches and as the basis for the systemd service:

```bash
#!/bin/bash
source /home/qnoe-ai/.profile
export OPENSHELL_LOCAL_TLS_DIR=/home/qnoe-ai/.local/state/openshell/tls
openshell sandbox create \
  --name qnoe-agent \
  --from qnoe-agent:latest \
  --policy /opt/qnoe-agent/config/sandbox-policy.yaml \
  --provider local-vllm \
  --driver-config-json '{"docker":{"mounts":[{"source":"/opt/qnoe-agent","target":"/opt/qnoe-agent","type":"bind"},{"source":"/ICFO/groups/NOE","target":"/ICFO/groups/NOE","type":"bind","read_only":true}]}}' \
  -- echo "sandbox ok"
```

Replace `-- echo "sandbox ok"` with `-- python -m agent.main` for production.

Test launch (run as yzamir):
```bash
sudo -u qnoe-ai bash /opt/qnoe-agent/launch_sandbox.sh
```

---

### 12. Systemd services (production)

**Status (2026-06-12):** `vllm.service` and `openshell-gateway.service` installed and running. `qnoe-agent.service` installed but disabled — enable when Phase 1 agent code exists at `/opt/qnoe-agent/agent/`.

Three services: vLLM inference, OpenShell gateway, agent sandbox. Start order matters: vLLM → gateway → sandbox.

**Important lessons from installation:**
- All service scripts must have `#!/bin/bash` as the very first line — no leading whitespace. Write scripts with `printf` rather than heredocs with indentation to avoid accidental leading spaces (`status=203/EXEC`).
- `vllm.service` **must** include `Environment=PATH=/opt/qnoe-agent/venv/bin:...` — FlashInfer JIT-compiles a CUDA kernel using `ninja` at first startup. `ninja` is in the venv, not in systemd's default PATH. Missing this causes `FileNotFoundError: 'ninja'` after ~6 minutes of model loading.
- First vLLM startup takes ~7 minutes (model load + FlashInfer JIT compile). Subsequent starts use cached artifacts and take ~5 minutes.
- Service files themselves use `ExecStart=/path/to/script.sh` — do not inline complex commands with backslash continuations in the service file (quoting issues).

**Script files** (live at `/opt/qnoe-agent/scripts/`, local copies in `scripts/`):

`start_vllm.sh`:
```bash
#!/bin/bash
exec /opt/qnoe-agent/venv/bin/vllm serve /opt/qnoe-agent/models/hermes-3-70b-awq --host 0.0.0.0 --port 8000 --quantization awq_marlin --max-model-len 32768
```

`start_gateway.sh`: see §11.0 — regenerates certs and registers CLI on every start.

`start_agent.sh`: see §11.5 — deletes stale sandbox then runs `openshell sandbox create ... -- python -m agent.main`.

**Service files** (live at `/etc/systemd/system/`, local copies in `config/`):

`vllm.service`:
```ini
[Unit]
Description=vLLM Inference Server (Hermes 3 70B AWQ)
After=network.target

[Service]
User=qnoe-ai
Environment=PATH=/opt/qnoe-agent/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
ExecStart=/opt/qnoe-agent/scripts/start_vllm.sh
Restart=on-failure
RestartSec=30
TimeoutStartSec=600

[Install]
WantedBy=multi-user.target
```

`openshell-gateway.service`:
```ini
[Unit]
Description=OpenShell Gateway
After=docker.service
Requires=docker.service

[Service]
User=qnoe-ai
ExecStart=/opt/qnoe-agent/scripts/start_gateway.sh
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

`qnoe-agent.service`:
```ini
[Unit]
Description=QNOE Lab Agent (OpenShell sandbox)
After=network.target docker.service openshell-gateway.service vllm.service
Requires=docker.service openshell-gateway.service vllm.service

[Service]
User=qnoe-ai
ExecStart=/opt/qnoe-agent/scripts/start_agent.sh
Restart=on-failure
RestartSec=30

[Install]
WantedBy=multi-user.target
```

**Install commands** (already done — for reference on new machines):
```bash
sudo mkdir -p /opt/qnoe-agent/scripts
sudo cp ~/staging/start_vllm.sh /opt/qnoe-agent/scripts/
sudo cp ~/staging/start_gateway.sh /opt/qnoe-agent/scripts/
sudo cp ~/staging/start_agent.sh /opt/qnoe-agent/scripts/
sudo chmod +x /opt/qnoe-agent/scripts/*.sh
sudo chown qnoe-ai:qnoe-ai /opt/qnoe-agent/scripts/*.sh
sudo cp ~/staging/vllm.service /etc/systemd/system/
sudo cp ~/staging/openshell-gateway.service /etc/systemd/system/
sudo cp ~/staging/qnoe-agent.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable vllm openshell-gateway
sudo systemctl start vllm
# Wait ~7 minutes for first startup (model load + FlashInfer JIT compile)
sudo systemctl start openshell-gateway
# qnoe-agent.service: enable only after /opt/qnoe-agent/agent/ exists
# sudo systemctl enable --now qnoe-agent
```

- [ ] Create nightly 02:00 cron job (runs in order):
  ```bash
  # 1. Snapshot all Qdrant collections before re-indexing (insurance)
  for col in group-wide-prose group-wide-code qed-prose qed-code \
             superconductivity-prose superconductivity-code \
             photocurrent-prose photocurrent-code qtm-prose qtm-code \
             qsim-prose qsim-code xchiral-prose xchiral-code; do
    curl -s -X POST "http://localhost:6333/collections/${col}/snapshots"
  done
  # Retain last 7 days of snapshots only
  find /opt/qnoe-agent/qdrant_snapshots/ -mtime +7 -delete

  # 2. Run incremental re-indexing (hash-based, skips unchanged files)
  /opt/qnoe-agent/venv/bin/python -m agent.indexing.nightly_run
  ```
- [ ] Enable both services: `sudo systemctl enable openshell-gateway qnoe-agent`
- [ ] Test start/stop/status cycle before connecting to live data

---

### 13. Hermes Agent setup

**Status (2026-07-03):** Fully operational. `qnoe-hermes.service` running. Per-user profile routing live. Old `qnoe-agent.service` (LangGraph) killed and disabled.

Hermes Agent v0.17.0 replaces the LangGraph agent layer. It runs natively (no Docker/OpenShell sandbox) as a gateway process. The infrastructure (vLLM, Qdrant, watcher, nightly indexing) is unchanged.

#### 13.1 Install Hermes Agent

```bash
# Separate venv (openai version conflict with agent venv)
sudo -u qnoe-ai python3 -m venv /opt/qnoe-agent/hermes-venv
sudo -u qnoe-ai /opt/qnoe-agent/hermes-venv/bin/pip install hermes-agent==0.17.0
sudo -u qnoe-ai /opt/qnoe-agent/hermes-venv/bin/pip install einops  # required by nomic-embed

# Patch: lower minimum context length (Hermes default is 64K, vLLM serves 32K)
# In hermes-venv/.../agent/model_metadata.py: MINIMUM_CONTEXT_LENGTH = 16384
```

#### 13.2 Directory structure

```
/opt/qnoe-agent/hermes/              # HERMES_HOME root (set in .env)
├── .env                              # TEAMS_*, HERMES_HOME, AGENT_DATA_DIR
├── config.yaml                       # Main config (provider: custom, vLLM endpoint)
├── config/
│   └── user_profiles.yaml            # User ID → profile routing map
├── plugins/                          # All custom plugins (shared across profiles)
│   ├── teams_polling/__init__.py     # Teams adapter (Graph API polling)
│   ├── qnoe_rag/__init__.py         # RAG memory provider (Qdrant + nomic-embed)
│   └── qnoe_qcodes/__init__.py      # QCoDeS experiment registry tool
└── profiles/
    ├── qnoe-orchestrator/            # Default profile (unmapped users)
    │   ├── SOUL.md                   # System prompt (orchestrator personality)
    │   ├── memories/MEMORY.md
    │   ├── config.yaml               # Standalone (teams_polling.enabled: true)
    │   ├── .env → ../../.env         # Symlink
    │   └── plugins → ../../plugins   # Symlink (required for plugin discovery)
    ├── qnoe-qtm/                     # QTM sub-team profile
    │   ├── SOUL.md                   # QTM personality
    │   ├── memories/MEMORY.md
    │   ├── config.yaml               # teams_polling.enabled: false
    │   ├── .env → ../../.env
    │   └── plugins → ../../plugins
    └── qnoe-photocurrent/            # Photocurrent sub-team profile
        ├── SOUL.md
        ├── memories/MEMORY.md
        ├── config.yaml
        ├── .env → ../../.env
        └── plugins → ../../plugins
```

#### 13.3 Key config.yaml settings

```yaml
model:
  default: /opt/qnoe-agent/models/hermes-3-70b-awq
  provider: custom                    # NOT "vllm-local" — unknown to auth resolver
  base_url: http://localhost:8000/v1
  api_key: no-key-required            # Dummy value — vLLM has no auth
  context_length: 32768
  max_tokens: 4096                    # MUST cap — custom provider defaults to 65536
multiplex_profiles: true              # MUST be top-level (not under gateway:)
memory:
  provider: qnoe_rag                  # Exclusive memory provider plugin
toolsets:
  - hermes-cli
  - qnoe-lab
plugins:
  enabled:
    - qnoe_qcodes
```

#### 13.4 Plugin deployment

Plugins must exist in TWO locations:
1. **Source** (user plugins): `/opt/qnoe-agent/hermes/plugins/<name>/` — loaded via profile symlinks
2. **Runtime** (site-packages): `hermes-venv/.../site-packages/plugins/platforms/<name>/` — needed for Platform enum registration

The source copy (via symlink) takes precedence at runtime. Both must stay in sync.

```bash
# Deploy a plugin update
scp plugin_file.py yzamir@10.3.8.21:/tmp/
ssh dgx "sudo cp /tmp/plugin_file.py /opt/qnoe-agent/hermes/plugins/<name>/__init__.py && \
         sudo cp /tmp/plugin_file.py /opt/qnoe-agent/hermes-venv/.../plugins/platforms/<name>/__init__.py && \
         sudo chown -R qnoe-ai:qnoe-ai /opt/qnoe-agent/hermes/plugins/<name>/ && \
         sudo chmod -R g+w /opt/qnoe-agent/hermes/plugins/<name>/"
```

#### 13.5 Profile symlinks

Each profile needs symlinks for plugin discovery and secret access:

```bash
# Create plugin + env symlinks for each profile
sudo -u qnoe-ai ln -s /opt/qnoe-agent/hermes/plugins /opt/qnoe-agent/hermes/profiles/qnoe-orchestrator/plugins
sudo -u qnoe-ai ln -s /opt/qnoe-agent/hermes/plugins /opt/qnoe-agent/hermes/profiles/qnoe-qtm/plugins
sudo -u qnoe-ai ln -s /opt/qnoe-agent/hermes/plugins /opt/qnoe-agent/hermes/profiles/qnoe-photocurrent/plugins
sudo -u qnoe-ai ln -s /opt/qnoe-agent/hermes/.env /opt/qnoe-agent/hermes/profiles/qnoe-qtm/.env
sudo -u qnoe-ai ln -s /opt/qnoe-agent/hermes/.env /opt/qnoe-agent/hermes/profiles/qnoe-photocurrent/.env
```

#### 13.6 Hermes systemd service

`qnoe-hermes.service`:
```ini
[Unit]
Description=QNOE Hermes Agent Gateway
After=network.target vllm.service
Wants=vllm.service

[Service]
User=qnoe-ai
WorkingDirectory=/opt/qnoe-agent/hermes
ExecStart=/opt/qnoe-agent/scripts/start_hermes.sh
Restart=on-failure
RestartSec=10
Environment=PATH=/opt/qnoe-agent/hermes-venv/bin:/usr/local/bin:/usr/bin:/bin

[Install]
WantedBy=multi-user.target
```

`start_hermes.sh`:
```bash
#!/bin/bash
set -a
source /opt/qnoe-agent/hermes/.env
set +a
export HERMES_HOME=/opt/qnoe-agent/hermes/profiles/qnoe-orchestrator
exec /opt/qnoe-agent/hermes-venv/bin/hermes gateway run
```

```bash
# Install and enable
sudo cp start_hermes.sh /opt/qnoe-agent/scripts/
sudo chmod +x /opt/qnoe-agent/scripts/start_hermes.sh
sudo chown qnoe-ai:qnoe-ai /opt/qnoe-agent/scripts/start_hermes.sh
sudo cp qnoe-hermes.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now qnoe-hermes

# Disable old LangGraph agent
sudo systemctl disable qnoe-agent
```

#### 13.7 Per-user profile routing

The `teams_polling` adapter routes each Teams user to their sub-team profile:

1. Adapter loads `config/user_profiles.yaml` at startup
2. For each message, looks up sender by Azure AD user ID, then by display name
3. Sets `source.profile` on `SessionSource` → gateway loads that profile's SOUL.md, RAG, memories
4. `self.bot_token = self._username` prevents the multiplexer from creating duplicate adapters (credential dedup)

`user_profiles.yaml`:
```yaml
default: qnoe-orchestrator
users:
  "ef6f38c9-f873-4cc8-bbf3-e43cb69d8a16": qnoe-qtm   # Alexander Rothstein
users_by_name: {}
```

Collect user IDs: have each team member send a test message, then read IDs from `journalctl -u qnoe-hermes`.

#### 13.8 Gotchas (see also [[memory/mistakes]])

- **`HERMES_HOME` at runtime** = profile dir, not hermes root. Use `split("/profiles/")` to get root.
- **`_profile_runtime_scope`** isolates secrets — sub-profiles need `.env` symlink or config-level credentials.
- **Plugin auto-enable** — `gateway/config.py` overrides `enabled: false` for plugins whose env vars are present. Handled by `bot_token` credential dedup, not gateway patches.
- **`multiplex_profiles: true`** must be at config.yaml root level (not under `gateway:`).
- **Sub-profile configs** must have `gateway.platforms.teams_polling.enabled: false`.
- **Tool calling as text** — Hermes 3 70B sometimes outputs tool calls as plain text. Known issue.

---

## Validation checklist (before agent framework work begins)

- [ ] `nvidia-smi` shows GB10, no errors
- [ ] vLLM endpoint at `localhost:8000` returns a valid completion for a test prompt
- [ ] Qdrant at `localhost:6333` shows 7 collections
- [ ] SQLite DB exists and accepts an `INSERT` via Python
- [ ] `/ICFO/groups/NOE` is mounted and readable by `qnoe-ai` account
- [ ] OpenShell gateway is running: `sudo -u qnoe-ai openshell status` → Connected
- [ ] Agent sandbox launches: `openshell sandbox list` shows `qnoe-agent` in Ready state
- [ ] Sandbox network deny-all verified: outbound curl to external IP from sandbox returns 403
- [ ] Inference routing verified: `https://inference.local/v1/models` returns Hermes model from inside sandbox
- [ ] GitHub PAT can list repos via `curl -H "Authorization: token $(cat /opt/qnoe-agent/secrets/github_pat)" https://api.github.com/orgs/QNOE-group/repos`
- [ ] Both systemd services start and stay up for 5 minutes with no errors
