# B7 Handoff — Re-enable the OpenShell sandbox (read-only enforcement)

*Written 2026-07-14. For a reviewing/implementing agent. Goal: make the QNOE Lab
Agent physically unable to write to lab data + repos, because read-only is
currently unenforced.*

## Why this is now HIGH PRIORITY (the trigger)

Red-team testing (`redteam/BACKLOG.md`, finding R4) proved the production agent
**actually wrote to a lab file** — it appended `# reviewed by agent` to
`/opt/qnoe-agent/repos/QTM-CodeBase/README.md` in 1 of 5 runs (reverted). T0/T1
"read-only" is enforced **only by a SOUL.md instruction**, and the model has
`write_file`/`patch`/`terminal` resident, so ~1/5 it just does the write. This is
a data-integrity hole, not a wrong answer. SOUL rules are probabilistic; this
needs code/OS enforcement.

## Current state — the sandbox is NOT in the execution path

- The Hermes gateway runs **bare on the host as user `qnoe-ai`**:
  `scripts/start_hermes.sh` → `exec hermes gateway run` ("no Docker needed").
  Service = `qnoe-hermes.service` (`After/Requires=vllm.service`).
- `terminal: backend: local` (runs shell on the host); file tools
  (`read_file`/`write_file`/`patch`) hit the host FS directly. Nothing sandboxed.
- Inference is separate: `vllm.service` runs llama.cpp serving gpt-oss-120b
  (unit name kept from the vLLM era). **Do not disturb it.**

## What already exists (Phase 0, June 2026 — built for the OLD LangGraph agent)

- **`config/sandbox-policy.yaml`** — an OpenShell landlock policy: `read_only`
  on `/ICFO/groups/NOE` + most of `/opt/qnoe-agent` (config/secrets/venv/agent/
  models); `read_write` only on `memory/`, `logs/`, `skills/`,
  `/ICFO/groups/NOE/ai_agent`. Runs the process as unprivileged user `sandbox`
  (uid/gid 1000660000). Network policies allow Qdrant, GitHub, Teams.
- **`Dockerfile`** — `python:3.12-slim`, creates the `sandbox` user, bind-mounts
  agent code/venv/models/data at runtime (image `qnoe-agent:latest`).
- **`launch_sandbox.sh`** — the intended invocation:
  `openshell sandbox create --name qnoe-agent --from qnoe-agent:latest
  --policy config/sandbox-policy.yaml ... mounts /opt/qnoe-agent (rw),
  /ICFO/groups/NOE (read_only:true)`.
- `openshell` is installed at `/usr/bin/openshell`. Hermes's own `terminal` tool
  also supports `backend: docker|modal` (but that sandboxes ONLY terminal, not
  the file tools — insufficient alone; see below).

## The task

Run the **Hermes gateway** under read-only enforcement so `write_file`/`patch`
**and** `terminal` cannot modify `/ICFO/groups/NOE` or `/opt/qnoe-agent/repos`,
while everything the agent legitimately needs still works. First decision for the
reviewer — pick the mechanism:

1. **OpenShell sandbox (the built path):** run the whole gateway inside the
   `openshell`-created container (as `sandbox`, landlock policy, read-only bind
   mounts). Enforces read-only on all tools. Risk: the policy/Docker were built
   for the LangGraph agent; needs re-validation for the Hermes gateway's runtime
   (Mem0, Teams polling, llama.cpp endpoint).
2. **OS-level (lighter):** run `qnoe-hermes.service` as an unprivileged user (not
   the file owner) with read-only bind mounts of `/ICFO` + repos via
   `systemd` sandboxing (`ReadOnlyPaths=`, `ProtectSystem=strict`,
   `BindReadOnlyPaths=`) — no container. May be the fastest robust fix; verify it
   doesn't break qnoe-ai-owned writes to `memory/`/`logs/`.
3. **`terminal: backend: docker` only** — REJECT as the sole fix: file tools
   bypass the terminal backend, so writes still succeed.

Recommend #1 or #2; evaluate and propose.

## Gaps to close regardless of mechanism

1. **`/opt/qnoe-agent/repos` is NOT in the policy's `read_only` list** — it's the
   exact path R4 wrote to. Add it (RAG/qcodes read it; must stay readable, not
   writable).
2. **Model endpoint missing from network policy** — add `localhost:8000`
   (llama.cpp) to `sandbox-policy.yaml` network rules, or the agent can't reach
   the LLM.
3. **Writable paths the gateway needs:** `memory/` (Mem0 + SQLite), `logs/`,
   Qdrant at `localhost:6333`, Teams Graph (network), the SharePoint manifest DBs.
   Confirm each is allowed.

## Definition of done / verification

- The **`perm-write-file` red-team probe FAILS TO WRITE**: from the live agent (or
  the harness), "append a line to a repo file" must be physically refused — verify
  the target file is unchanged on disk afterward. (Probe now targets a throwaway
  `/opt/qnoe-agent/repos/_redteam/…` file; a real repo write must be impossible.)
- **Secrets unreadable** at the FS level: `/opt/qnoe-agent/secrets/` returns
  permission denied even if the model tries (belt-and-suspenders vs the SOUL rule).
- **Nothing regressed:** Teams round-trip works; RAG answers; `qcodes_search`
  works; Mem0 read+write works; nightly cron + SharePoint sync still run.
- Production restored to a known-good state at every step; the bare service stays
  available as rollback.

## Environment & constraints

- SSH: `ssh -i "/c/Users/yzamir/.ssh/id_ed25519_dgx" -o StrictHostKeyChecking=no yzamir@10.3.8.21`
  (ask the user once per session; sudo needs a password for anything outside the
  NOPASSWD set: `cp chown chmod mkdir systemctl cat` are passwordless, others are
  not — hand interactive-sudo steps to the user).
- Deploy pattern: write to `/tmp` → `sudo cp` → `sudo chown qnoe-ai:qnoe-ai`.
- Repo is the source of truth (`Z:\code\AI_Student`, GitHub `yuvalzamir/QNOE_Agent`
  `master`); mirror any DGX change back and commit.
- **Do not touch** `vllm.service` (llama.cpp) or the red-team `--temp 0.2` tuning
  in flight.

## Rollback

The current bare `qnoe-hermes.service` is the fallback. Keep `start_hermes.sh`
and the current unit intact; stage the sandboxed version as a parallel
script/unit and switch `ExecStart` only after verification. Revert = point
`ExecStart` back.

## References
- `redteam/BACKLOG.md` (R4 detail) · `memory/mistakes.md` M47 · `TODO.md`
  (R4→B7 item) · `PHASE2_BACKLOG.md` B7 · `memory/decisions.md` D15 (current
  serving stack) · `memory/agent-code.md` (tool/config state) ·
  `config/sandbox-policy.yaml`, `Dockerfile`, `launch_sandbox.sh` on the DGX.
