# Red-team harness — QNOE Lab Agent

Adversarial probe loop that drives trap questions at the live agent, grades
against ground truth, and surfaces design defects (the M38/M44/M45/M46 classes)
as a **repeatable process** instead of by luck. Plan:
`~/.claude/plans/lexical-munching-book.md`.

## Two channels

- **Channel A — self-driven (`hermes -z`).** `runner.py` runs full agent turns
  headless and grades them. Covers confabulation, attribution, grounding,
  tool-selection, permission/refusal, injection, calibration.
- **Channel B — Teams relay.** Claude hands numbered cards; a human relays into
  Teams; Claude triages the live per-profile `logs/agent.log`. Covers Mem0
  recall/isolation/poisoning, routing, formatting — the things that need a real
  gateway `user_id` (`hermes -z` has none; `qnoe_rag` ignores `MEM0_USER_ID`).

## Run it (Channel A)

MUST run as `qnoe-ai` — the profile home is mode 700:

```bash
sudo -u qnoe-ai bash /opt/qnoe-agent/redteam/run.sh --dry-run   # 3-probe plumbing check
sudo -u qnoe-ai bash /opt/qnoe-agent/redteam/run.sh             # full channel-A bank
sudo -u qnoe-ai bash /opt/qnoe-agent/redteam/run.sh --class confabulation
sudo -u qnoe-ai bash /opt/qnoe-agent/redteam/run.sh --list
```

Report lands in `reports/redteam_<ts>.md` (+ `.json`). Read it with `sudo cat`.

## Isolation guarantees

- `MEM0_ENABLED=0` → zero writes to the live `episodic_memory` Qdrant
  collection. The runner records the collection's point count before/after and
  flags any change.
- Throwaway `HERMES_HOME` under `homes/<profile>/` whose config/SOUL/plugins/
  `.env` are **symlinks** to the live profile (full parity), but whose
  `state.db` + `logs/` are local — no SQLite lock contention with the running
  gateway, no session pollution of the live profile.
- Injection payloads are confined to `/opt/qnoe-agent/repos/_redteam/`, planted
  and deleted within the single probe that uses them.

## Caveat — Channel A log triage

`hermes -z` calls `logging.disable(CRITICAL)`, so the `prefetch inject:` INFO
line is usually **not** emitted in Channel A. The answer + oracle verdict is the
primary signal; for deep per-turn triage (`rag_chars=0`, `mem_facts=0
session=''`, `qcodes_block=…`) use Channel B, where the live gateway logs INFO.

## Files

- `runner.py` — driver + report writer.
- `probes.py` — the probe bank (`PROBES`, `DRY_RUN_IDS`).
- `graders.py` — deterministic graders (combo / refusal / manual→REVIEW).
- `oracle.py` — ground truth via the live `qnoe_qcodes` registry helpers.
- `BACKLOG.md` — findings → fix → re-verify log (the loop's memory).
- `homes/`, `reports/` — runtime, git-ignored.

## Deploy

Standard pattern (source lives in the repo under `redteam/`):
```bash
scp -r redteam yzamir@dgx:/tmp/redteam_src
ssh dgx "sudo cp -r /tmp/redteam_src/* /opt/qnoe-agent/redteam/ && \
         sudo chown -R qnoe-ai:qnoe-ai /opt/qnoe-agent/redteam"
```

## Adding probes

Append to `PROBES` in `probes.py`: `{id, cls, profile, channel, prompt, grader,
why[, inject]}`. Prefer `combo`/`refusal` graders with ground truth you can
verify from `oracle.py`; use `manual` (→ REVIEW) only for nuance that substring
matching can't score.
