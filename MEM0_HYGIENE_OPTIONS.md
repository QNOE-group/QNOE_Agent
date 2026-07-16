# Mem0 Provenance + Audit + Extraction-Hygiene — Options Menu

*Created: 2026-07-16. Source task: TODO.md 🔴 HIGH "Mem0 provenance + audit + EXTRACTION-HYGIENE tooling".*

> Related: [[MEM0_INTEGRATION]] · [[memory/mistakes#M47]] · [[memory/mistakes#M55]] · [[memory/decisions#D13]]

---

## The task and why it exists

The TODO item asks for four things: **(a)** tighten what Mem0 extracts so only durable interests/context get stored, **(b)** tag each stored fact with provenance, **(c)** a periodic audit that flags suspicious facts and oracle-checks lab claims against the QCoDeS registry, and **(d)** an ops script to dump/purge by filter. Explicit constraint: **keep the "the memory says…" attribution framing the user likes** — fix what's *stored*, not how it's cited.

It exists because of two incidents documented in `memory/mistakes.md`:

- **M47 (2026-07-14, poisoning):** ~43 assistant confabulations (fake runs, wrong physics, a nonexistent `.db`) had been distilled into Mem0 as user "facts" and were overriding correct tool answers in live Teams turns. Because nothing distinguished assistant-derived facts from genuine preferences, the only safe remedy was a **full wipe of the user's 51 facts** — nuclear, not surgical.
- **M55 (2026-07-16, hygiene):** even after the M46/M47 fixes (user-messages-only writes in `qnoe_rag.sync_turn`, SOUL "memory is not a data source" guard), the extraction itself stores **one-off queries as facts** — 14 of Yuval's 16 facts were interaction logs like "User asked about run 999999", which the model then wove back into answers as "memory". Purged manually via a throwaway script (`/tmp/purge_querylogs.py`).

The pattern: every fix so far guarded memory *usage* or the *input side* of writes; nothing controls what the extraction LLM decides to keep, nothing records where a fact came from, and cleanup is always a manual dump-and-read exercise.

---

## Alternatives

These map to different layers (write-time prevention, storage metadata, read-time detection), so they're partly complementary rather than mutually exclusive.

### Option 1 — Custom Mem0 extraction prompt (native knob)

Mem0 OSS supports a `custom_fact_extraction_prompt` config key — replace the default with one that extracts *only* durable preferences/context (sample names, projects, tool preferences) and explicitly returns nothing for questions, requests, and one-off lookups.

- **Pros:** attacks the root cause at write time; a config-only change to `MEM0_CONFIG` — no code fork, Mem0 keeps owning dedup/update logic (consistent with D13's "no custom memory system"); zero added per-turn cost.
- **Cons:** still LLM-judged — gpt-oss-120b at `reasoning_effort:low` may misclassify, so it reduces rather than eliminates junk; must verify the key exists and behaves in the pinned mem0ai 2.0.11 (the 2.x API has drifted before, see MEM0_INTEGRATION.md §11); prompt must be re-validated on every mem0 upgrade; does nothing for provenance or already-stored junk. (M53 habit: any new instruction text with trigger-ish phrasing gets a scan-check — this prompt lives outside Hermes' scanner, but keep the habit.)

### Option 2 — Pre-write gate in `sync_turn` (our code, before `add()` is called)

In the plugin, classify the user message before calling `_get_mem0().add()`: a deterministic heuristic (skip pure questions/requests — "where is", "find", "what were the parameters of", run-id patterns), optionally backed by a one-token LLM yes/no ("does this contain a durable preference or personal context?"). Only matched turns reach Mem0.

- **Pros:** fully in code we own (`qnoe_rag` is already the single hook point), immune to mem0 upgrades; the deterministic tier is exactly the pattern that has worked repeatedly in this project (the run-id and find_file prefetch hooks were built *because* prompting the model was ~80% unreliable); skipped turns also skip the extraction LLM call entirely — saves inference; kills the M55 query-log class at the source.
- **Cons:** heuristics have false negatives (a preference phrased as a question — "can you always answer in bullet points?" — gets dropped) and need list maintenance; the LLM-gate variant adds a call per turn and reintroduces nondeterminism; still no provenance and no defense against future extraction drift for messages that pass the gate.

### Option 3 — Provenance metadata + read-side filtering

Tag every `add()` with metadata: `source` (user-stated vs assistant-distilled), timestamp, session, and the verbatim source message. Prefetch can then filter or render provenance, and purges become surgical (`qdrant delete` by metadata filter) instead of per-user wipes.

- **Pros:** makes both M47-style and M55-style cleanups surgical forever after — the "nuclear wipe was the only remedy" problem disappears; directly supports the attribution framing the user wants to keep; cheap (metadata dict on an existing call); makes the Option 4 audit actionable.
- **Cons:** prevents nothing — junk is still stored, just labeled; Mem0's internal ADD/UPDATE/DELETE consolidation may merge facts, and it's unverified how faithfully metadata survives an UPDATE (needs a test); existing facts have no tags (small problem today — the store is 2 facts post-purge).

### Option 4 — Periodic audit job with oracle-checking (nightly standing check)

A nightly task in the pattern already established twice (soul_health, context-block tally): dump each user's `episodic_memory`, classify facts (query-log / declarative-lab-claim / genuine preference), oracle-check any run/db/param assertion against the QCoDeS registry, and emit a suspects list into the nightly report; pair with the ops dump/purge script (productionize `/tmp/purge_querylogs.py`).

- **Pros:** catches everything *regardless of how it got in* — extraction drift, mem0 upgrades, a future poisoning class nobody's imagined — which no write-time fix can claim; fits the existing nightly-report + JSONL + "stale monitor = FAILURE" infrastructure exactly; read-only detection, so deployment risk is near zero; delivers TODO parts (c) and (d) directly.
- **Cons:** reactive — a bad fact lives (and can corrupt answers) until the next audit, and M47 proved an injected memory fact overrides tool-use rules in the meantime; classification needs the LLM, so it depends on llama.cpp being up at audit time; another cron/report surface to maintain; must be tuned not to false-flag the genuine facts.

### Option 5 — Drop automatic extraction entirely: explicit memory only

Disable distillation and store facts only on explicit user request ("remember that my sample is X" → `add(infer=False)` verbatim), possibly with the agent offering to remember things.

- **Pros:** zero junk *by construction* — the whole problem class (M46, M47, M55) becomes impossible; perfect provenance for free (every fact is user-authored, verbatim); no extraction LLM cost; trivially auditable. The evidence mildly supports it: after purging, passive extraction had yielded only **2** durable facts — automatic distillation is producing almost no value to protect.
- **Cons:** loses passive memory — lab users won't remember to teach the bot, so the store may stay nearly empty; departs from D13's "Mem0 owns the hard logic" design; loses Mem0's dedup/update of evolving facts; a UX/behavior change other users would need to learn; arguably over-rotation for a problem that manual purges have so far contained.

---

## Recommendation

The TODO's four sub-items already sketch the right answer: this is a layered problem, not a pick-one. The strongest combination is **Option 2 (deterministic gate, with Option 1's prompt as a second filter behind it) + Option 3 (provenance metadata) + Option 4 (nightly audit + purge tooling)** — prevention, traceability, and a standing safety net, each independently deployable and revertable.

Minimum-effort first step: **Option 3 + the purge script** — the cheapest change that permanently ends the "wipe everything" failure mode, and it makes whichever write-side fix comes later measurable (the audit can tell you whether the gate is actually working).

**Fallback:** Option 5, if after a few weeks the gated pipeline still fills the store with noise — at 2 genuine facts, there is little passive-extraction value to lose.

---

*Status: options menu only — no decision taken, nothing deployed.*
