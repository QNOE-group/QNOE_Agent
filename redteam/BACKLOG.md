# Red-team findings backlog

The loop's memory: each round's findings → root-cause → fix → re-verify status.
Newest round on top. Probe classes and the historical defects they target live
in `probes.py` and `memory/mistakes.md` (M37–M46).

## Round 0 — harness bring-up (2026-07-13)

- Harness built (`runner.py`, `probes.py`, `graders.py`, `oracle.py`).
- Pending: dry-run (3 probes) to confirm `hermes -z` fidelity + MEM0 isolation,
  then the first full Channel-A battery.

<!-- Template for a finding:
### R<n>-<id> — <one-line defect>
- Probe: <id> (<class>)  · Verdict: FAIL
- Symptom: <what the agent did>
- Root cause: <layer — RAG / hook / SOUL / Mem0 / tool>
- Fix: <commit / SOUL edit / config>  · Re-verify: PASS in R<n+1>
-->
