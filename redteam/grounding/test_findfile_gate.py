"""R11 follow-up regression: the find_file bare-filename gate + extraction.

Tests only the LLM-independent gate/extraction logic in qnoe_rag (no registry,
no Qdrant), so it can run anywhere Python is available (its loader stubs the one
non-stdlib top-level import). The gap it guards: "where is photocurrent_SLG_
240206" (bare stem, no file-noun word, no extension) used to fail the hook gate.
"""
import sys
from _util import load_qnoe_rag

q = load_qnoe_rag()
fails = []


def gate(msg):
    """Replicate the gate decision at the top of _find_file_block (pre-search)."""
    if not msg or not q._FIND_INTENT_RE.search(msg):
        return False
    return bool(q._FILE_NOUN_RE.search(msg) or q._stem_terms(msg))


def check(name, cond):
    print(f"[{'PASS' if cond else 'FAIL'}] {name}")
    if not cond:
        fails.append(name)


# ---- THE GAP: bare filename stem, no noun, no extension, must now fire ----
check("bare stem fires gate (the R11 gap)",
      gate("where is photocurrent_SLG_240206"))
check("bare stem extracted whole (not just the digit run)",
      "photocurrent_SLG_240206" in q._extract_terms("where is photocurrent_SLG_240206"))
check("repo-code stem fires (L208_Opticool)",
      gate("can you locate L208_Opticool for me"))
check("hyphen device id fires (SLG09-C2-PhQH)",
      gate("find SLG09-C2-PhQH"))

# ---- regression: existing triggers still work ----
check("explicit extension still fires", gate("where is the report.pdf"))
check("file-noun still fires", gate("find the spectromag documentation"))
check("stem preferred over trailing digit-run",
      q._extract_terms("locate run_data_240206")[0] == "run_data_240206")

# ---- false-positive guards: must NOT fire ----
check("no intent -> no gate",
      not gate("photocurrent_SLG_240206 was measured yesterday"))
check("date is not a stem (no letter)",
      q._stem_terms("what happened on 2026-07-16") == [])
check("plain hyphenated word is not a stem (no digit)",
      q._stem_terms("where is the back-gate calibration") == [])
check("short code L110 is not a stem",
      "L110" not in q._stem_terms("where is L110 setup"))
check("bare intent, no file, no stem -> no gate",
      not gate("where is the meeting today"))

print()
print("ALL PASS" if not fails else f"FAILURES: {fails}")
sys.exit(1 if fails else 0)
