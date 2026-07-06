# OpenShell Integration — Design Proposal
*Draft 2026-06-09 — for review before editing any existing docs*

---

## Summary

NVIDIA OpenShell is a purpose-built sandboxed runtime for AI agents. It replaces the majority of our hand-crafted shell security layer (DGX_SETUP.md §11) with kernel-level policy enforcement via declarative YAML config. This document identifies what changes, what is dropped, what stays, and exactly what the new configuration looks like.

---

## What OpenShell gives us that we were building manually

| What we designed                                        | OpenShell equivalent                                                                                                                                  |
| ------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| PATH whitelist in `.bashrc`                             | Container isolation — agent only has what's in the container image                                                                                    |
| Bash alias blocks for `rm`, `chmod`, `sudo` etc.        | `process: run_as_user: sandbox` (non-root, uid 1000660000) + Landlock LSM (kernel-level fs enforcement) + seccomp filters blocking dangerous syscalls |
| Shell audit hook → `shell_audit.log`                    | `openshell logs` — OCSF-structured audit of all network decisions, process events                                                                     |
| Manually written `start_agent.sh`                       | `openshell sandbox create -- python -m agent.main`                                                                                                    |
| systemd `ProtectSystem=strict`, `NoNewPrivileges`, etc. | Superseded by container isolation                                                                                                                     |
| Manual network egress blocking                          | OpenShell network policy — **deny-all by default**, explicit allow per endpoint+binary                                                                |
| `safe_delete()` soft-delete                             | Still needed (application-level Python semantics), but filesystem policy enforces path boundaries as a second layer                                   |

**DGX_SETUP.md §11 is almost entirely superseded.** The `.bashrc` additions we were about to write can be skipped.

---

## Architecture change

### Current design
```
Host (qnoe-ai account)
  └── systemd service → python -m agent.main (direct on host)
```

### Proposed design
```
Host (qnoe-ai account)
  └── OpenShell gateway (k3s in Docker)
       └── QNOE agent sandbox (Docker container)
            └── python -m agent.main
                 ├── filesystem: /opt/qnoe-agent/* (bind-mounted)
                 ├── filesystem: /ICFO/groups/NOE (bind-mounted, read-only T0/T1)
                 ├── inference: https://inference.local → vLLM at host:8000
                 └── network: Qdrant host:6333, GitHub API, Teams API
```

---

## What changes

### 1. One line change in agent Python code

Current: `base_url="http://localhost:8000/v1"`
Proposed: `base_url="https://inference.local/v1"` (dummy API key, proxy resolves it)

Everything else in LangGraph and the vLLM config is unchanged. vLLM still serves on the host at port 8000.

### 2. Qdrant network access from inside the container

Qdrant runs on the host at `localhost:6333`. From inside the Docker container, the host is reachable at the Docker bridge IP (typically `172.18.0.1`). The Python process needs a network policy entry for this.

The `qdrant_client` Python library uses the HTTP REST API. The binary in the policy is the Python interpreter.

```yaml
network_policies:
  qdrant:
    name: qdrant-local
    endpoints:
      - host: 172.18.0.1    # Docker bridge IP — confirm: ip addr show docker0 | grep inet
        port: 6333
        protocol: rest
        enforcement: enforce
        access: read-write
        allowed_ips: ["172.16.0.0/12"]   # required for RFC 1918 private IPs
    binaries:
      - path: /opt/qnoe-agent/venv/bin/python
```

### 3. Host paths bind-mounted into container

The agent needs `/opt/qnoe-agent/` (code, models reference, memory, skills) and `/ICFO/groups/NOE` (lab data). These are bind-mounted via `--driver-config-json` at sandbox creation:

```bash
openshell sandbox create \
  --driver-config-json '{"docker": {"mounts": [
    {"source": "/opt/qnoe-agent", "target": "/opt/qnoe-agent", "type": "bind"},
    {"source": "/ICFO/groups/NOE", "target": "/ICFO/groups/NOE", "type": "bind", "read_only": true}
  ]}}' \
  ...
```

Filesystem policy then grants access to these paths:
```yaml
filesystem_policy:
  read_only:
    - /ICFO/groups/NOE
  read_write:
    - /opt/qnoe-agent/memory
    - /opt/qnoe-agent/logs
    - /opt/qnoe-agent/skills
    - /tmp
```

### 4. GitHub PAT managed as OpenShell provider

Instead of storing the PAT in a file and hoping it doesn't leak into the container, OpenShell injects it as an env var and rewrites credential placeholders in HTTP requests. The PAT file on disk (`/opt/qnoe-agent/secrets/github_pat`) is only needed to register the provider — the sandbox never sees the file.

```bash
openshell provider create \
  --name github \
  --type github \
  --credential GITHUB_TOKEN=$(cat /opt/qnoe-agent/secrets/github_pat)
```

In Python agent code: use `GITHUB_TOKEN` env var (injected automatically when sandbox is created with `--provider github`).

### 5. Simplified systemd service

The `ProtectSystem=strict` and related systemd sandbox directives are superseded. The service becomes a thin wrapper that starts the sandbox:

```ini
[Unit]
Description=QNOE Agent (OpenShell sandbox)
After=network.target docker.service openshell-gateway.service
Requires=docker.service openshell-gateway.service

[Service]
User=qnoe-ai
ExecStart=openshell sandbox create \
  --name qnoe-agent \
  --from /opt/qnoe-agent/Dockerfile \
  --policy /opt/qnoe-agent/config/sandbox-policy.yaml \
  --provider github \
  --provider local-vllm \
  --driver-config-json '{"docker":{"mounts":[
    {"source":"/opt/qnoe-agent","target":"/opt/qnoe-agent","type":"bind"},
    {"source":"/ICFO/groups/NOE","target":"/ICFO/groups/NOE","type":"bind","read_only":true}
  ]}}' \
  -- python -m agent.main
ExecStop=openshell sandbox delete qnoe-agent
Restart=on-failure
RestartSec=30

[Install]
WantedBy=multi-user.target
```

A separate service starts the OpenShell gateway (one-time, not per-restart):
```ini
[Unit]
Description=OpenShell Gateway
After=docker.service
Requires=docker.service

[Service]
User=qnoe-ai
ExecStart=openshell gateway start
ExecStop=openshell gateway stop
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
```

---

## Full sandbox policy for QNOE agent

```yaml
# /opt/qnoe-agent/config/sandbox-policy.yaml
version: 1

# --- STATIC: locked at sandbox creation ---

filesystem_policy:
  include_workdir: false
  read_only:
    - /usr
    - /lib
    - /proc
    - /dev/urandom
    - /etc
    - /opt/qnoe-agent/models      # read model configs (not loaded directly — vLLM is on host)
    - /opt/qnoe-agent/config      # read config files
    - /opt/qnoe-agent/secrets     # read GitHub PAT for provider registration
    - /opt/qnoe-agent/venv        # Python venv (read-only, don't let agent modify packages)
    - /opt/qnoe-agent/agent       # agent source code (read-only)
    - /ICFO/groups/NOE            # lab data server — read-only for T0/T1
    - /ICFO/smbhome/yzamir        # personal share — read-only
  read_write:
    - /opt/qnoe-agent/memory      # SQLite DBs (episodic.db, checkpoints.db)
    - /opt/qnoe-agent/logs        # audit + startup logs
    - /opt/qnoe-agent/skills      # skill registry (agent can write new skills with approval)
    - /tmp

landlock:
  compatibility: best_effort

process:
  run_as_user: sandbox
  run_as_group: sandbox

# --- DYNAMIC: hot-reloadable ---

network_policies:

  # Qdrant vector DB on host (Docker bridge)
  qdrant:
    name: qdrant-local
    endpoints:
      - host: 172.18.0.1          # Docker bridge IP — verify with: ip addr show docker0
        port: 6333
        protocol: rest
        enforcement: enforce
        access: read-write
        allowed_ips: ["172.16.0.0/12"]
    binaries:
      - path: /opt/qnoe-agent/venv/bin/python

  # GitHub — read-only for T0/T1 (upgraded to read-write for T2+ via policy update)
  github:
    name: github-api
    endpoints:
      - host: api.github.com
        port: 443
        protocol: rest
        enforcement: enforce
        access: read-only         # T2+: change to read-write + add specific deny_rules
    binaries:
      - path: /opt/qnoe-agent/venv/bin/python
      - path: /usr/bin/git

  # GitHub raw content (for cloning/fetching)
  github_objects:
    name: github-objects
    endpoints:
      - host: github.com
        port: 443
      - host: objects.githubusercontent.com
        port: 443
    binaries:
      - path: /usr/bin/git

  # Microsoft Teams / Graph API (for sending messages)
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

  # PyPI — needed if agent installs packages (skill registry)
  # DISABLED for T0/T1 MVP. Enable when skill registry is active.
  # pypi:
  #   name: pypi
  #   endpoints:
  #     - host: pypi.org
  #       port: 443
  #     - host: files.pythonhosted.org
  #       port: 443
  #   binaries:
  #     - path: /opt/qnoe-agent/venv/bin/uv
```

### Notes on the policy

- **Inference (`inference.local`)** is NOT in `network_policies` — it is a special endpoint handled by the Privacy Router, configured separately via `openshell provider create` + `openshell inference set`. The proxy intercepts all traffic to `inference.local` automatically.
- **T2+ write access** to GitHub: use `openshell policy update` to change `access: read-only` to `read-write` + add `deny_rules` for destructive operations (branch protection changes, force pushes, etc.) on the approved repo only. This is a hot-reload — no sandbox restart needed.
- **NOE share for T2+ write**: the bind-mount at creation time is `read_only: true`. Changing it to writable requires sandbox delete + recreate (static, part of the container config). This should happen as part of the T2 implementation phase.

---

## New Dockerfile for agent container

```dockerfile
# /opt/qnoe-agent/Dockerfile
FROM python:3.12-slim

# Network + filesystem tools required by OpenShell
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl iproute2 git \
    && rm -rf /var/lib/apt/lists/*

# Non-root sandbox user required by OpenShell (uid/gid 1000660000)
RUN groupadd -g 1000660000 sandbox && \
    useradd -m -u 1000660000 -g sandbox sandbox

# Working directory — owned by sandbox user
RUN install -d -o sandbox -g sandbox /sandbox
WORKDIR /sandbox
USER sandbox

# Agent code and venv are bind-mounted from host at /opt/qnoe-agent/
# Nothing to COPY here — all paths come in via --driver-config-json mounts
```

The container image is intentionally minimal. All agent code, the venv, models reference, and data are bind-mounted from the host — no need to rebuild the image when code changes.

---

## New files needed

| File | Purpose | Static/Dynamic |
|---|---|---|
| `/opt/qnoe-agent/Dockerfile` | Minimal container image for the agent | n/a |
| `/opt/qnoe-agent/config/sandbox-policy.yaml` | Full policy (see above) | filesystem/landlock/process static; network dynamic |
| `/etc/systemd/system/openshell-gateway.service` | Starts OpenShell gateway on boot | n/a |
| `/etc/systemd/system/qnoe-agent.service` | Starts agent sandbox on boot (revised) | n/a |

---

## What stays the same

| Component | Status |
|---|---|
| vLLM serving Hermes 3 70B | Unchanged — runs on host |
| Qdrant (host) | Unchanged — sandbox reaches it via network policy |
| SQLite episodic store | Unchanged — accessible via filesystem policy (bind-mounted) |
| LangGraph framework | Unchanged |
| Mem0 integration | Unchanged |
| Permission tiers T0–T4 | Unchanged — application logic |
| `safe_delete()` Python wrapper | Still needed — OpenShell provides second enforcement layer, not a replacement |
| Teams bot integration | Unchanged — needs network policy entry (already in policy above) |

---

## What is dropped

| Item | Reason |
|---|---|
| `.bashrc` PATH restriction + command blocks | Superseded by container isolation + Landlock |
| Custom shell audit hook | Superseded by `openshell logs` |
| `start_agent.sh` | Superseded by `openshell sandbox create` |
| systemd `ProtectSystem`, `NoNewPrivileges` etc. | Superseded by container isolation |
| Most of DGX_SETUP.md §11 sub-tasks | See above |

---

## What is added (setup steps)

1. Add `qnoe-ai` to docker group: `sudo usermod -aG docker qnoe-ai`
2. Configure NVIDIA container runtime: `sudo nvidia-ctk runtime configure --runtime=docker && sudo systemctl restart docker`
3. Install OpenShell as `qnoe-ai`: `sudo -u qnoe-ai uv tool install -U openshell`
4. Register vLLM inference provider
5. Register GitHub provider (once PAT is ready)
6. Write `Dockerfile` and `sandbox-policy.yaml`
7. Write and enable `openshell-gateway.service` + revised `qnoe-agent.service`
8. Verify Docker bridge IP and update policy accordingly

---

## Open questions

1. **`--driver-config-json` exact Docker volume mount keys** — need to verify the precise JSON keys for bind mounts in the Docker driver. The docs reference snake_case driver settings but do not show a full volume mount example. Verify once OpenShell is installed (`openshell sandbox create --help` + test).

2. **Docker bridge IP on DGX** — typical is `172.18.0.1` but may differ. Confirm: `ip addr show docker0 | grep inet`. This goes in the Qdrant network policy.

3. **`qnoe-ai` user env for `uv tool`** — `uv tool install` installs into the user's tool dir. Confirm the installed `openshell` binary is on `qnoe-ai`'s PATH after install.

4. **NOE share write access for T2+** — bind-mount is static (locked at creation). T2 write access requires sandbox recreate. Design the approval gate to include this. Document in AGENT_FRAMEWORK.md.

---

## Suggested doc updates (once approved)

1. `DGX_SETUP.md §11` — replace manual shell hardening tasks with OpenShell setup steps
2. `DGX_SETUP.md §12` — simplify systemd service, add gateway service, drop ProtectSystem directives
3. Add `DGX_SETUP.md §13` — OpenShell: install, gateway, policy, Dockerfile
4. `AGENT_FRAMEWORK.md` — update shell tool to use `inference.local`; note no application-level command whitelist needed
5. `HANDOFF.md` + `CLAUDE.md` — update infrastructure table (add Dockerfile and policy paths)
6. `TODO.md` — mark §11 manual tasks as superseded, add OpenShell setup tasks
