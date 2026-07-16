"""R11 #2 follow-up regression: run<->sample / run<->params (default-OFF check).

Enables QNOE_GROUNDING_CHECK_SAMPLE_PARAMS for the duration of the test.
Registry-dependent — run on the DGX. Anchored on Tip5Sample9 run 848, whose
row has sample_name "Sample: Grated_Graphene_3L_hBN_Sample9 and Tip: Graphite_5"
and parameters ["gate","g_complex","dc_current"].
"""
import os
import sys

os.environ["QNOE_GROUNDING_CHECK_SAMPLE_PARAMS"] = "1"
from _util import load_grounding_validator  # noqa: E402 — after env set

gv = load_grounding_validator()

TIP5 = "/ICFO/groups/NOE/Setups/L110 QTM/Measurement/2026.05_Tip5Sample9_qcodes/DB.db"
fails = []


def check(name, text, want_missample, want_misparam):
    v = gv.check(text)
    got_s = [t[2] for t in v["missample_runs"]]
    got_p = [t[2] for t in v["misparam_runs"]]
    ok = (bool(got_s) == want_missample) and (bool(got_p) == want_misparam)
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: missample={got_s} misparam={got_p}")
    if not ok:
        fails.append(name)


# 1-2. FP guards — a sample claim is accepted from EITHER the db PATH (folder
#      name) OR the sample_name FIELD (crystal-stack name), which diverge.
check("sample=folder-name (path match, no flag)",
      f"Run 848 on sample Tip5Sample9 ({TIP5}) is a gate sweep.", False, False)
check("sample=field-name (field match, no flag)",
      f"Run 848 ({TIP5}), sample Grated_Graphene_3L_hBN_Sample9. Gate sweep.", False, False)
# 3. TP — fabricated sample in neither source.
check("sample=fabricated (flag)",
      f"Run 848 ({TIP5}) was taken on sample BFNB4_D99.", True, False)
# 4. FP — real channel params ("gate","dc_current" are in the JSON).
check("params=real channels (no flag)",
      f"Run 848 ({TIP5}) swept gate and measured dc_current.", False, False)
# 5. TP — fabricated channel-style param absent from the JSON.
check("params=fabricated channel (flag)",
      f"Run 848 ({TIP5}) recorded lockin_r and stage_position.", False, True)
# 6. FP — physics notation isn't a channel token, so it's skipped (fail-open).
check("params=physics notation (skipped, no flag)",
      f"Run 848 ({TIP5}) swept Vbg (gate voltage) and measured Rxx.", False, False)
# 7. FP — prose 'sample' with a non-distinctive word must not capture.
check("sample=prose 'the' (no flag)",
      f"Run 848 ({TIP5}); the sample was cooled overnight before the sweep.", False, False)

# 8. Toggle OFF -> nothing fires even on a fabricated sample.
os.environ["QNOE_GROUNDING_CHECK_SAMPLE_PARAMS"] = "0"
v = gv.check(f"Run 848 ({TIP5}) on sample BFNB4_D99, recorded fake_chan_x.")
off_ok = not v["missample_runs"] and not v["misparam_runs"]
print(f"[{'PASS' if off_ok else 'FAIL'}] toggle OFF suppresses both: "
      f"missample={v['missample_runs']} misparam={v['misparam_runs']}")
if not off_ok:
    fails.append("toggle-off")
os.environ["QNOE_GROUNDING_CHECK_SAMPLE_PARAMS"] = "1"

# 9. Regression — existing run<->DB misattribution still fires alongside.
v = gv.check("Run 848 in /Measurement/2026.06_Tip6Sample9/DB.db, sample Tip6Sample9.")
reg_ok = bool(v["misattributed_runs"])
print(f"[{'PASS' if reg_ok else 'FAIL'}] regression run<->DB still fires: "
      f"misattr={v['misattributed_runs']}")
if not reg_ok:
    fails.append("regression-misattr")

print()
print("ALL PASS" if not fails else f"FAILURES: {fails}")
sys.exit(1 if fails else 0)
