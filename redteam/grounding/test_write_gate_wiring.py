"""Regression test for the Mem0 write-gate WIRING in qnoe_rag.__init__
(_apply_write_gate — MEMORY_ARCHITECTURE Part 6 item 2, wired 2026-07-20).

The classifier itself is covered by test_memory_gate.py (29/29); this file
tests the glue: ADD events are classified and dropped facts deleted, UPDATE/
DELETE events are audit-logged but never deleted, malformed results don't
crash the writer thread, and the env toggle defaults OFF.

Pure stdlib — stubs mem0 via a fake, no registry/LLM needed.
"""
import sys
from _util import load_qnoe_rag

mod = load_qnoe_rag()
fails = []


class FakeMem0:
    def __init__(self):
        self.deleted = []

    def delete(self, mem_id):
        self.deleted.append(mem_id)


def run_case(name, add_result, want_deleted):
    fake = FakeMem0()
    mod._get_mem0 = lambda: fake          # bypass the lru_cached real init
    try:
        mod._apply_write_gate(add_result, uid="test-user")
    except Exception as e:  # the writer thread must never blow up
        print(f"[FAIL] {name}: raised {type(e).__name__}: {e}")
        fails.append(name)
        return
    ok = fake.deleted == want_deleted
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: deleted={fake.deleted} "
          f"want={want_deleted}")
    if not ok:
        fails.append(name)


# 1) ADD of a lab query-log -> deleted (M55 class)
run_case(
    "ADD lab-query-log dropped",
    {"results": [{"id": "m1", "event": "ADD",
                  "memory": "User requested to locate the file "
                            "photocurrent_SLG_240206.pptx"}]},
    want_deleted=["m1"],
)

# 2) ADD of a genuine personalization fact -> kept
run_case(
    "ADD personal fact kept",
    {"results": [{"id": "m2", "event": "ADD",
                  "memory": "Prefers answers in bullet points"}]},
    want_deleted=[],
)

# 3) Mixed batch: record dropped, preference kept, third-party dropped
run_case(
    "mixed batch",
    {"results": [
        {"id": "m3", "event": "ADD",
         "memory": "Run 848 is a gate sweep measurement in Tip5Sample9"},
        {"id": "m4", "event": "ADD", "memory": "Name is Yuval"},
        {"id": "m5", "event": "ADD",
         "memory": "Sergi's cooldown data shows a transition at 4K"},
    ]},
    want_deleted=["m3", "m5"],
)

# 4) UPDATE with droppable text -> audit only, never deleted
run_case(
    "UPDATE never deleted",
    {"results": [{"id": "m6", "event": "UPDATE",
                  "memory": "User requested to locate run 999999"}]},
    want_deleted=[],
)

# 5) DELETE event -> audit only
run_case(
    "DELETE event audit only",
    {"results": [{"id": "m7", "event": "DELETE", "memory": "old fact"}]},
    want_deleted=[],
)

# 6) Malformed shapes -> no crash, no delete
run_case("None result", None, want_deleted=[])
run_case("list result (version drift)", [{"id": "x"}], want_deleted=[])
run_case("empty results", {"results": []}, want_deleted=[])
run_case("ADD with no id", {"results": [{"event": "ADD",
                                         "memory": "User asked about run 42 "
                                                   "measurement data"}]},
         want_deleted=[])

# 7) Env toggle defaults OFF (this process never set MEM0_WRITE_GATE)
ok = mod.MEM0_WRITE_GATE is False
print(f"[{'PASS' if ok else 'FAIL'}] MEM0_WRITE_GATE default OFF")
if not ok:
    fails.append("default-off")

print(f"\n{'ALL PASS' if not fails else 'FAILURES: ' + ', '.join(fails)}")
sys.exit(1 if fails else 0)
