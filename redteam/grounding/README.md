# Grounding-validator regression tests (redteam R11 / R11 #2)

Deterministic unit tests for `hermes/plugins/qnoe_rag/grounding_validator.py`
(and the `qnoe_rag` find_file gate). They assert the exact behaviour behind the
R11 grounding hardening: fabrication flagging, run↔DB / run↔type misattribution,
run↔sample / run↔params, and the find_file bare-filename gate.

**No LLM needed** — pure code + SQLite. They are the reproducible replacement for
the throwaway `/tmp` scripts used during development.

## What each file covers

| File | Checks | Registry needed? |
|---|---|---|
| `test_misattribution.py` | run↔DB (wrong db) + run↔type (mislabeled) + denial suppression + nonexistent-ref regression | **yes** (live `qcodes_registry`) |
| `test_sample_params.py` | run↔sample / run↔params (default-OFF check; enabled in-test) + FP guards | **yes** |
| `test_findfile_gate.py` | find_file bare-stem gate + whole-stem extraction + FP guards | no (stdlib only) |
| `test_memory_gate.py` | Mem0 write-gate classifier — keep personal/first-party, drop lab-records/query-logs/third-party (calibrated to real Mem0 phrasing) | no (stdlib only) |

The registry tests are anchored on real QTM rows (Tip5Sample9 run 848 = a
gate-sweep; Tip6Sample9 runs 114–118 = IV, and 848 is not among them; Tip5 run
735 = photocurrent). They must run where the SQLite files in
`grounding_validator.REGISTRY_DBS` exist — i.e. **on the DGX**.

## Running

On the DGX, against the **deployed** plugin (`/opt/qnoe-agent/…`):

```bash
cd /opt/qnoe-agent/redteam/grounding
for t in test_*.py; do echo "== $t =="; python3 "$t"; done
```

Against **un-deployed edits** staged in a scratch dir (test before `sudo cp` to
/opt): copy `grounding_validator.py` + `__init__.py` into the dir and point at it:

```bash
QNOE_PLUGIN_DIR=/tmp/gvtest python3 /tmp/gvtest/test_misattribution.py
```

Resolution order for the code under test: `$QNOE_PLUGIN_DIR` → repo layout
(`../../hermes/plugins/qnoe_rag`) → `/opt/qnoe-agent/hermes/plugins/qnoe_rag`.

Each script prints `[PASS]`/`[FAIL]` per case and exits non-zero on any failure.
