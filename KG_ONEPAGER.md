# QNOE Group Knowledge Graph
### A research-aware memory layer for the lab's AI assistant

**What it is.** A structured map of the group's research — the concepts and phenomena we study, the open questions we pursue, the techniques and setups we use, the projects and people — all connected to the actual measurement record. It lets the lab's AI assistant reason about *how the group's science fits together*, rather than just searching documents.

**Why it matters.** Today the assistant retrieves passages of text. The knowledge graph lets it answer connective, multi-step questions — *"which experiments probed the twist-angle dependence, on what setup, and what did we find?"* — and it acts as an authoritative reference that keeps the assistant's answers grounded and honest.

---

**Technology.** Built on **Cognee** (open-source). It runs **entirely on-premises on the group's DGX — no data leaves the lab.** It reuses our existing infrastructure: the local language model (gpt-oss-120b) reads the documents, our current search index supplies the text, and the graph itself lives in an on-disk graph database.

**Structure — two tiers.** The graph keeps two kinds of knowledge deliberately separate:

- **Facts (exact).** *Samples, experiments, measurement runs, setups, people* — loaded automatically and exactly from the measurement database. This is ground truth.
- **Research (inferred).** *Materials, concepts, phenomena, techniques, physical quantities, research questions, projects, findings, publications* — read by the AI from our papers, proposals and notes.

The two tiers connect through the **experiment** — a *person*, on a *setup*, with a *sample* — which ties every measurement to the research it serves. For example: a *project* studies a *phenomenon* using a *technique* that runs on a *setup*; the *experiment* that tests it contains the individual *runs* on a specific *sample* and *material*.

**How it is used.** During a conversation the assistant consults the graph and injects the relevant connected context into its reasoning. The factual tier also serves as a reference the assistant checks its own claims against before answering.

**How it stays current.** Automatically and continuously. As new measurements and documents arrive, the graph updates overnight — no manual curation. The measurement tier stays in exact sync with the database; new papers and notes are folded in as they appear.

**Safeguard against invented knowledge.** The factual tier is exact by construction. The research tier is AI-inferred, so every concept and relationship **keeps a link to the source document it came from**, is validated before it is trusted, and is **never presented as established fact without that provenance.** This directly guards against the assistant "confabulating" knowledge — the central risk of any AI memory.

**Status.** Designed and specified. The next step is a focused pilot on the QTM material to validate the quality of the inferred research graph before the full rollout.
