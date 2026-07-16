#!/usr/bin/env python3
"""SOUL / context-file health check.

Hermes silently drops context content that matches a threat pattern, leaving
only a per-turn WARNING in that profile's agent.log (see memory/mistakes.md
M53: the orchestrator ran ~18h with no SOUL). Two distinct scan surfaces in
core (verified against site-packages 2026-07-16):

1. agent.prompt_builder._scan_context_content — context files loaded into the
   system prompt (SOUL.md, .hermes.md, AGENTS.md, CLAUDE.md, .cursorrules),
   scope="context", WHOLE FILE replaced by a [BLOCKED: ...] placeholder.
   SOUL.md is whitelisted by the QNOE core patch (M53) and can no longer be
   dropped — we still scan it and report `would_match` as an FYI.
   Warning: "Context file <name> blocked: <ids>"

2. tools.memory_tool._sanitize_entries_for_snapshot — persistent memory
   (<profile>/memories/MEMORY.md and USER.md), split into entries on "\\n§\\n",
   each entry scanned at scope="strict" (a SUPERSET of context patterns);
   a matching ENTRY is replaced in the snapshot, the rest of the file loads.
   Warning: "Memory entry from <name> blocked at load time: <ids>"

This check mirrors BOTH surfaces with Hermes' OWN scanner (so it can never
drift from production) and reports anything that would be blocked. Exit code
1 if anything is blocked, 0 if all loads. `--json` emits a machine-readable
summary for the nightly report / context-block tally.

Run: /opt/qnoe-agent/hermes-venv/bin/python3 scripts/soul_health.py
(also works under the agent venv — it locates the hermes-venv scanner itself).
"""
import glob
import json
import os
import sys
from datetime import datetime

HERMES_ROOT = os.environ.get("HERMES_ROOT", "/opt/qnoe-agent/hermes")
HERMES_VENV_SP = os.environ.get(
    "HERMES_VENV_SITE_PACKAGES",
    "/opt/qnoe-agent/hermes-venv/lib/python3.12/site-packages",
)
# Mirror the prompt_builder whitelist (QNOE core patch, mistakes M53): SOUL.md is
# operator-authored and exempt from blocking, so it can never be silently dropped.
EXEMPT = {"SOUL.md"}
# Mirrors tools.memory_tool.ENTRY_DELIMITER (import attempted at runtime below).
ENTRY_DELIMITER = "\n§\n"


def _load_scanner():
    """Return Hermes' real scan_for_threats, importing from hermes-venv if needed."""
    try:
        from tools.threat_patterns import scan_for_threats
    except ImportError:
        if HERMES_VENV_SP not in sys.path:
            sys.path.insert(0, HERMES_VENV_SP)
        from tools.threat_patterns import scan_for_threats
    return scan_for_threats


def _entry_delimiter():
    """Use core's ENTRY_DELIMITER when importable so we can't drift from it."""
    try:
        from tools.memory_tool import ENTRY_DELIMITER as delim
        return delim
    except Exception:
        return ENTRY_DELIMITER


def _offending_lines(text, scan, scope):
    """Best-effort per-line attribution (a cross-line match won't be pinned)."""
    return [i for i, line in enumerate(text.splitlines(), 1) if scan(line, scope)]


def scan_all():
    scan = _load_scanner()
    delim = _entry_delimiter()
    results = []
    for prof_dir in sorted(glob.glob(os.path.join(HERMES_ROOT, "profiles", "*"))):
        if not os.path.isdir(prof_dir):
            continue
        prof = os.path.basename(prof_dir)

        # Surface 1: SOUL.md — context scope, whole-file (exempt via M53 patch).
        soul_path = os.path.join(prof_dir, "SOUL.md")
        if os.path.isfile(soul_path):
            text = open(soul_path, encoding="utf-8", errors="replace").read()
            ids = scan(text, "context")
            entry = {"profile": prof, "file": "SOUL.md", "exempt": True,
                     "scope": "context", "blocked_by": [], "would_match": ids}
            results.append(entry)

        # Surface 2: memories/MEMORY.md + USER.md — strict scope, per-entry.
        for mf in ("MEMORY.md", "USER.md"):
            path = os.path.join(prof_dir, "memories", mf)
            if not os.path.isfile(path):
                continue
            raw = open(path, encoding="utf-8", errors="replace").read()
            entries = [e.strip() for e in raw.split(delim) if e.strip()]
            blocked_entries = []
            all_ids = []
            for i, e in enumerate(entries):
                ids = scan(e, "strict")
                if ids:
                    blocked_entries.append({
                        "index": i, "patterns": ids,
                        "preview": e[:80].replace("\n", " "),
                    })
                    all_ids.extend(x for x in ids if x not in all_ids)
            rec = {"profile": prof, "file": f"memories/{mf}", "exempt": False,
                   "scope": "strict", "entries_total": len(entries),
                   "entries_blocked": blocked_entries,
                   "blocked_by": all_ids, "would_match": []}
            results.append(rec)
    return results


def summary_line(results):
    """One-line status suitable for the nightly report."""
    blocked = [r for r in results if r["blocked_by"]]
    if not blocked:
        fyi = [r for r in results if r.get("would_match")]
        base = f"SOUL health: {len(results)} context files, all load ✅"
        return base + (f" (FYI: {len(fyi)} exempt file(s) contain scanner-trigger text)" if fyi else "")
    parts = []
    for r in blocked:
        n_e = len(r.get("entries_blocked", []))
        what = f"{n_e} entr{'y' if n_e == 1 else 'ies'}" if n_e else "file"
        parts.append(f"{r['profile']}/{r['file']} ({what}: {','.join(r['blocked_by'])})")
    return f"SOUL health: ⚠️ {len(blocked)}/{len(results)} BLOCKED — " + "; ".join(parts)


def main(argv):
    results = scan_all()
    blocked = [r for r in results if r["blocked_by"]]
    if "--json" in argv:
        print(json.dumps({"blocked": blocked, "scanned": len(results),
                          "summary": summary_line(results),
                          "generated_at": datetime.now().isoformat(timespec="seconds")}))
    elif "--line" in argv:
        print(summary_line(results))
    else:
        print(f"SOUL/context-file health: scanned {len(results)} file(s)")
        if not blocked:
            print("ALL CLEAN — every context file loads.")
        else:
            print(f"WARNING: {len(blocked)} file(s) have BLOCKED content "
                  "(dropped from the prompt — those rules/facts are NOT applied):")
            for r in blocked:
                if r.get("entries_blocked"):
                    for be in r["entries_blocked"]:
                        print(f"  - {r['profile']}/{r['file']} entry #{be['index']}: "
                              f"{be['patterns']} — \"{be['preview']}\"")
                else:
                    print(f"  - {r['profile']}/{r['file']}: {r['blocked_by']}")
            print("Fix: reword the offending entry so it stops matching "
                  "tools/threat_patterns.py, then it reloads on the next turn.")
    return 1 if blocked else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
