# MVP_VERIFICATION_PLAN — the 4 untested acceptance criteria

*Written: 2026-07-10 · Closes: [[AGENT_FRAMEWORK]] §9.4 criteria #1, #3, #7, #8 → MVP-1 declaration.*
*Criteria #5/#6/#10 are deferred to [[PHASE2_BACKLOG]] B8/B9/B10 (user decision 2026-07-10). #2/#4/#9 already
verified — see [[SETUP_LOG]] 2026-07-10.*

Estimated total effort: ~30 min of Claude-side setup + ~15 min of human Teams messages (two people).

---

## T1 — Routing (criterion #1): photocurrent mapping + orchestrator default

**Today:** both mapped users → `qnoe-qtm`; `default: qnoe-orchestrator` never exercised.

1. **[User] Pick the photocurrent tester** — any photocurrent sub-team member willing to send 3 Teams messages
   (their Azure AD id is captured automatically in step 2).
2. **[User→Claude] Tester DMs the bot anything** (they'll get an orchestrator-flavoured reply — that message IS
   the orchestrator-default test, part two of this criterion). **[Claude]** reads the gateway log
   (`inbound message: … user=<Name>`), extracts the Azure AD id, adds
   `"<id>": qnoe-photocurrent  # <Name>` to `hermes/config/user_profiles.yaml` (deploy via `/tmp` + `sudo cp`),
   restarts `qnoe-hermes.service`, and mirrors the change to the repo.
3. **[User] Tester asks:** *"Which sub-team do you support and what tools do you have?"*
   **Pass:** reply identifies as **Photocurrent-Agent** (photocurrent SOUL persona), no skill tools listed.
   **[Claude] verifies** in `qnoe-photocurrent/logs/agent.log`: session initialized for that user, tool_search
   `7 kept / 3 deferred`.
4. **Pass condition for #1 overall:** step 2's pre-mapping reply came from the orchestrator persona AND step 3's
   reply comes from Photocurrent-Agent. *(Bonus, re-verifies #9 cross-profile: Yuval sends a QTM question while
   the tester's photocurrent question is in flight — both answered, no persona/memory bleed.)*

## T2 — RAG-paper with citation (criterion #3)

1. **[User or tester] Ask the photocurrent profile:** *"How is the photothermoelectric effect distinguished from
   the photovoltaic effect in our graphene devices? Cite the source."*
   (Known-good corpus coverage: Krystian's thesis Ch_1_2 — eval Q8 retrieved it with score margin.)
2. **Pass:** answer describes gate-dependence/sign-change discrimination AND cites a concrete source path or
   document name from the corpus (per the SOUL citation style + grounding rules). General-literature additions
   must be labeled as such (D16).
3. **[Claude] verifies** the injection log line (`rag_chars>0`) and that the cited path exists in the corpus.

## T3 — `/switch` (criterion #7) — RESOLVED by inspection 2026-07-10

**Finding:** `/switch` does not exist in the Hermes gateway (available: `/new`, `/help`, `/model`, `/resume`,
`/undo`, `/command`, …). The SOULs' "Type /switch" instructions were LangGraph-era fiction — a confabulation trap
(the agent told a user to type it on 2026-07-10). Under Hermes, users are routed to their sub-team profile
automatically, so *switching is obsolete by architecture*: criterion #7 is **recast** as "off-topic questions get
an honest group-wide answer naming the right sub-team; no phantom commands." **Fix shipped:** all 3 SOULs
cleaned — /switch removed, off-topic behaviour rewritten, dead /help//new instruction text removed (the gateway
intercepts slash commands before the model sees them), orchestrator no longer claims `delegate_task` (disabled;
B10). **[User] residual test:** ask the QTM agent an off-topic (e.g. superconductivity) question — pass = honest
group-wide answer + names the sub-team, no "/switch" mention.

## T4 — `/help` (criterion #8) — recast after inspection

**Finding:** the gateway intercepts `/help` and returns its own command list — the model never sees it, so the
original "sub-team-specific /help" is unimplementable at the SOUL level. Recast as two checks:
1. **[User]** send `/help` — pass = accurate platform command list (no `/switch` in it, no error).
2. **[User]** ask *"what can you do?"* — pass = concise sub-team-specific capability list (now an explicit SOUL
   instruction; one example per item, under 10 lines).

---

## Evidence & declaration

For each test, **[Claude]** records pass/fail + the log excerpt in [[SETUP_LOG]] under a dated
"MVP-1 verification" section, ticks §9.4, and writes the **MVP-1 declaration** into [[SETUP_LOG]] + [[HOME]]
(active workstream → "MVP-1 declared, Phase 2 planning"). Remaining standing re-tests (run-159 → 49,
gate-sweep → run 848, colleague Mem0 isolation, I9 find_file) ride along in the same Teams session — they are
not MVP gates but should be captured in the same evidence section.

**Declaration collateral (after passes):** update the PPTX Gantt phase order before presenting to Frank
(CLAUDE.md open item).
