# Memory System Alternatives Analysis
*Last updated: 2026-05-29*

---

## Context

This document evaluates off-the-shelf memory solutions as potential replacements or
simplifications of the custom memory architecture designed for the QNOE Lab Agent.
The goal: something simpler to set up that performs well with large amounts of data.

---

## Requirements baseline

What the system must do — derived from the current architecture:

| Requirement | Detail |
|---|---|
| **Fully local / air-gapped** | No data leaves the DGX. No cloud API calls |
| **Large corpus** | All group repos, PDFs, notebooks, QCoDeS metadata — potentially hundreds of GBs |
| **Multiple content types** | Python, Jupyter, PDFs, Word docs, QCoDeS DBs |
| **Per-user scoping** | 10–15 researchers, isolated memory per person |
| **Cross-conversation recall** | "What did we decide about X in March?" |
| **LangGraph compatible** | Must plug into the existing agent framework |
| **Semantic + exact-term retrieval** | Device IDs, function names, paper titles |
| **Episodic + knowledge store** | Both what happened and what is known |
| **Persistent across DGX restarts** | Durable storage, not in-memory |
| **Audit trail** | T2–T4 action log |

---

## Option 1 — Zep Community Edition + Graphiti

### What it is

Zep is a framework-agnostic memory layer built on Graphiti, a temporal knowledge
graph engine. It stores facts as nodes with validity windows, tracks how facts change
over time, and uses hybrid retrieval combining semantic embeddings, BM25 keyword
search, and graph traversal — without requiring LLM inference at query time.
LangGraph integration is documented and maintained. Community Edition is fully
self-hostable (Apache 2.0).

### ✅ Pros
- Handles temporal reasoning natively — "what approach did we use before we switched?"
- Hybrid retrieval (semantic + BM25) covers meaning and exact-term matching in one system
- Entity resolution tracks the same entity across unstructured conversations and structured records
- LangGraph integration is maintained
- Fully self-hostable, no cloud dependency
- Production-proven (Zep Cloud serves millions of DAUs; CE shares the same core)

### ❌ Cons
- Requires Neo4j as a dependency — another system to operate on the DGX
- Designed for conversation memory and user facts, **not** large document corpora —
  you'd still need a separate RAG layer for lab knowledge (repos, PDFs, notebooks)
- Does not replace the document indexing pipeline

### What it replaces in the current design
Mem0 (L3.5) + SQLite episodic store (L3). Does **not** replace Qdrant RAG (L1/L2).

### Verdict
Best if temporal reasoning matters. Medium setup complexity. Does not solve the
full-corpus problem.

---

## Option 2 — Mem0 (self-hosted, open source)

### What it is

Mem0 is a self-improving memory layer that extracts and persists distilled facts
about individual users across conversations. It points at your existing Qdrant
instance as a vector store and uses your local LLM for extraction. p95 retrieval
latency: 0.200s. LangGraph native integration. Apache 2.0.

Already included in the current design as L3.5 — listed here for completeness
as a candidate for a more central role.

### ✅ Pros
- Simplest setup of all options — points at existing Qdrant, done
- Per-user scoping built in via `user_id`
- Up to 80% prompt token reduction via memory compression
- No extra infrastructure beyond what is already planned
- LangGraph native integration

### ❌ Cons
- Flat key-value architecture — no knowledge graph, no entity extraction,
  no relationship modeling, limited ability to build institutional knowledge
- Designed for user-level fact extraction only — does not handle large document
  corpus indexing at all
- Everything else (RAG, episodic task log) still needs to be built separately

### What it replaces in the current design
L3.5 user memory only. Nothing else.

### Verdict
Easiest addition but narrowest scope. Handles user preferences and cross-session
recall only. Recommended as a component, not a replacement for the full stack.

---

## Option 3 — Cognee

### What it is

Cognee is an open-source knowledge engine that ingests data in any format —
documents, code, PDFs, APIs — and builds a knowledge graph combining vector search,
graph databases, and auto-generated ontologies. It supports self-hosting, multi-tenancy
with user/group/session-level isolation, and has a maintained LangGraph integration
package (`cognee-integration-langgraph`). Supports FalkorDB or Neo4j as graph backend.

This is the most ambitious option — it attempts to replace both the RAG pipeline
and the episodic memory in one system.

### ✅ Pros
- Single system for document corpus AND conversation memory — potentially replaces
  Qdrant RAG + Mem0 + episodic SQLite
- Auto-generates knowledge graph from documents — relationships between papers,
  code, and experiments emerge automatically
- Supports 30+ data source connectors
- LangGraph integration is maintained
- Fully self-hostable on DGX

### ❌ Cons
- Heavy reliance on structured LLM output for knowledge graph extraction —
  quantized local models (AWQ INT8) may struggle to perform reliably at this task
- More complex to set up — requires graph DB backend (FalkorDB or Neo4j)
- Younger, less production-proven than Zep or Mem0
- Large corpus indexing at graph extraction quality is compute-intensive —
  initial indexing of all QNOE repos + literature could be very slow
- Risk: if graph extraction quality is poor on Hermes 70B AWQ, the whole
  system degrades

### What it replaces in the current design
Potentially L1 (Qdrant RAG) + L2 (BM25) + L3 (SQLite episodic) + L3.5 (Mem0).
If it works well, it is the closest to a full replacement.

### Verdict
Most powerful if it works well with Hermes 70B INT8. Highest risk. **Recommended
approach: prototype on QTM repos + a handful of PDFs first, test retrieval quality,
then decide.** Do not commit the full corpus without validation.

---

## Option 4 — LangMem

### What it is

LangMem is LangChain's official long-term memory toolkit, built natively into
LangGraph's store. Provides semantic, episodic, and procedural memory types as
JSON documents scoped by configurable namespaces. A background memory manager
automatically extracts and consolidates facts from conversations. Zero extra
infrastructure required.

### ✅ Pros
- Zero extra infrastructure — built into LangGraph
- Simplest possible setup for a LangGraph-native stack
- Namespace partitioning handles per-user/per-team scoping
- Maintained by LangChain with active development

### ❌ Cons
- **p95 latency: 59.82 seconds** on LoCoMo benchmark — not suitable for
  interactive agents responding to researchers in real time
- Entirely coupled to LangGraph — no portability to other frameworks
- No knowledge graph, no relationship modeling
- Does not handle large document corpora
- No published retrieval quality benchmarks

### What it replaces in the current design
Nothing recommended — eliminated by the latency figure for interactive use.

### Verdict
**Eliminated.** Latency is a dealbreaker for a Teams-facing interactive agent.

---

## Comparison table

| | Zep + Graphiti | Mem0 | Cognee | LangMem |
|---|---|---|---|---|
| **Fully local** | ✅ | ✅ | ✅ | ✅ |
| **Large corpus (docs, code, PDFs)** | ❌ | ❌ | ✅ | ❌ |
| **Cross-conversation recall** | ✅ | ✅ | ✅ | ✅ |
| **Semantic + exact-term retrieval** | ✅ | Partial | ✅ | ❌ |
| **Per-user scoping** | ✅ | ✅ | ✅ | ✅ |
| **LangGraph compatible** | ✅ | ✅ | ✅ | ✅ (native) |
| **Temporal reasoning** | ✅ | ❌ | Partial | ❌ |
| **Setup complexity** | Medium | Low | High | Very Low |
| **Replaces Qdrant RAG** | ❌ | ❌ | Potentially | ❌ |
| **Production maturity** | High | High | Medium | ❌ (latency) |

---

## Recommendation

No off-the-shelf solution fully replaces the current design as a single drop-in.
The hard problem is that **no existing tool handles both large technical document
corpora and conversational memory equally well** — which is why the current design
is layered.

**If simplicity is the priority:**
Use Mem0 for user memory + Zep/Graphiti for temporal episodic recall, and accept
that Qdrant RAG still needs to be built for the document corpus. This is a cleaner,
less custom version of the existing design with less code to maintain.

**If you want to attempt a full replacement:**
Prototype Cognee on a subset of the data first (QTM repos + ~20 PDFs). Test
retrieval quality against the 20-question RAG evaluation set. If results are
acceptable on Hermes 70B AWQ, it becomes a viable single-system replacement.
If not, fall back to the layered approach.

**Eliminated outright:** LangMem — p95 latency of 59.82s is incompatible with
an interactive Teams-facing agent.
