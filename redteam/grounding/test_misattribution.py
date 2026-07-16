"""R11 #2 misattribution regression: run<->DB (real run, wrong db) + run<->type
(real run in the right db, wrong measurement-type label).

Registry-dependent — run on the DGX. Verifies against the LIVE qcodes_registry:
  Tip5Sample9 run 848 = a real gate_sweep; Tip6Sample9 runs 114-118 exist but
  are IV (not gate-sweeps) and 848 is NOT among Tip6's runs; Tip5 run 735 = a
  real photocurrent run.  See R11_MISATTRIBUTION_PLAN.md.
"""
import sys
from _util import load_grounding_validator

gv = load_grounding_validator()

TIP5 = "/ICFO/groups/NOE/Setups/L110 QTM/Measurement/2026.05_Tip5Sample9_qcodes/DB.db"
TIP6 = "/ICFO/groups/NOE/Setups/L110 QTM/Measurement/2026.06_Tip6Sample9/DB.db"

fails = []


def run(label, text, expect_footer):
    v = gv.check(text)
    footered = bool(gv._footer(v))
    flags = {k: v[k] for k in ("fab_runs", "fab_dbs", "misattributed_runs",
                               "mistyped_runs") if v[k]}
    ok = footered == expect_footer
    print(f"[{'PASS' if ok else 'FAIL'}] {label}: footer={footered} "
          f"want={expect_footer} {flags if flags else ''}")
    if not ok:
        fails.append(label)


# --- true positives ---
run("run<->type: 114-118 mislabeled gate-sweeps (sticky 'same DB')",
    f"Recent gate-sweep runs (most recent first):\n\n"
    f"- Run ID 118 - DB `{TIP6}`\n- Run ID 117 - same DB\n- Run ID 116 - same DB\n"
    f"- Run ID 115 - same DB\n- Run ID 114 - same DB", True)
run("run<->DB: run 848 cited in Tip6 (wrong db)",
    f"Run 848 is a gate sweep stored in `{TIP6}`.", True)

# --- false-positive guards ---
run("FP: run 848 gate-sweep in its real Tip5 db",
    f"The gate-sweep run 848 is in `{TIP5}`.", False)
run("FP: run 735 photocurrent in Tip5 (correct)",
    f"- Run 735 from run card `{TIP5}` (photocurrent measurement).", False)
run("FP: run 118 correctly labelled IV in Tip6",
    f"IV measurements: Run ID 118 in `{TIP6}`.", False)
run("FP: correct denial of run 999999 (denial-context suppression)",
    "The registry contains no run with ID 999999. No such run exists.", False)

# --- regression: original R11 nonexistent-ref checks still fire ---
run("regression: run 75000 + fake qcodes_dbs path",
    "See run 75000 at /opt/qnoe-agent/qcodes_dbs/photocurrent/highbias_blg_2024-07-03.db",
    True)

print()
print("ALL PASS" if not fails else f"FAILURES: {fails}")
sys.exit(1 if fails else 0)
