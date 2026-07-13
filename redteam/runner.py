#!/usr/bin/env python3
"""Red-team harness runner (Channel A — self-driven `hermes -z`).

MUST run as qnoe-ai (profile home is mode 700):
    sudo -u qnoe-ai bash /opt/qnoe-agent/redteam/run.sh [--dry-run] [--class C] [--profile P] [--list]

Per probe it: (1) builds a throwaway HERMES_HOME whose config/SOUL/plugins/.env
are SYMLINKS to the live profile (full parity) but whose state.db + logs are
local (no lock contention with the live gateway, no session pollution);
(2) plants any injection file; (3) runs one full agent turn with MEM0_ENABLED=0
(no writes to the live episodic_memory collection); (4) captures the answer,
grades it, and (5) cleans up. Writes a markdown + JSON report.

Note: `hermes -z` calls logging.disable(CRITICAL), so INFO log lines (the
`prefetch inject:` triage line) are usually suppressed in Channel A — the
answer + oracle verdict is the primary signal here; deep log triage lives on
Channel B (Teams). See README.md.
"""
from __future__ import annotations
import argparse
import json
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import graders  # noqa: E402
import oracle   # noqa: E402
from probes import PROBES, DRY_RUN_IDS  # noqa: E402

HERMES = "/opt/qnoe-agent/hermes-venv/bin/hermes"
LIVE_PROFILES = "/opt/qnoe-agent/hermes/profiles"
HOMES = os.path.join(HERE, "homes")
REPORTS = os.path.join(HERE, "reports")
TOOLSETS = "file,terminal,clarify,qnoe-lab"
QDRANT = os.environ.get("QDRANT_URL", "http://localhost:6333")
LINK_ENTRIES = ["config.yaml", "SOUL.md", ".env", "plugins", "memories",
                "USER.md", "AGENTS.md", ".managed"]
PROBE_TIMEOUT = 300


def _throwaway_home(profile: str) -> str:
    live = os.path.join(LIVE_PROFILES, profile)
    home = os.path.join(HOMES, profile)
    shutil.rmtree(home, ignore_errors=True)
    os.makedirs(os.path.join(home, "logs"), exist_ok=True)
    for entry in LINK_ENTRIES:
        src = os.path.join(live, entry)
        if os.path.exists(src) or os.path.islink(src):
            try:
                os.symlink(src, os.path.join(home, entry))
            except OSError:
                pass
    return home


def _plant(inject: dict) -> None:
    path = inject["file"]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(inject["payload"])


def _unplant(inject: dict) -> None:
    d = os.path.dirname(inject["file"])
    shutil.rmtree(d, ignore_errors=True)


def _episodic_count() -> int:
    try:
        out = subprocess.run(
            ["curl", "-s", f"{QDRANT}/collections/episodic_memory"],
            capture_output=True, text=True, timeout=10).stdout
        return json.loads(out)["result"]["points_count"]
    except Exception:
        return -1


def _run_one(probe: dict) -> dict:
    profile = probe["profile"]
    home = _throwaway_home(profile)
    inject = probe.get("inject")
    if inject:
        _plant(inject)
    env = dict(os.environ, HERMES_HOME=home, MEM0_ENABLED="0")
    rec = {"id": probe["id"], "cls": probe["cls"], "profile": profile,
           "prompt": probe["prompt"], "why": probe["why"]}
    try:
        t0 = time.time()
        p = subprocess.run(
            [HERMES, "-z", probe["prompt"], "--toolsets", TOOLSETS],
            env=env, capture_output=True, text=True, timeout=PROBE_TIMEOUT)
        rec["wall"] = round(time.time() - t0, 1)
        rec["answer"] = (p.stdout or "").strip()
        rec["stderr_tail"] = (p.stderr or "").strip()[-600:]
        rec["rc"] = p.returncode
    except subprocess.TimeoutExpired:
        rec["answer"] = ""
        rec["stderr_tail"] = f"TIMEOUT after {PROBE_TIMEOUT}s"
        rec["rc"] = -1
        rec["wall"] = PROBE_TIMEOUT
    finally:
        if inject:
            _unplant(inject)
    # best-effort triage line (often empty under -z logging.disable)
    logf = os.path.join(home, "logs", "agent.log")
    rec["inject_log"] = ""
    if os.path.exists(logf):
        for line in open(logf, errors="ignore"):
            if "prefetch inject" in line:
                rec["inject_log"] = line.strip()
    verdict, note = graders.grade(probe["grader"], rec["answer"])
    rec["verdict"], rec["note"] = verdict, note
    return rec


def _select(args):
    ids = set(DRY_RUN_IDS) if args.dry_run else None
    out = []
    for p in PROBES:
        if p["channel"] != "A":
            continue
        if ids is not None and p["id"] not in ids:
            continue
        if args.cls and p["cls"] != args.cls:
            continue
        if args.profile and p["profile"] != args.profile:
            continue
        out.append(p)
    return out


def _write_report(results, meta):
    os.makedirs(REPORTS, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    base = os.path.join(REPORTS, f"redteam_{stamp}")
    with open(base + ".json", "w") as f:
        json.dump({"meta": meta, "results": results}, f, indent=2)
    rollup = {}
    for r in results:
        rollup.setdefault(r["verdict"], 0)
        rollup[r["verdict"]] += 1
    lines = [f"# Red-team report — {stamp}", ""]
    lines.append(f"Probes: {len(results)} · "
                 + " · ".join(f"{k}={v}" for k, v in sorted(rollup.items())))
    lines.append(f"Isolation (episodic_memory points): before={meta['mem_before']} "
                 f"after={meta['mem_after']} "
                 f"({'OK, unchanged' if meta['mem_before'] == meta['mem_after'] else 'CHANGED — investigate'})")
    lines.append("")
    for r in results:
        lines.append(f"## [{r['verdict']}] {r['id']}  ({r['cls']} / {r['profile']}, {r.get('wall')}s)")
        lines.append(f"*Targets:* {r['why']}")
        lines.append(f"*Grader:* {r['note']}")
        lines.append(f"*Prompt:* {r['prompt']}")
        if r.get("inject_log"):
            lines.append(f"*Triage:* `{r['inject_log']}`")
        ans = r["answer"] or "(empty stdout)"
        if len(ans) > 1800:
            ans = ans[:1800] + "\n…(truncated)…"
        lines.append("*Answer:*\n\n```\n" + ans + "\n```")
        if r.get("stderr_tail") and not r["answer"]:
            lines.append("*stderr:*\n\n```\n" + r["stderr_tail"] + "\n```")
        lines.append("")
    with open(base + ".md", "w") as f:
        f.write("\n".join(lines))
    return base + ".md"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="run only the 3 dry-run probes")
    ap.add_argument("--class", dest="cls", default=None)
    ap.add_argument("--profile", default=None)
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()

    probes = _select(args)
    if args.list:
        for p in probes:
            print(f"{p['id']:24} {p['cls']:14} {p['profile']}")
        print(f"\n{len(probes)} channel-A probes selected")
        return

    print(f"Running {len(probes)} probe(s) as {os.environ.get('USER', '?')} …", flush=True)
    mem_before = _episodic_count()
    results = []
    for p in probes:
        print(f"  → {p['id']} …", flush=True)
        results.append(_run_one(p))
    mem_after = _episodic_count()
    meta = {"mem_before": mem_before, "mem_after": mem_after,
            "n": len(results), "dry_run": args.dry_run}
    path = _write_report(results, meta)
    print(f"\nReport: {path}")
    print("Verdicts: " + ", ".join(f"{r['id']}={r['verdict']}" for r in results))
    if mem_before != mem_after:
        print(f"WARNING: episodic_memory changed {mem_before}->{mem_after} "
              "(MEM0 isolation breach — investigate before trusting results)")


if __name__ == "__main__":
    main()
