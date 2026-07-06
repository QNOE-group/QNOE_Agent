# QNOE Group AI Agent — Project Brief
*Last updated: 2026-05-26 (v2)*

---

## 1. Context & Setting

**Group:** QNOE (Quantum Nano-Optoelectronics) — ICFO, Barcelona  
**PI:** Frank Koppens | **Lab manager:** David Alcaraz  
**Size:** ~20 members (students + postdocs), several semi-independent sub-teams  
**Sub-teams:** QED · Photocurrent · SNOM · QTM (and others)  
**Maintainer of this agent system:** Designated person (initial deployer)

The agent is intended to function as a **virtual lab student** — proactive, knowledgeable about all group work, and capable of acting autonomously on routine and analytical tasks.

---

## 2. Hardware Platform

**NVIDIA DGX Spark** — on-premises compute node. All inference and agent logic runs **fully locally**; no data leaves the lab network.  
The agent runs under a **dedicated QNOE account** provisioned with appropriate access to all group resources.

---

## 3. Model Stack

- **Base model:** NVIDIA open-weight model (Llama or NVIDIA-native family — TBD)
- **Inference:** Local, on-premise only
- **Language:** Primarily text + code (Python); potential extension to tabular/scientific data modalities

---

## 4. Agent Paradigm

- **Proactive agent** — not purely reactive; initiates tasks, monitors state, acts autonomously within defined permissions
- Inspired by frameworks such as **OpenHands (OpenDevin)**, **Hermes**, and similar agentic systems
- Behaves as a **junior lab student**: takes initiative, asks when uncertain, learns from outcomes

### 4.1 Execution Model — **Decision Pending**

Three candidate models (see §11 for full pro/con analysis):
1. **Scheduled (cron)** — periodic jobs at fixed intervals
2. **Event-driven (triggers)** — reacts to GitHub pushes, new data files, Teams messages
3. **Continuous loop** — agent runs an always-on inner loop, polling and acting

> **Current preference:** Evaluate continuous loop; fall back to event-driven + scheduled hybrid if resource or safety concerns arise.

---

## 5. Core Capabilities

### Phase 1 (MVP)
| Capability | Description |
|---|---|
| **Data analysis** | Read QCoDeS datasets and numpy arrays from local server; run analysis; produce reports/notebooks |
| **Code maintenance** | Audit group GitHub repos; open PRs; apply fixes within permission boundaries |
| **Literature awareness** | Index and query papers, presentations stored on lab servers |
| **Communication** | Respond to and initiate conversations via Microsoft Teams |

### Phase 2 (future)
| Capability | Description |
|---|---|
| **Measurement integration** | Interface with existing instrument MCPs (no direct hardware control in Phase 1) |
| **Advanced scheduling** | Trigger measurement jobs, monitor running experiments |

---

## 6. Infrastructure Access

| Resource | Details | Access Method |
|---|---|---|
| **Group GitHub (QNOE-group)** | ~35 repos across projects, tools, data-replication, docs | Git + GitHub API (agent org account) |
| **Lab data server** | GBs of QCoDeS datasets + numpy arrays; **not** on GitHub | Local network mount (read + write) |
| **Literature / presentations** | PDFs, slides stored on lab servers | Local network mount (read) |
| **Microsoft Teams** | Primary human↔agent interface | Teams Bot / Microsoft Graph API |

### 6.1 Security Model
- **Open shell environment** is the foundational execution context — **mandatory**
- All access scopes, permissions, and trust boundaries are defined and enforced through this environment
- GitHub permissions follow the QNOE-group repo strategy (see §7)
- No credentials or sensitive data may be transmitted outside the lab network

---

## 7. GitHub Repository Strategy & Agent Permissions

Based on `QNOE-group-info/README.md`:

### Repo categories
| Category | Examples | Agent role |
|---|---|---|
| **Projects** | `BLG-QED`, `GRASP-Analysis`, `SLG07-PhQH` | Read + analysis + PR |
| **Tools** | `GRASP-TWINS`, `Nbandstructure`, `QTM_CodeBase` | Read + suggest fixes + PR |
| **Data / Replication** | `MoO3-hBN-MoO3`, device-specific repos | Read + analysis notebooks |
| **Docs / Lab** | `QNOE-group-info`, `NOE_GitHub_tutorial` | Read; PRs with maintainer approval |

### Per-repo architecture
- **Setup/instrument repos** — contain operational/acquisition code (e.g. `GRASP-Acquisition`, `FTIR-L205-RapidScan`, `QTM_CodeBase`). Agent can read and suggest; PRs require human review.
- **Analysis repos** — contain plotting/analysis notebooks (e.g. `GRASP-Analysis`, `SLG05_PhQH`). Agent can create/edit notebooks, open PRs, and self-merge only where explicitly permitted.

### Naming convention (for agent indexing)
Analysis repos follow `subteam-project-device` (e.g. `SLG07-PhQH` → subteam: photocurrent, project: PhQH, device: SLG07).

### Branch/merge rules
- **Read:** All repos the agent account has access to
- **Push / PR:** All repos in scope
- **Merge to `main`:** Only where explicitly granted; otherwise requires human approval

---

## 8. Data Layer

- **Primary format:** QCoDeS datasets (`.db` SQLite files + HDF5)
- **Secondary format:** NumPy arrays (`.npy`, `.npz`)
- **Volume:** GBs per experiment; not stored in GitHub — on **local data server**
- **Notebooks:** Jupyter (primary); Marimo (emerging — see `QNOE-marimo-examples`)
- **Agent access:** Mounted network path; read + write (for saving analysis outputs)

---

## 9. Memory System

Multi-tier persistent architecture:

| Tier | Content | Technology (TBD) |
|---|---|---|
| **Episodic** | Conversation history, task logs, user interactions | Vector DB (e.g. Chroma, Qdrant) |
| **Semantic** | Group knowledge: papers, repo docs, notebooks, READMEs | RAG over vector DB |
| **Procedural** | Skills, analysis templates, learned workflows | Structured skill registry |
| **Working** | Current task context, active files, recent events | In-context window |

Memory persists across sessions and is queryable at inference time.

---

## 10. Skill System

- **Definition:** A skill is a modular, versioned, callable Python tool — highly domain-specific (e.g. band structure calculation via `Nbandstructure`, QCoDeS data loading, SNOM image analysis)
- **Sources:**
  - Organically developed through the agent's own work
  - Imported from external scientist-contributed repositories (community tools)
  - Existing group code promoted to formal skills (e.g. `Nbandstructure`, `GRASP-TWINS`)
- **Format:** Python modules/packages with a defined interface; registered in a local skill registry
- **Versioning:** Git-tracked in a dedicated `agent-skills` repo

---

## 11. System Architecture — Layer Definitions

### 11.1 Layer overview

```
┌─────────────────────────────────────────────────────┐
│  Hermes 3 70B  (reasoning + tool-call decisions)    │  ← "what to do"
├─────────────────────────────────────────────────────┤
│  LangGraph     (orchestration, state, routing)      │  ← "what happens next"
├─────────────────────────────────────────────────────┤
│  Open shell    (universal execution primitive)      │  ← "how it happens"
│    git · python · nbconvert · safe_delete · ...     │
├─────────────────────────────────────────────────────┤
│  External resources                                 │
│    Lab data server · QNOE GitHub org · Literature   │
└─────────────────────────────────────────────────────┘
```

### 11.2 Hermes 3 70B — reasoning engine
- Decides which tool/skill to call and with what arguments
- Outputs structured tool-call JSON (trained explicitly for this)
- Stateless — knows nothing between calls except what is in the assembled context
- Does NOT route between agents, manage state, or enforce permissions
- One shared model instance; persona + scope controlled by system prompt per agent

### 11.3 LangGraph — orchestration runtime
- Maintains shared `AgentState` across the multi-agent graph
- Routes tool-call outputs to the correct executor node
- Intercepts every write action and enforces the T0–T4 permission tiers
- Manages the approval flow (sends Teams request, awaits confirmation)
- Runs the continuous perception loop and scheduled background sweeps
- Does NOT reason about tasks — that is entirely Hermes' job

### 11.4 Open shell — universal execution primitive (MANDATORY)
The open shell is the single execution surface through which all agent actions reach the world. It is not one tool among many — it is the foundation everything else runs on.

- **All permissions are defined here**, at the Unix account level: PATH whitelist, forbidden commands, filesystem access scopes
- **All external interactions go through shell commands:** `git` replaces a bespoke GitHub connector; `python` and `jupyter nbconvert` replace a bespoke Jupyter connector; QCoDeS data access is just Python in the shell
- **`safe_delete()` is implemented here** as a shell-level Python wrapper — the agent never calls `rm` directly
- **Audit trail** captures shell commands executed, not just high-level actions
- Security is enforced once, in one place, rather than duplicated across many connectors

### 11.5 Memory — queried before each Hermes call, written after
- **Qdrant** (semantic/RAG): context window injection — relevant code, papers, notebook outputs
- **SQLite** (episodic): recent event log, task history, approval records
- **Skill registry**: available tools injected into Hermes' system prompt as function definitions
- LangGraph assembles all three into the context that Hermes receives

---

## 12. Execution Model — Pro/Con Analysis

### Option A: Scheduled (Cron)
The agent wakes at fixed intervals (e.g. every hour, nightly) to perform pre-defined tasks.

| ✅ Pros | ❌ Cons |
|---|---|
| Predictable, bounded resource use | High latency — can miss events for hours |
| Easy to audit and debug | Cannot respond in real-time to Teams messages |
| Simple to implement and maintain | Feels passive, not truly proactive |
| Low risk of runaway actions | Misses ephemeral events (brief file changes, etc.) |

---

### Option B: Event-Driven (Triggers)
The agent wakes in response to specific events: GitHub push, new data file, Teams message, file watcher.

| ✅ Pros | ❌ Cons |
|---|---|
| Responsive to real events | Requires robust trigger infrastructure (webhooks, watchers) |
| Resource-efficient — idle when nothing happens | Complex to debug cascade failures |
| Natural fit for Teams interaction | Some events can be missed if trigger pipeline fails |
| Scales to many event types | Harder to handle "background awareness" tasks |

---

### Option C: Continuous Loop
The agent runs an always-on inner loop: poll → perceive → reason → act → sleep(N) → repeat.

| ✅ Pros | ❌ Cons |
|---|---|
| Truly proactive — can notice patterns over time | Constant GPU/memory pressure (model always loaded) |
| Real-time responsiveness | Higher risk of unintended autonomous actions |
| Mirrors how a human student actually works | Harder to audit: what did it do and why? |
| Simpler code architecture (one loop, not many handlers) | Requires robust action-gating and human-approval hooks |
| Model stays warm — low latency on all interactions | Loop bugs can spiral; needs watchdog/kill-switch |

---

### Recommendation
A **hybrid** is likely optimal for the DGX Spark context:
- **Continuous loop** for perception and reasoning (model stays warm, always monitoring)
- **Event-driven gates** before any write action (PR, file edit, Teams post)
- **Scheduled sweeps** for heavyweight background tasks (full repo audit, literature indexing)

This gives continuous awareness with controlled action surfaces.

---

## 12. Resolved Design Decisions

| # | Question | Decision |
|---|---|---|
| 1 | Measurement equipment | Phase 1: none. Phase 2: via existing MCPs only |
| 2 | Data format/volume | QCoDeS + numpy, GBs, on local server |
| 3 | Execution model | TBD — see §11 |
| 4 | GitHub write access | PRs yes; direct merge where explicitly permitted |
| 5 | Primary language | Python |
| 6 | Skill format | Versioned Python packages in local skill registry |
| 7 | Execution environment | **Open shell — mandatory. All permissions defined here.** |
| 8 | User workflow | Jupyter notebooks (primary), Marimo (emerging) |
| 9 | System maintainer | Dedicated person (initial deployer) |

---

## 13. Next Steps

- [ ] Decide on execution model (§11) — continuous loop vs. hybrid
- [ ] Evaluate architecture alternatives (monolithic agent vs. multi-agent, RAG strategy)
- [ ] Select specific products and frameworks for each layer (model, vector DB, agent framework, Teams connector)
- [ ] Define MVP scope and phased rollout plan
- [ ] Set up agent GitHub org account with correct permission tiers
- [ ] Design open shell environment and access control schema


---

## 14. Multi-Agent Architecture

The system uses a **hierarchical multi-agent design**: one orchestrator with group-wide presence, and one specialist sub-agent per research sub-team.

### 14.1 Orchestrator Agent ("Lab Student")
- Single group-wide identity visible to all members via Teams
- Handles all incoming messages; routes tasks to the appropriate sub-agent
- Owns group-level memory (cross-team knowledge, meeting notes, shared tools)
- The only agent that posts to group-wide Teams channels
- Manages the global task queue and approval pipeline

### 14.2 Sub-Agents (one per sub-team)
Each sub-agent is a specialized instance with deep expertise in its sub-team's domain.

| Sub-Agent | Sub-team | Repos in scope (indicative) | Specialization |
|---|---|---|---|
| **QED-Agent** | QED | `BLG-QED`, `QED-*`, `Nbandstructure`, `Polaritons-On_Chip_FTIR` | Cavity QED, BLG devices, polaritons, light-matter coupling |
| **Superconductivity-Agent** | Superconductivity | `D3-BSCCO-MoO3`, `QED-BSCCO_*`, `MoO3-hBN-MoO3` | BSCCO, superconducting devices, hyperbolic materials |
| **Photocurrent-Agent** | Photocurrent | `SLG*-PhQH`, `Elisa-codes`, `GRASP-*` | Quantum Hall photocurrents, graphene transport, GRASP platform |
| **QTM-Agent** | QTM | `QTM_CodeBase`, `L208_Opticool` | Tunneling microscopy, cryogenic systems, room-T and cryo QTM |
| **QSIM-Agent** | QSIM | `QSIM_HeFIB`, `QSIM_Patterned_Kagome`, `SIM-Meep`, `gvAI` | Simulations, Kagome lattice, MEEP FDTD, condensed matter theory |
| **XCHIRAL-Agent** | XCHIRAL | *(repos TBD)* | Chirality, XCHIRAL-specific experimental and analysis work |

> Sub-agents share the same base model but differ in their RAG context (only their sub-team's repos, data, and literature are in their retrieval scope) and their system prompt (sub-team-specific persona and tool access).

### 14.3 Routing Logic
```
User message → Orchestrator
  ├── Sub-team keyword detected? → Route to sub-agent
  ├── Cross-team query? → Orchestrator synthesises from multiple sub-agents
  ├── Group-wide action? → Orchestrator handles directly
  └── Ambiguous? → Orchestrator asks user to clarify
```

### 14.4 Memory Separation
- Each sub-agent has its own **isolated semantic memory** (RAG index over its repos/data)
- The orchestrator has a **shared episodic memory** (conversation history, task logs)
- Cross-agent knowledge sharing happens via structured summaries, not raw context sharing

---

## 15. Permission & Approval System

### 15.1 Tier Definitions

| Tier | Label | Who can approve | Requires |
|---|---|---|---|
| **T0** | Read / Analyse | Autonomous | Nothing — runs freely |
| **T1** | Suggest / Draft | Autonomous | Nothing — drafts only, no write |
| **T2** | Write (own scope) | Repo owner / task requester | Single confirmation in Teams |
| **T3** | Write (group scope) | Designated group approvers (≤5 people) | Explicit approval from designated list |
| **T4** | Destructive | Special protocol (see §15.3) | Full safety stack (see below) |

### 15.2 Action Classification

| Action | Tier |
|---|---|
| Read files, index repos, run analysis | T0 |
| Open draft PR, post analysis to Teams | T1 |
| Merge PR on own repo, save output notebook | T2 |
| Edit shared tool repos, group-wide Teams posts | T3 |
| Delete / move data files, bulk file operations | T4 |
| Modify agent permissions or skill registry | T3 |
| Any operation on `main` branch of shared tools | T3 |

### 15.3 Destructive Operation Safety Stack (T4)

Every T4 operation is subject to all four layers in sequence. **All layers are mandatory and non-bypassable.**

```
Layer 1 — SCOPE LOCK
  The agent resolves the exact set of affected objects before doing anything else.
  No wildcards on critical paths. No recursive operations without explicit depth limit.
  If the resolved scope exceeds a configurable threshold (e.g. >100 files, >10 GB),
  the operation is automatically refused and escalated to T3 approvers.

Layer 2 — DRY-RUN MANIFEST
  The agent produces and posts to Teams a full manifest:
    • Operation type
    • Exact list of affected files/paths (or a count + sample if >50)
    • Total data volume
    • Estimated reversibility
  No confirmation is requested yet — the user must review the manifest first.

Layer 3 — TYPED CONFIRMATION
  The user must respond with a confirmation string that includes the scope:
    e.g.  CONFIRM DELETE 47 files /data/SLG07/raw/2024-03
  A generic "yes" or "ok" is rejected. The agent parses the confirmation and
  verifies it matches the manifest before proceeding.

Layer 4 — SNAPSHOT + TIME WINDOW
  Immediately before execution:
    a. A manifest JSON is written to /data/.agent-snapshots/<timestamp>/
    b. For file deletions: files are MOVED to /data/.trash/<timestamp>/ (soft-delete)
       — never hard-deleted by the agent
    c. A 5-minute cancellation window is announced in Teams
    d. Any group member (not just the requester) can type CANCEL <operation-id>
       during this window to abort
  After the window: operation executes. Audit log entry written.
```

### 15.4 Agent-Level Soft-Delete (No IT cooperation required)

Since the data server is managed by the IT team and cannot be modified at the OS/filesystem level, the soft-delete architecture is implemented **entirely within the agent's own code layer**.

The agent wraps every filesystem delete call in a `safe_delete()` function that:
1. Creates a `.agent_trash/<ISO-timestamp>/` directory on the server (using the agent's own write access — no IT involvement needed)
2. Moves the target file/directory there instead of deleting it
3. Writes a manifest JSON alongside the moved content
4. Logs the operation to the audit trail

```python
# All T4 delete ops go through this — rm is never called directly
def safe_delete(path: str, operation_id: str) -> None:
    trash_root = Path(SERVER_MOUNT) / ".agent_trash" / iso_timestamp()
    trash_root.mkdir(parents=True, exist_ok=True)
    shutil.move(path, trash_root / Path(path).name)
    write_manifest(trash_root, path, operation_id)
    audit_log(operation_id, action="soft_delete", src=path, dst=str(trash_root))
```

This is purely application-layer; IT does not need to configure anything. The `.agent_trash/` folder accumulates until a human (lab manager or maintainer) purges it on their own schedule. True data loss requires both the agent to act AND a human to manually empty the trash.

### 15.5 Audit Log
Every T2–T4 action is logged to a persistent audit file with:
- Timestamp
- Requesting user
- Approving user(s)
- Action type and scope
- Outcome (success / cancelled / failed)
- Link to snapshot if applicable

---

## 16. Resolved Design Decisions (updated)

| # | Question | Decision |
|---|---|---|
| 1 | Measurement equipment | Phase 1: none. Phase 2: via existing MCPs only |
| 2 | Data format/volume | QCoDeS + numpy, GBs, on local server |
| 3 | Execution model | Hybrid continuous loop (perception) + event gates (actions) + scheduled sweeps |
| 4 | GitHub write access | PRs yes; direct merge where explicitly permitted per tier system |
| 5 | Primary language | Python |
| 6 | Skill format | Versioned Python packages in local skill registry |
| 7 | Execution environment | **Open shell — mandatory. All permissions defined here.** |
| 8 | User workflow | Jupyter notebooks (primary), Marimo (emerging) |
| 9 | System maintainer | Dedicated person (initial deployer) |
| 10 | Agent identity | Single group-wide orchestrator + sub-agents per sub-team |
| 11 | Approval model | Tiered T0–T4; T4 uses 4-layer safety stack + soft-delete architecture |
| 12 | Dangerous ops | Scope lock → dry-run manifest → typed confirmation → snapshot + time window |

---

## 17. Next Steps

- [ ] **Decide execution model** — confirm hybrid continuous loop approach
- [ ] **Architecture deep-dive** — monolithic vs. multi-agent framework choice, RAG strategy
- [ ] **Product/framework selection** — model, vector DB, agent framework, Teams connector
- [ ] **Define MVP scope** — which sub-agent first? which capabilities in v1?
- [ ] **Set up agent GitHub account** with correct permission tiers per §15
- [ ] **Design open shell environment** and access control schema
- [ ] **Implement soft-delete** on data server before any agent has write access
