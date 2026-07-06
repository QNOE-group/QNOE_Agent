# QNOE Agent — Comprehensive Tools Plan
*Created: 2026-06-30*

This document catalogs every tool the agent needs, scored by user importance and implementation complexity, with a build-vs-download recommendation for each.

---

## Scoring Legend

**Importance** (to the end user — the researcher):
- **5** — Essential for MVP; agent is useless without it
- **4** — High value; covers a frequent user need
- **3** — Medium value; nice-to-have that improves experience significantly
- **2** — Low-frequency use but valuable when needed
- **1** — Edge case or Phase 3+ only

**Complexity** (effort to build from scratch):
- **5** — Multi-week effort; requires domain expertise, sandboxing, or external integrations
- **4** — Several days; non-trivial logic, error handling, security concerns
- **3** — 1-2 days; moderate logic, well-understood problem
- **2** — Half a day; straightforward wrapper
- **1** — Trivial; < 50 lines, mostly boilerplate

---

## Current State

### Deployed Tools (LLM-callable via tool_calls)

| Tool | Status | File |
|---|---|---|
| `read_file` | DEPLOYED | `agent/tools.py` |
| `list_directory` | DEPLOYED | `agent/tools.py` |
| `search_files` | DEPLOYED | `agent/tools.py` |

### Deployed Infrastructure (not LLM-callable — runs automatically)

| Component | Status | File |
|---|---|---|
| RAG retrieval | DEPLOYED — runs per turn | `agent/retrieval.py` |
| Watcher daemon | DEPLOYED — watches server for file changes | `agent/watcher/smb_watcher.py` |
| QCoDeS scanner | DEPLOYED — nightly scan of measurement DBs | `agent/ingest/qcodes_scanner.py` |
| Nightly reindex | DEPLOYED — 02:00 cron | `agent/indexing/nightly_run.py` |

### Installed Packages (ready for future tools)

| Package | Version | Purpose | Used by tools |
|---|---|---|---|
| `PyGithub` | installed | GitHub REST API wrapper | 4.1–4.6 (GitHub tools) |
| `GitPython` | 3.1.50 | Local git operations | 4.3, 9.3 |
| `arxiv` | installed | arXiv paper search | 3.2 (`search_arxiv`) |
| `duckduckgo-search` | installed | Web search, no API key | 3.3 (`search_web`) |
| `pint` | 0.25.3 | Unit conversion (SI, CGS) | 9.4 (`convert_units`) |
| `sympy` | 1.14.0 | Safe symbolic math | 2.3 (`calculate`) |
| `nbformat` | 5.10.4 | Parse .ipynb notebooks | 8.2 (`check_failing_notebooks`) |
| `semanticscholar` | installed | Academic paper search | 3.5 (`search_semantic_scholar`) |

Everything else below is **not yet built**.

---

## Tool Catalog

### Category 1 — File & Code Operations

| # | Tool | Description | Importance | Complexity | Recommendation |
|---|---|---|:---:|:---:|---|
| 1.1 | `read_file` | Read lines from a file with line range | 5 | 1 | **DONE** |
| 1.2 | `list_directory` | List directory contents | 5 | 1 | **DONE** |
| 1.3 | `search_files` | Glob/regex filename search across repos and server | 5 | 2 | **BUILD** — unique paths and ALLOWED_ROOTS |
| 1.4 | `grep_code` | Search file contents by keyword/regex | 5 | 2 | **BUILD** — wraps `grep -rn` with path validation |
| 1.5 | `file_info` | Get file metadata: size, modified date, type, line count | 3 | 1 | **BUILD** — trivial `os.stat` wrapper |
| 1.6 | `write_file` | Write/create a file (T2+ only) | 4 | 3 | **BUILD** — needs permission gate, backup, audit |
| 1.7 | `edit_file` | Apply a targeted edit (replace lines, insert, delete) | 3 | 4 | **BUILD** — diff-based, needs rollback support |

**Notes:**
- `search_files` and `grep_code` are the highest-impact missing tools. Without them, the agent cannot navigate the codebase — it must already know exact paths, which users rarely provide.
- `write_file` and `edit_file` are Phase 2 (T2 permission tier). Design now, implement when T2 gates are ready.
- No downloadable package fits our unique path validation and permission model. All file tools must be custom.

---

### Category 2 — Code Execution & Computation

| # | Tool | Description | Importance | Complexity | Recommendation |
|---|---|---|:---:|:---:|---|
| 2.1 | `run_python` | Execute a Python snippet in a sandboxed subprocess | 5 | 4 | **BUILD** — custom sandbox with whitelisted imports |
| 2.2 | `run_shell` | Execute a shell command (read-only, T0) | 3 | 3 | **BUILD** — command whitelist + timeout |
| 2.3 | `calculate` | Evaluate a math expression safely | 4 | 1 | **BUILD** — `ast.literal_eval` or `sympy.sympify` |

**Notes on `run_python` (the most important unbuilt tool):**

This is the tool that transforms the agent from a Q&A chatbot into a "lab student." Without it, the agent cannot:
- Compute statistics on measurement data
- Generate plots
- Run analysis scripts
- Do any quantitative work

**Sandbox design:**
- Run in a subprocess with `resource.setrlimit()` (CPU time, memory)
- Whitelist: `numpy`, `scipy`, `pandas`, `matplotlib`, `h5py`, `qcodes` (read-only)
- Blacklist: `os.system`, `subprocess`, `socket`, `importlib`, `__import__` of non-whitelisted modules
- Timeout: 60 seconds hard kill
- Output: stdout + stderr + any saved `.png` figure paths
- Filesystem: read-only access to `ALLOWED_ROOTS`; write only to a temp dir for figures

**Downloadable alternatives evaluated:**
| Package | Verdict |
|---|---|
| **E2B** (`pip install e2b`) | Cloud-only. Data leaves network. Rejected. |
| **Modal** | Cloud-only. Rejected. |
| **AIO Sandbox** (Docker) | Possible but overkill — we already run inside Docker. A subprocess sandbox with resource limits is sufficient for Phase 1. |
| **gVisor** | Good for Phase 2 hardening. Not needed for MVP where the agent is T0/T1 read-only. |
| **LangChain PythonREPL** (`langchain-experimental`) | Too permissive — no import whitelist, no resource limits. Useful as a reference but not directly usable. |

**Recommendation:** Build `run_python` as a custom subprocess sandbox. Reference LangChain's `PythonREPL` for the interface pattern but add whitelisting + resource limits. Consider gVisor hardening in Phase 2.

---

### Category 3 — Search & Retrieval

| # | Tool | Description | Importance | Complexity | Recommendation |
|---|---|---|:---:|:---:|---|
| 3.1 | `search_knowledge` | Explicit RAG query against Qdrant (user-triggered) | 5 | 2 | **BUILD** — wraps existing `retrieval.py` as a callable tool |
| 3.2 | `search_arxiv` | Search arXiv for papers by query | 3 | 1 | **DOWNLOAD** — `pip install arxiv` + thin wrapper |
| 3.3 | `search_web` | General web search for technical questions | 2 | 2 | **DOWNLOAD** — self-hosted SearxNG or DuckDuckGo API |
| 3.4 | `search_qcodes_runs` | Query the QCoDeS registry by device, date, parameters | 4 | 2 | **BUILD** — queries `qcodes_registry` SQLite table |
| 3.5 | `search_semantic_scholar` | Search Semantic Scholar for papers | 2 | 1 | **DOWNLOAD** — free API, no key needed |

**Notes:**
- `search_knowledge` is critical. Currently RAG runs automatically per turn, but the user cannot explicitly ask "search the QTM codebase for X" and get targeted results. Making it a callable tool gives the agent control over *what* to search and *which collections* to target.
- `search_arxiv`: The `arxiv` Python package (`pip install arxiv`) is mature and works offline after fetching. LangChain also has `ArxivQueryRun` in `langchain-community`. Either works.
- `search_web`: For a fully local option, **SearxNG** can be self-hosted in Docker and queried via REST API. Alternatively, DuckDuckGo has a free API (`pip install duckduckgo-search`). Both work without API keys.

**Downloadable packages:**
| Package | Install | Works offline? | API key? |
|---|---|---|---|
| `arxiv` | `pip install arxiv` | After fetch | No |
| `duckduckgo-search` | `pip install duckduckgo-search` | No | No |
| `semanticscholar` | `pip install semanticscholar` | No | No (free tier) |
| SearxNG | Docker container | Yes (self-hosted) | No |

---

### Category 4 — GitHub Operations

| # | Tool | Description | Importance | Complexity | Recommendation |
|---|---|---|:---:|:---:|---|
| 4.1 | `github_search_code` | Search code across QNOE repos via GitHub API | 4 | 2 | **BUILD** — `requests` + GitHub REST API |
| 4.2 | `github_get_pr` | Get PR details (diff, comments, status) | 3 | 2 | **BUILD** — GitHub REST API |
| 4.3 | `github_list_recent_commits` | List recent commits for a repo | 3 | 1 | **BUILD** — GitHub REST API |
| 4.4 | `github_create_pr` | Create a PR (T2) | 3 | 3 | **BUILD** — needs approval gate |
| 4.5 | `github_comment_pr` | Comment on a PR (T2) | 2 | 2 | **BUILD** — needs approval gate |
| 4.6 | `github_get_file` | Fetch a specific file from a repo at any ref | 3 | 1 | **BUILD** — GitHub REST API |

**Notes:**
- For Phase 1 (T0/T1), only read operations (4.1-4.3, 4.6) are needed.
- We already have repos cloned locally, so `github_search_code` could alternatively search local clones via `grep_code` (tool 1.4). The GitHub API version adds searching repos not yet cloned.
- **GitPython** (`pip install GitPython`) is useful for local git operations (log, diff, blame) but is not needed for the GitHub API tools.
- **PyGithub** (`pip install PyGithub`) provides a higher-level wrapper around the GitHub REST API. Worth using instead of raw `requests`.

**Downloadable packages:**
| Package | Install | What it does |
|---|---|---|
| `PyGithub` | `pip install PyGithub` | Full GitHub REST API wrapper. Mature, well-documented. |
| `GitPython` | `pip install GitPython` | Local git operations (log, diff, blame, status). |

**Recommendation:** Use **PyGithub** for all GitHub API tools. Use **GitPython** for local repo operations (diff, blame, log).

---

### Category 5 — Data Analysis & Visualization

| # | Tool | Description | Importance | Complexity | Recommendation |
|---|---|---|:---:|:---:|---|
| 5.1 | `load_qcodes_dataset` | Load QCoDeS measurement data (B3 skill) | 5 | 3 | **BUILD** — see PHASE2_BACKLOG.md B3 |
| 5.2 | `get_run_metadata` | Get QCoDeS run metadata without loading data | 4 | 2 | **BUILD** — see PHASE2_BACKLOG.md B3 |
| 5.3 | `basic_stats` | Compute min/max/mean/std/NaN count on a dataset | 4 | 1 | **BUILD** — thin numpy wrapper |
| 5.4 | `plot_1d` | Generate a 1D plot (x vs y) and return the image path | 4 | 2 | **BUILD** — matplotlib wrapper |
| 5.5 | `plot_2d` | Generate a 2D colormap and return the image path | 3 | 2 | **BUILD** — matplotlib wrapper |
| 5.6 | `fit_curve` | Fit a function to data (linear, polynomial, custom) | 3 | 2 | **BUILD** — `scipy.optimize.curve_fit` wrapper |
| 5.7 | `detect_anomalies` | Flag NaN runs, clipped values, noise floor issues | 3 | 3 | **BUILD** — domain-specific logic |

**Notes:**
- Tools 5.1-5.2 are the B3 skill from PHASE2_BACKLOG.md. They are the foundation for all data analysis.
- Tools 5.3-5.7 can alternatively be run *inside* `run_python` (tool 2.1) rather than as separate tools. The trade-off:
  - **Separate tools**: More reliable (deterministic code, no LLM-generated code risks), faster, smaller context usage
  - **Inside run_python**: More flexible (LLM can do arbitrary analysis), but slower and riskier
  - **Recommendation**: Build both. Separate tools for common operations; `run_python` as fallback for custom analysis.
- These are all domain-specific to our lab. No downloadable package covers them.

---

### Category 6 — Teams Communication

| # | Tool | Description | Importance | Complexity | Recommendation |
|---|---|---|:---:|:---:|---|
| 6.1 | `send_teams_message` | Send a message to a Teams channel or DM | 4 | 2 | **BUILD** — wraps existing Teams connector |
| 6.2 | `send_teams_card` | Send an Adaptive Card (formatted message with buttons) | 3 | 3 | **BUILD** — JSON card template + Graph API |
| 6.3 | `send_teams_file` | Upload and share a file (e.g., plot) in Teams | 3 | 3 | **BUILD** — Graph API file upload |
| 6.4 | `get_teams_user_info` | Look up a user's display name, email, team | 2 | 1 | **BUILD** — Graph API |

**Notes:**
- `send_teams_message` is already partially implemented in `agent/teams.py` as part of the reply flow, but not as an LLM-callable tool. Wrapping it as a tool lets the agent proactively send messages (e.g., notify a user about a failing notebook).
- For Adaptive Cards, Microsoft provides JSON templates. The `botbuilder-core` package (`pip install botbuilder-core`) has card builders, but for our polling-based approach, raw JSON + Graph API is simpler.
- No external package is needed; the Graph API is well-documented and our auth is already working.

---

### Category 7 — Memory & Context Management

| # | Tool | Description | Importance | Complexity | Recommendation |
|---|---|---|:---:|:---:|---|
| 7.1 | `remember_fact` | Store a user-specific fact in Mem0 | 3 | 2 | **BUILD** — wraps Mem0 `add()` |
| 7.2 | `recall_facts` | Retrieve stored facts about a user | 3 | 2 | **BUILD** — wraps Mem0 `search()` |
| 7.3 | `log_event` | Write an event to the episodic SQLite log | 4 | 1 | **BUILD** — simple INSERT |
| 7.4 | `get_task_history` | Retrieve past task outcomes for this session | 3 | 1 | **BUILD** — simple SELECT |

**Notes:**
- Mem0 (`pip install mem0ai`) is already in the design (INFERENCE_MEMORY.md L3.5). Tools 7.1-7.2 wrap its API.
- `log_event` and `get_task_history` are internal tools (not user-facing) but important for the agent's self-awareness.
- These are all thin wrappers around existing infrastructure. Low effort, high value.

---

### Category 8 — Proactive Monitoring (Trigger Tools)

| # | Tool | Description | Importance | Complexity | Recommendation |
|---|---|---|:---:|:---:|---|
| 8.1 | `check_stale_prs` | Find PRs with no activity > 48h | 3 | 2 | **BUILD** — PyGithub + time filter |
| 8.2 | `check_failing_notebooks` | Scan .ipynb files for error cell outputs | 4 | 3 | **BUILD** — JSON parse + error detection |
| 8.3 | `check_new_papers` | Detect newly indexed PDFs | 3 | 2 | **BUILD** — query index_manifest |
| 8.4 | `check_large_files` | Detect new files > N GB on data server | 2 | 1 | **BUILD** — watcher integration |

**Notes:**
- These are not user-callable tools — they run in the orchestrator's background loop (G7 triggers).
- They share infrastructure with the watcher daemon (`agent/watcher/smb_watcher.py`) already deployed.
- All must be custom-built; no generic package covers lab-specific trigger logic.

---

### Category 9 — Utility Tools

| # | Tool | Description | Importance | Complexity | Recommendation |
|---|---|---|:---:|:---:|---|
| 9.1 | `summarize_text` | Summarize a long document or code file | 4 | 2 | **BUILD** — calls Hermes with a summarization prompt |
| 9.2 | `explain_code` | Explain what a code block does | 4 | 1 | **BUILD** — calls Hermes with an explanation prompt |
| 9.3 | `diff_files` | Show differences between two files | 2 | 1 | **BUILD** — wraps `difflib.unified_diff` |
| 9.4 | `convert_units` | Convert between physical units | 2 | 1 | **DOWNLOAD** — `pip install pint` |
| 9.5 | `latex_render` | Render a LaTeX equation to an image | 1 | 2 | **DOWNLOAD** — `pip install matplotlib` (already available) |
| 9.6 | `format_table` | Format data as a markdown table | 2 | 1 | **BUILD** — trivial string formatting |

**Notes:**
- `summarize_text` and `explain_code` are "meta-tools" — they call the LLM itself with a specific prompt. Useful when the agent needs to process a large file that doesn't fit in context.
- `convert_units`: The **Pint** library (`pip install pint`) is the standard for unit conversions in Python physics. Mature, well-tested, and handles SI, CGS, and custom units.
- Most of these are simple enough to build inline.

---

## Priority Matrix — What to Build First

### Tier 1 — Build Immediately (MVP blockers)

| # | Tool | Importance | Complexity | Effort Est. |
|---|---|:---:|:---:|---|
| 1.3 | `search_files` | 5 | 2 | 2-3 hours |
| 1.4 | `grep_code` | 5 | 2 | 2-3 hours |
| 3.1 | `search_knowledge` | 5 | 2 | 2-3 hours |
| 2.1 | `run_python` | 5 | 4 | 1-2 days |

**Rationale:** Without file search and grep, the agent cannot navigate the codebase. Without explicit RAG search, it can't target specific collections. Without Python execution, it can't do any computation.

### Tier 2 — Build Next (High-value, moderate effort)

| # | Tool | Importance | Complexity | Effort Est. |
|---|---|:---:|:---:|---|
| 2.3 | `calculate` | 4 | 1 | 1 hour |
| 3.4 | `search_qcodes_runs` | 4 | 2 | 3-4 hours |
| 4.1 | `github_search_code` | 4 | 2 | 3-4 hours |
| 5.1 | `load_qcodes_dataset` | 5 | 3 | 1 day |
| 5.2 | `get_run_metadata` | 4 | 2 | half day |
| 6.1 | `send_teams_message` | 4 | 2 | 3-4 hours |
| 7.3 | `log_event` | 4 | 1 | 1 hour |
| 9.1 | `summarize_text` | 4 | 2 | 2-3 hours |

### Tier 3 — Build When Needed (Medium value)

| # | Tool | Importance | Complexity |
|---|---|:---:|:---:|
| 1.5 | `file_info` | 3 | 1 |
| 3.2 | `search_arxiv` | 3 | 1 |
| 4.2 | `github_get_pr` | 3 | 2 |
| 4.3 | `github_list_recent_commits` | 3 | 1 |
| 4.6 | `github_get_file` | 3 | 1 |
| 5.3 | `basic_stats` | 4 | 1 |
| 5.4 | `plot_1d` | 4 | 2 |
| 5.5 | `plot_2d` | 3 | 2 |
| 5.6 | `fit_curve` | 3 | 2 |
| 6.2 | `send_teams_card` | 3 | 3 |
| 6.3 | `send_teams_file` | 3 | 3 |
| 7.1 | `remember_fact` | 3 | 2 |
| 7.2 | `recall_facts` | 3 | 2 |
| 8.2 | `check_failing_notebooks` | 4 | 3 |

### Tier 4 — Phase 2+ (Lower priority or gated on permissions)

| # | Tool | Importance | Complexity |
|---|---|:---:|:---:|
| 1.6 | `write_file` | 4 | 3 |
| 1.7 | `edit_file` | 3 | 4 |
| 2.2 | `run_shell` | 3 | 3 |
| 3.3 | `search_web` | 2 | 2 |
| 3.5 | `search_semantic_scholar` | 2 | 1 |
| 4.4 | `github_create_pr` | 3 | 3 |
| 4.5 | `github_comment_pr` | 2 | 2 |
| 5.7 | `detect_anomalies` | 3 | 3 |
| 6.4 | `get_teams_user_info` | 2 | 1 |
| 7.4 | `get_task_history` | 3 | 1 |
| 8.1 | `check_stale_prs` | 3 | 2 |
| 8.3 | `check_new_papers` | 3 | 2 |
| 8.4 | `check_large_files` | 2 | 1 |
| 9.2 | `explain_code` | 4 | 1 |
| 9.3 | `diff_files` | 2 | 1 |
| 9.4 | `convert_units` | 2 | 1 |

---

## External Packages to Install

These are ready-made packages worth using instead of building from scratch:

| Package | Install | Used by tools | Why use it |
|---|---|---|---|
| **PyGithub** | `pip install PyGithub` | 4.1-4.6 | Full GitHub REST API wrapper; avoids raw `requests` boilerplate |
| **GitPython** | `pip install GitPython` | 4.3, 9.3 | Local git operations (log, diff, blame) |
| **arxiv** | `pip install arxiv` | 3.2 | Mature arXiv search API client |
| **duckduckgo-search** | `pip install duckduckgo-search` | 3.3 | Free web search, no API key |
| **pint** | `pip install pint` | 9.4 | Unit conversion (SI, CGS, custom) |
| **mem0ai** | `pip install mem0ai` | 7.1, 7.2 | User memory (already in design) |
| **nbformat** | `pip install nbformat` | 8.2 | Parse .ipynb files for error detection |
| **sympy** | `pip install sympy` | 2.3 | Safe symbolic math evaluation |

All of these are pip-installable, work offline (after install), and have no cloud dependencies.

---

## Packages Evaluated and Rejected

| Package | Why rejected |
|---|---|
| **Composio** (`composio-core`) | Cloud-dependent OAuth for most integrations. Our agent is air-gapped. Individual tools (GitHub, Teams) are better built with direct API calls. |
| **LangChain tools** (`langchain-community`) | Too heavyweight as a dependency for simple wrappers. Individual tools (PythonREPL, ArXiv) are useful as *reference implementations* but not worth the dependency chain. |
| **CrewAI tools** (`crewai-tools`) | Tightly coupled to CrewAI's agent loop. Hard to extract standalone. |
| **smolagents** (`smolagents`) | Code-writing agent paradigm doesn't match our tool-calling architecture. |
| **E2B** | Cloud-only sandbox. Data leaves network. |
| **Modal** | Cloud-only compute. Data leaves network. |
| **Phidata/Agno** | Full framework — we already have LangGraph. Not useful for individual tools. |
| **OpenAI Agents SDK** | Requires OpenAI API. Not compatible with local vLLM without significant adaptation. |

---

## Implementation Pattern

All tools follow the same pattern established in `agent/tools.py`:

```python
# 1. OpenAI-format tool definition (for vLLM)
TOOL_DEFINITIONS.append({
    "type": "function",
    "function": {
        "name": "tool_name",
        "description": "What it does and when to use it.",
        "parameters": {
            "type": "object",
            "properties": { ... },
            "required": [ ... ],
        },
    },
})

# 2. Python implementation
def tool_name(**kwargs) -> str:
    """Returns a string result (always — for LLM consumption)."""
    ...

# 3. Register in dispatch table
TOOL_FUNCTIONS["tool_name"] = tool_name
```

**Context window cost per tool:** Each tool definition adds ~100-150 tokens to the system prompt. With 32K context and 1,500 tokens budgeted for system prompt + skills, we can afford ~10-12 tools active at once. Tools should be grouped and only the relevant set loaded per sub-agent.

**Tool grouping by sub-agent:**

| Tool set | Tools included | Which agents |
|---|---|---|
| **Core** (always loaded) | `read_file`, `list_directory`, `search_files`, `grep_code`, `search_knowledge` | All |
| **Computation** | `run_python`, `calculate` | All |
| **Data** | `load_qcodes_dataset`, `get_run_metadata`, `search_qcodes_runs`, `basic_stats`, `plot_1d`, `plot_2d` | All (measurement sub-agents) |
| **GitHub** | `github_search_code`, `github_get_pr`, `github_list_recent_commits` | All |
| **Communication** | `send_teams_message`, `send_teams_card` | Orchestrator only (sub-agents reply via the graph) |
| **Memory** | `remember_fact`, `recall_facts`, `log_event` | Internal (not in system prompt) |
| **Write** (Phase 2) | `write_file`, `edit_file`, `github_create_pr` | T2+ gated |

---

## Summary Statistics

| Category | Total tools | Build custom | Download/wrap | Already done |
|---|---|---|---|---|
| File & Code | 7 | 5 | 0 | 2 |
| Code Execution | 3 | 3 | 0 | 0 |
| Search & Retrieval | 5 | 3 | 2 | 0 |
| GitHub | 6 | 6 (using PyGithub) | 0 | 0 |
| Data Analysis | 7 | 7 | 0 | 0 |
| Teams Communication | 4 | 4 | 0 | 0 |
| Memory & Context | 4 | 4 | 0 | 0 |
| Proactive Monitoring | 4 | 4 | 0 | 0 |
| Utilities | 6 | 4 | 2 | 0 |
| **Total** | **46** | **40** | **4** | **2** |

**Why mostly custom:** This agent has unique constraints (air-gapped network, CIFS mounts, permission tiers, QCoDeS domain) that no generic tool package covers. The tools themselves are simple — most are <100 lines. The complexity is in the security model (path validation, permission gates, audit logging), which must be consistent across all tools.

---

## Next Steps

1. **Implement Tier 1 tools** (4 tools): `search_files`, `grep_code`, `search_knowledge`, `run_python`
2. **Deploy and test** with the running agent on DGX
3. **Implement Tier 2 tools** (8 tools): `calculate`, `search_qcodes_runs`, `github_search_code`, `load_qcodes_dataset`, `get_run_metadata`, `send_teams_message`, `log_event`, `summarize_text`
4. **Install external packages** on DGX: `PyGithub`, `GitPython`, `arxiv`, `pint`, `sympy`, `nbformat`
5. **Proceed to Tier 3/4** as Phase 2 permission gates are built

---

## Inspiration Sources for All 40 Custom Tools

Reference implementations and source code to build from. Each link points to a working implementation we can adapt.

### File & Code Operations

| # | Tool | Inspiration Source | Notes |
|---|---|---|---|
| 1.3 | `search_files` | [LangChain FileSearchTool](https://github.com/langchain-ai/langchain/blob/master/libs/community/langchain_community/tools/file_management/list_dir.py) | Pattern: glob + directory walker. We added `find` fast-path + depth limit. |
| 1.4 | `grep_code` | [smolagents CodeSearchTool](https://github.com/huggingface/smolagents/blob/main/src/smolagents/default_tools.py) | Pattern: subprocess `grep -rn` with result capping. Also see [ripgrep](https://github.com/BurntSushi/ripgrep). |
| 1.5 | `file_info` | [LangChain FileManagement](https://github.com/langchain-ai/langchain/tree/master/libs/community/langchain_community/tools/file_management) | Trivial `os.stat` wrapper — barely needs inspiration. |
| 1.6 | `write_file` | [LangChain WriteFileTool](https://github.com/langchain-ai/langchain/blob/master/libs/community/langchain_community/tools/file_management/write_file.py) | Add permission gate (T2+) + backup before overwrite. |
| 1.7 | `edit_file` | [Aider edit format](https://github.com/paul-gauthier/aider/blob/main/aider/coders/editblock_coder.py) | Search/replace block pattern. Also see [Claude Code Edit tool pattern](https://docs.anthropic.com/en/docs/claude-code). |

### Code Execution

| # | Tool | Inspiration Source | Notes |
|---|---|---|---|
| 2.1 | `run_python` | [Secure Python Sandbox for LLM Agents (dida.do)](https://dida.do/blog/setting-up-a-secure-python-sandbox-for-llm-agents) | Best reference for subprocess + resource limits + import whitelist. |
| 2.1 | `run_python` (alt) | [LangChain PythonREPL](https://github.com/langchain-ai/langchain/blob/master/libs/experimental/langchain_experimental/utilities/python.py) | Simpler pattern — no sandbox. Use as interface reference only. |
| 2.1 | `run_python` (alt) | [Agency Swarm IPythonInterpreter](https://github.com/VRSEN/agency-swarm/blob/main/agency_swarm/tools/coding/IPythonInterpreter.py) | Persistent IPython session pattern. |
| 2.2 | `run_shell` | [Agency Swarm PersistentShellTool](https://github.com/VRSEN/agency-swarm/blob/main/agency_swarm/tools/general/PersistentShellTool.py) | Shell with state persistence between calls. |
| 2.3 | `calculate` | [SymPy safe eval](https://docs.sympy.org/latest/modules/parsing.html#sympy.parsing.sympy_parser.parse_expr) | `parse_expr` with `evaluate=False` for safe math. Also: `ast.literal_eval`. |

### Search & Retrieval

| # | Tool | Inspiration Source | Notes |
|---|---|---|---|
| 3.1 | `search_knowledge` | [LlamaIndex QueryEngineTool](https://github.com/run-llama/llama_index/blob/main/llama-index-core/llama_index/core/tools/query_engine.py) | Pattern: wrap existing retrieval as a callable tool with collection targeting. |
| 3.2 | `search_arxiv` | [LangChain ArxivQueryRun](https://github.com/langchain-ai/langchain/blob/master/libs/community/langchain_community/tools/arxiv/tool.py) | Thin wrapper around `pip install arxiv`. |
| 3.3 | `search_web` | [DuckDuckGo Search](https://github.com/deedy5/duckduckgo_search) | `pip install duckduckgo-search`. Also: [SearxNG self-hosted](https://github.com/searxng/searxng). |
| 3.4 | `search_qcodes_runs` | [LangChain SQLDatabaseToolkit](https://github.com/langchain-ai/langchain/blob/master/libs/community/langchain_community/utilities/sql_database.py) | Pattern for safe parameterized SQLite queries. We build a hardcoded query, not arbitrary SQL. |
| 3.5 | `search_semantic_scholar` | [semanticscholar PyPI](https://github.com/danielnsilva/semanticscholar) | `pip install semanticscholar`. Free API, no key. |

### GitHub Operations

| # | Tool | Inspiration Source | Notes |
|---|---|---|---|
| 4.1 | `github_search_code` | [PyGithub search_code](https://pygithub.readthedocs.io/en/stable/examples/Search.html) | `pip install PyGithub`. `g.search_code(query, org="QNOE-group")`. |
| 4.2 | `github_get_pr` | [PyGithub PullRequest](https://pygithub.readthedocs.io/en/stable/github_objects/PullRequest.html) | `repo.get_pull(number)` — returns diff, comments, status. |
| 4.3 | `github_list_recent_commits` | [PyGithub get_commits](https://pygithub.readthedocs.io/en/stable/github_objects/Repository.html#github.Repository.Repository.get_commits) | `repo.get_commits(since=datetime)`. |
| 4.4 | `github_create_pr` | [PyGithub create_pull](https://pygithub.readthedocs.io/en/stable/github_objects/Repository.html#github.Repository.Repository.create_pull) | T2 gated. `repo.create_pull(title, body, head, base)`. |
| 4.5 | `github_comment_pr` | [PyGithub create_issue_comment](https://pygithub.readthedocs.io/en/stable/github_objects/PullRequest.html#github.PullRequest.PullRequest.create_issue_comment) | T2 gated. `pr.create_issue_comment(body)`. |
| 4.6 | `github_get_file` | [PyGithub get_contents](https://pygithub.readthedocs.io/en/stable/github_objects/Repository.html#github.Repository.Repository.get_contents) | `repo.get_contents(path, ref=branch)`. |

### Data Analysis & Visualization

| # | Tool | Inspiration Source | Notes |
|---|---|---|---|
| 5.1 | `load_qcodes_dataset` | [QCoDeS DataSet API](https://qcodes.github.io/Qcodes/examples/DataSet/Accessing-data-in-DataSet.html) | `load_by_id()`, `.to_pandas_dataframe_dict()`. Row cap needed. |
| 5.2 | `get_run_metadata` | [QCoDeS experiment info](https://qcodes.github.io/Qcodes/examples/DataSet/Working-With-Pandas-DataFramedict.html) | `ds.run_id`, `ds.snapshot`, `ds.parameters`, `ds.run_timestamp()`. |
| 5.3 | `basic_stats` | [Pandas describe()](https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.describe.html) | `df.describe()` + NaN count. Trivial wrapper. |
| 5.4 | `plot_1d` | [matplotlib basic usage](https://matplotlib.org/stable/tutorials/pyplot.html) | `plt.plot(x, y)` + `savefig()`. Return path. |
| 5.5 | `plot_2d` | [matplotlib pcolormesh](https://matplotlib.org/stable/api/_as_gen/matplotlib.pyplot.pcolormesh.html) | `plt.pcolormesh(X, Y, Z)` + colorbar + `savefig()`. |
| 5.6 | `fit_curve` | [scipy curve_fit](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.curve_fit.html) | `curve_fit(f, xdata, ydata)`. Provide common models (linear, poly, exp). |
| 5.7 | `detect_anomalies` | [pandas + numpy anomaly patterns](https://machinelearningmastery.com/how-to-identify-outliers-in-your-data/) | NaN runs, IQR outliers, clipped values, zero-variance. Domain-specific. |

### Teams Communication

| # | Tool | Inspiration Source | Notes |
|---|---|---|---|
| 6.1 | `send_teams_message` | [MS Graph — Send chatMessage](https://learn.microsoft.com/en-us/graph/api/chatmessage-post) | POST `/chats/{id}/messages`. Already have auth in `teams.py`. |
| 6.2 | `send_teams_card` | [Adaptive Cards Designer](https://adaptivecards.io/designer/) | JSON schema + POST as attachment. [Python example](https://learn.microsoft.com/en-us/microsoftteams/platform/task-modules-and-cards/cards/cards-format). |
| 6.3 | `send_teams_file` | [MS Graph — Upload to OneDrive](https://learn.microsoft.com/en-us/graph/api/driveitem-put-content) | Upload to OneDrive, then share link in message. |
| 6.4 | `get_teams_user_info` | [MS Graph — Get user](https://learn.microsoft.com/en-us/graph/api/user-get) | GET `/users/{id}`. Returns displayName, mail, department. |

### Memory & Context

| # | Tool | Inspiration Source | Notes |
|---|---|---|---|
| 7.1 | `remember_fact` | [Mem0 quickstart](https://docs.mem0.ai/quickstart) | `m.add(text, user_id=uid)`. |
| 7.2 | `recall_facts` | [Mem0 search](https://docs.mem0.ai/features/search) | `m.search(query, user_id=uid)`. |
| 7.3 | `log_event` | [SQLite INSERT pattern](https://docs.python.org/3/library/sqlite3.html#sqlite3-howto-row-factory) | Parameterized INSERT into `events` table. Trivial. |
| 7.4 | `get_task_history` | [SQLite SELECT pattern](https://docs.python.org/3/library/sqlite3.html) | `SELECT * FROM task_history WHERE session_id=? ORDER BY timestamp DESC LIMIT 20`. |

### Proactive Monitoring

| # | Tool | Inspiration Source | Notes |
|---|---|---|---|
| 8.1 | `check_stale_prs` | [PyGithub list pulls with date filter](https://pygithub.readthedocs.io/en/stable/github_objects/Repository.html#github.Repository.Repository.get_pulls) | `repo.get_pulls(state='open')` + filter by `updated_at`. |
| 8.2 | `check_failing_notebooks` | [nbformat cell error check](https://nbformat.readthedocs.io/en/latest/api.html) | Parse `.ipynb` JSON → check `cell.outputs` for `output_type == "error"`. |
| 8.3 | `check_new_papers` | Custom — query `index_manifest` | `SELECT path FROM index_manifest WHERE content_type='pdf' AND indexed_at > ?`. |
| 8.4 | `check_large_files` | Custom — watcher integration | Check watcher queue or run `find -size +5G -newer marker_file`. |

### Utilities

| # | Tool | Inspiration Source | Notes |
|---|---|---|---|
| 9.1 | `summarize_text` | [LangChain summarize chain](https://python.langchain.com/docs/tutorials/summarization/) | Pattern: chunk text → map-reduce with LLM. We just call Hermes directly. |
| 9.2 | `explain_code` | Same pattern as 9.1 | System prompt: "Explain this code concisely." |
| 9.3 | `diff_files` | [Python difflib](https://docs.python.org/3/library/difflib.html#difflib.unified_diff) | `difflib.unified_diff()`. Trivial. |
| 9.4 | `convert_units` | [Pint documentation](https://pint.readthedocs.io/en/stable/) | `pip install pint`. `ureg.parse_expression("5 mV").to("V")`. |
| 9.5 | `latex_render` | [matplotlib mathtext](https://matplotlib.org/stable/gallery/text_labels_and_annotations/mathtext_demo.html) | `fig.text(0.5, 0.5, r"$\LaTeX$")` + `savefig()`. |
| 9.6 | `format_table` | [Python string formatting](https://docs.python.org/3/library/string.html#format-specification-mini-language) | Trivial markdown table generator. |

---

## Sources

### Agent tool frameworks evaluated
- [Composio — 1000+ AI Agent Integrations](https://composio.dev/toolkits)
- [LangChain Community Tools](https://docs.langchain.com/oss/python/langchain/tools)
- [smolagents — Hugging Face](https://huggingface.co/docs/smolagents)
- [CrewAI Tools](https://docs.crewai.com/en/concepts/tools)
- [Agency Swarm](https://github.com/VRSEN/agency-swarm)
- [Phidata/Agno](https://docs.phidata.com/introduction)

### Hermes function calling
- [NousResearch/Hermes-Function-Calling](https://github.com/NousResearch/Hermes-Function-Calling)
- [Hermes 3 agent function calling guide](https://internet10k.com/en/blog/hermes-3-agent-function-calling-en/)

### Code execution sandboxing
- [E2B — Secure Sandboxes](https://e2b.dev/)
- [Secure Python Sandbox for LLM Agents](https://dida.do/blog/setting-up-a-secure-python-sandbox-for-llm-agents)
- [Modal — Best Code Execution Sandboxes](https://modal.com/resources/best-code-execution-sandboxes-ai-agents)

### Lab-specific tools
- [QCoDeS DataSet API](https://qcodes.github.io/Qcodes/examples/DataSet/Accessing-data-in-DataSet.html)
- [Microsoft Graph API — Teams messaging](https://learn.microsoft.com/en-us/graph/api/chat-post-messages)
- [PyGithub documentation](https://pygithub.readthedocs.io/)

### General agent design
- [LLM Agents: The Ultimate Guide 2026](https://www.superannotate.com/blog/llm-agents)
- [Top 7 Python Frameworks for AI Agents](https://www.kdnuggets.com/top-7-python-frameworks-for-ai-agents)
- [Best Open Source Agent Frameworks 2026](https://www.firecrawl.dev/blog/best-open-source-agent-frameworks)
