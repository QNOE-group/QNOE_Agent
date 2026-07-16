# R11 #2 — Misattribution detection (run↔DB + run↔type)

*Plan, 2026-07-16. Extends the R11 grounding validator to catch misattribution of
REAL entities. Not yet executed — tracked in [[TODO]]. See `redteam/BACKLOG.md` R11
(survey-confab round) for the live evidence.*

## Context

The R11 grounding validator (`hermes/plugins/qnoe_rag/grounding_validator.py`, a
`transform_llm_output` hook) catches **nonexistent** references (fake run, fake
`.db`, fake path) but not **misattribution of REAL entities**. Two flavors are
demonstrated live:

- **run↔DB** (R11-round-2): real run cited in the WRONG db. Because `run_id` is
  per-database (composite key `(db_path, run_id)` — run 5 exists in 174 DBs), the
  current `_run_exists(rid)` finds it *somewhere* and passes.
- **run↔type** (`survey-fake-run-in-list`, harness FAIL 2026-07-16): runs 114–118
  listed as "gate-sweeps" in `/…/2026.06_Tip6Sample9/DB.db`. The run↔DB pairing is
  *correct* (those runs are in that DB) — but that DB has **zero** gate-sweeps;
  they're mislabeled. Real gate-sweeps are in Tip5Sample9 (run 848).

**Root cause:** `check()` extracts run ids and db paths in *independent* loops (no
pairing) and checks existence globally. **Fix:** pair each cited run to its cited
db from the reply text, then verify the composite `(db, run)` row and the claimed
measurement-type label against the registry.

**Hard constraint (verified):** the hook is **REPLY-ONLY** — it receives only
`response_text, session_id, model, platform`. The user's question is not passed,
and the on-disk session store is empty / different keyspace, so it's not
recoverable from a plugin. All new signals must come from `response_text` (the
claimed type reliably appears as a header, e.g. "gate-sweep runs:"). A core patch
could forward the user message (the adjacent `post_llm_call` hook already gets it)
but that edits site-packages — out of scope.

## Scope

- **In this plan:** run↔DB check (strict) + run↔type check (advisory) — the two
  demonstrated failures.
- **Deferred (separate TODO items):** `run↔sample/params` (verify claimed
  `sample_name` + specific measured params vs the registry row — same mechanics,
  more extraction/FP surface); and the unrelated `find_file` bare-filename hook gap.

## Design — extend `grounding_validator.check()`

Reuse: `_RUN_ID_RE`, `_ROOTED_PATH_RE`, `_esc`, `_connect_ro`, `_denied`/`_DENIAL_RE`,
`_footer`, `REGISTRY_DBS`. Registry facts: `(db_path, run_id)` is the composite key;
measurement type lives in `run_name` OR `exp_name` free text (NOT swept-param names —
canonical gate sweeps use channel names like `bilt_chan01_v` labelled "Bottom Vg"
with no "gate" substring), so match against `run_name || ' ' || exp_name`.

New helpers (all fail-open on `sqlite3.Error`, mirroring existing style):
- `_pair_runs_to_dbs(text)` → `[(run_id, cited_db, span)]` by same-line / ±120-char
  proximity of a `_RUN_ID_RE` hit to a `_ROOTED_PATH_RE` `.db` hit; + the set of
  UNPAIRED run ids. Many runs on one line → all pair to that line's db.
- `_run_in_db(run_id, db_tail)` → `(db_exists, run_in_db)` via
  `SELECT 1 FROM qcodes_registry WHERE db_path LIKE ?%tail%` and `… AND run_id=?`.
  **Require a distinctive tail** (≥1 parent dir + basename; bare `DB.db` is not) —
  else return `(True, True)` (fail-open, don't flag).
- `_row_type_text(run_id, db_tail)` → `lower(run_name+' '+exp_name)` of the paired row, or None.
- `_claimed_type(text, near_span)` → scan a small keyword/synonym map for a
  measurement-type header adjacent to the run: `gate|vg|back-gate` → {`gate`,`vg`};
  `iv|i-v|bias sweep` → {`iv`,`bias`}; `photocurrent` → {`photocurrent`,`pc`};
  `temperature|temp sweep` → {`temp`}. Returns the needle set or None (unknown →
  None, fail-open, no flag).

`check()` new flow (added to the existing run/db/path passes):
1. Pair runs↔dbs.
2. Per pair `(run, cited_db)`:
   - **run↔DB:** if `db_exists and not run_in_db` → `misattributed_runs += (run, cited_db)`. **STRICT.**
   - **run↔type** (only if `QNOE_GROUNDING_CHECK_TYPE` on, and `run_in_db`): if
     `_claimed_type` present near the run AND none of its needles occur in
     `_row_type_text` → `mistyped_runs += (run, cited_db, claimed, actual_run_name)`. **ADVISORY.**
3. UNPAIRED runs → existing `_run_exists` (unchanged; weaker, no new FPs).
4. Drop any flagged item whose span is in `_denied` context.
5. Extend `_footer`:
   - misattributed → "run 118 does not appear in the database you cited (…/Tip6Sample9/DB.db)"
   - mistyped → "run 118 in …/Tip6Sample9/DB.db is not a gate-sweep"
6. Existing `fab_runs`/`fab_dbs`/`unver_paths` untouched.

Toggles: `QNOE_GROUNDING_VALIDATE` (existing) + `QNOE_GROUNDING_CHECK_TYPE` (new,
default on — the advisory run↔type check, so it can be silenced if noisy).

## Files

| Action | Path | What |
|---|---|---|
| MOD | `hermes/plugins/qnoe_rag/grounding_validator.py` | pairing pass + `_pair_runs_to_dbs`/`_run_in_db`/`_row_type_text`/`_claimed_type`; extend `check()` + `_footer`; `QNOE_GROUNDING_CHECK_TYPE` |
| MOD | `redteam/probes.py` | add a `survey-misattribution` probe (run↔DB flavor, deterministic combo grader on a known fabricated pairing); make `survey-fake-run-in-list`'s expected outcome (footer on mislabel) explicit |

Single deployed copy of `qnoe_rag` (`hermes/plugins/`, no site-packages shadow);
restart `qnoe-hermes-sandbox.service` so `register()` re-runs.

## Verification

1. **Unit (offline, on DGX, against the real registry):**
   - run↔DB: "runs 735 in `/…/Tip5Sample9_qcodes/DB.db`" → FLAG (735 not in Tip5Sample9). *R11-round-2 repro.*
   - run↔type: "gate-sweep runs: run 114…118 in `/…/Tip6Sample9/DB.db`" → FLAG mistyped. *survey-fake-run repro.*
   - **FP guards (must NOT flag):** run 848 in its real Tip5Sample9 DB labelled `gate_sweep`; a correct list of real gate-sweeps in their real DB; a run correctly paired to its db; a non-distinctive bare `DB.db` tail (fail-open); a `_denied` self-correction.
2. **Regression:** existing R11 cases still fire (nonexistent run 75000, fake `qcodes_dbs` path); clean run-848 answer still no footer.
3. **Live:** `run.sh --class survey-confab` ×3 → `survey-fake-run-in-list` now carries the ⚠️ footer (or the model abstains); `survey-real-baseline` stays clean.

## Risks & mitigations

- **run↔type is heuristic** (synonyms, exp_name-vs-run_name, channel-named gate
  sweeps). → advisory + `QNOE_GROUNDING_CHECK_TYPE` toggle + flag only on a clear
  adjacent header AND a clear text contradiction + fail-open + real-baseline probe guards regression.
- **Pairing fragility** (truncated bare `DB.db`, prose separation). → require a
  distinctive tail; unpaired runs keep the old weak existence check (no new FPs); fail-open.
- **Rollback:** `QNOE_GROUNDING_CHECK_TYPE=0` (advisory off) / `QNOE_GROUNDING_VALIDATE=0`
  (whole validator) — instant, no redeploy; or revert the file.

## Effort

~0.5–1 day: pairing + two checks + footer, offline unit tests against the live
registry, one probe, deploy + live verify.
