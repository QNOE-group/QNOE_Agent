#!/usr/bin/env python3
"""Context-block tally — makes threat-scanner drops visible (TODO "context-block
tracking", lineage: memory/mistakes.md M53).

Hermes silently drops context content that matches a threat pattern; the only
runtime trace is a per-turn WARNING in each profile's private agent.log
(0700 qnoe-ai — invisible to everyone else). This job, run hourly as qnoe-ai
by qnoe-context-tally.timer (OUTSIDE the OpenShell sandbox, so it can read
those logs), does three things:

1. Incrementally parses every profile's logs/agent.log for block WARNINGs and
   appends structured events to logs/context_blocks.jsonl (30-day retention).
   Two verified message formats (site-packages, 2026-07-16):
     agent.prompt_builder: Context file <name> blocked: <ids>
     tools.memory_tool: Memory entry from <name> blocked at load time: <ids>
   A LOOSE detector also runs; block-ish lines that the strict regexes miss
   become kind="anomaly" events — a Hermes upgrade changing the message text
   shows up as anomalies instead of silently zeroing the tally.
2. Re-runs scripts/soul_health.py --json and atomically rewrites
   logs/soul_health.json, so a live edit to a MEMORY/USER file is caught
   within the hour instead of only at the next gateway restart.
3. Updates logs/context_block_tally.state.json (per-file offsets + last_run).
   The nightly report's task_context_blocks reads all three files and flags
   the tally as STALE when last_run is old — the monitor monitors itself.

All output is written with group rw (umask 002) so the yzamir nightly can read
it. Timestamps are naive local time, matching agent.log. Exit code is always 0
on partial failure (errors go to stderr → journal); a wedged step never blocks
the other steps.
"""
import glob
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta

HERMES_ROOT = os.environ.get("HERMES_ROOT", "/opt/qnoe-agent/hermes")
LOGS_DIR = os.environ.get("AGENT_LOGS_DIR", "/opt/qnoe-agent/logs")
EVENTS_PATH = os.path.join(LOGS_DIR, "context_blocks.jsonl")
STATE_PATH = os.path.join(LOGS_DIR, "context_block_tally.state.json")
HEALTH_PATH = os.path.join(LOGS_DIR, "soul_health.json")
SOUL_HEALTH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "soul_health.py")
RETENTION_DAYS = 30
RECENT_HASHES_MAX = 500
RAW_TRUNC = 300

# agent.log line: "YYYY-mm-dd HH:MM:SS,ms LEVEL [session] logger: message"
# (the [session] bracket is present for agent loggers, absent for e.g. urllib3).
_PREFIX = r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d+ WARNING (?:\[(?P<session>\S+)\] )?"
STRICT_RES = [
    (re.compile(_PREFIX + r"agent\.prompt_builder: Context file (?P<file>.+?) "
                          r"blocked: (?P<patterns>.+)$"), "context_file"),
    (re.compile(_PREFIX + r"tools\.memory_tool: Memory entry from (?P<file>.+?) "
                          r"blocked at load time: (?P<patterns>.+)$"), "memory_entry"),
]
# Format-drift canary: anything block-ish from the two scanning modules that
# the strict regexes did NOT match becomes an "anomaly" event.
LOOSE_RE = re.compile(r"(prompt_builder|memory_tool).*block", re.IGNORECASE)

_now = lambda: datetime.now().isoformat(timespec="seconds")


def _warn(msg):
    print(f"context_block_tally: {msg}", file=sys.stderr)


def _atomic_write(path, text):
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".tally-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.chmod(tmp, 0o664)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _load_state():
    try:
        with open(STATE_PATH, encoding="utf-8") as fh:
            state = json.load(fh)
        if state.get("version") == 1:
            return state
    except (OSError, ValueError):
        pass
    return {"version": 1, "last_run": None, "files": {}, "recent_hashes": []}


def _event_hash(ev):
    key = "|".join([ev.get("ts") or "", ev.get("session") or "", ev["profile"],
                    ev["kind"], ev.get("file") or "", ",".join(ev.get("patterns") or []),
                    ev.get("raw", "")])
    return hashlib.sha1(key.encode("utf-8", "replace")).hexdigest()[:16]


def _parse_line(line, profile):
    for rx, kind in STRICT_RES:
        m = rx.match(line)
        if m:
            return {"ts": m.group("ts").replace(" ", "T"),
                    "session": m.group("session"),
                    "profile": profile, "kind": kind, "file": m.group("file"),
                    "patterns": [p.strip() for p in m.group("patterns").split(",")]}
    if LOOSE_RE.search(line):
        return {"ts": None, "session": None, "profile": profile, "kind": "anomaly",
                "file": None, "patterns": [], "raw": line.strip()[:RAW_TRUNC]}
    return None


def parse_logs(state):
    """Incrementally read each profile's agent.log; return new events."""
    events = []
    seen_paths = set()
    for prof_dir in sorted(glob.glob(os.path.join(HERMES_ROOT, "profiles", "*"))):
        log_path = os.path.join(prof_dir, "logs", "agent.log")
        if not os.path.isfile(log_path):
            continue
        profile = os.path.basename(prof_dir)
        seen_paths.add(log_path)
        try:
            st = os.stat(log_path)
            fstate = state["files"].get(log_path, {})
            offset = fstate.get("offset", 0)
            if fstate.get("inode") != st.st_ino or st.st_size < offset:
                offset = 0  # new / rotated / truncated file — start over
            with open(log_path, encoding="utf-8", errors="replace") as fh:
                fh.seek(offset)
                while True:
                    pos = fh.tell()
                    line = fh.readline()
                    if not line:
                        break
                    if not line.endswith("\n"):
                        # partial line mid-write — re-read it next run
                        fh.seek(pos)
                        break
                    ev = _parse_line(line.rstrip("\n"), profile)
                    if ev:
                        events.append(ev)
                new_offset = fh.tell()
            state["files"][log_path] = {"inode": st.st_ino, "offset": new_offset}
        except OSError as e:
            _warn(f"cannot read {log_path}: {e}")
    # forget files that vanished
    for path in [p for p in state["files"] if p not in seen_paths]:
        del state["files"][path]
    return events


def append_events(events, state):
    """Dedup against recent_hashes, then append to the JSONL (0664 via umask)."""
    recent = state.setdefault("recent_hashes", [])
    fresh = []
    now = _now()
    for ev in events:
        h = _event_hash(ev)
        if h in recent:
            continue
        recent.append(h)
        ev["ingested_at"] = now
        fresh.append(ev)
    del recent[:-RECENT_HASHES_MAX]
    if fresh:
        with open(EVENTS_PATH, "a", encoding="utf-8") as fh:
            for ev in fresh:
                fh.write(json.dumps(ev, ensure_ascii=False) + "\n")
    return len(fresh)


def prune_events():
    """Drop events older than RETENTION_DAYS (sp_activity precedent)."""
    if not os.path.isfile(EVENTS_PATH):
        return
    cutoff = (datetime.now() - timedelta(days=RETENTION_DAYS)).isoformat(timespec="seconds")
    kept, dropped = [], 0
    try:
        with open(EVENTS_PATH, encoding="utf-8") as fh:
            for line in fh:
                line = line.rstrip("\n")
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                    ts = ev.get("ts") or ev.get("ingested_at") or ""
                except ValueError:
                    kept.append(line)  # never destroy lines we can't parse
                    continue
                if ts >= cutoff:
                    kept.append(line)
                else:
                    dropped += 1
    except OSError as e:
        _warn(f"prune: cannot read {EVENTS_PATH}: {e}")
        return
    if dropped:
        _atomic_write(EVENTS_PATH, "".join(l + "\n" for l in kept))
        _warn(f"pruned {dropped} event(s) older than {RETENTION_DAYS}d")


def refresh_static_scan():
    """Re-run soul_health.py --json → atomic rewrite of soul_health.json."""
    try:
        out = subprocess.run(
            [sys.executable, SOUL_HEALTH, "--json"],
            capture_output=True, text=True, timeout=120,
        ).stdout.strip()
        obj = json.loads(out)  # validate before overwriting the previous good file
        _atomic_write(HEALTH_PATH, json.dumps(obj) + "\n")
        return obj.get("summary", "")
    except (OSError, ValueError, subprocess.SubprocessError) as e:
        _warn(f"static scan failed (previous soul_health.json left in place): {e}")
        return None


def main():
    os.umask(0o002)
    state = _load_state()

    try:
        events = parse_logs(state)
        n = append_events(events, state)
        anomalies = sum(1 for e in events if e["kind"] == "anomaly")
        print(f"context_block_tally: {n} new event(s)"
              + (f", {anomalies} anomaly line(s)" if anomalies else ""))
    except Exception as e:  # noqa: BLE001 — step isolation, never skip the rescan
        _warn(f"log parse failed: {e}")

    summary = refresh_static_scan()
    if summary:
        print(f"context_block_tally: static scan — {summary}")

    try:
        prune_events()
    except Exception as e:  # noqa: BLE001
        _warn(f"prune failed: {e}")

    state["last_run"] = _now()
    try:
        _atomic_write(STATE_PATH, json.dumps(state) + "\n")
    except OSError as e:
        _warn(f"cannot write state: {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
