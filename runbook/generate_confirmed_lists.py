#!/usr/bin/env python3
"""Resolve confirmed paper paths from SUSPECTED_PAPERS_REVIEW.md and write full-path lists.

Handles paths with '...' (truncated names) by using 'find' to locate them.

Usage:
    python generate_confirmed_lists.py
Output files:
    /tmp/confirmed_papers_manuscripts.txt
    /tmp/confirmed_papers_theses.txt
    /tmp/confirmed_papers_books.txt
"""
import re
import subprocess
from pathlib import Path

REVIEW_FILE = Path("/opt/qnoe-agent/runbook/SUSPECTED_PAPERS_REVIEW.md")
BASE_DIRS = {
    "Manuscripts": Path("/ICFO/groups/NOE/Manuscripts"),
    "Theses": Path("/ICFO/groups/NOE/Theses & reports"),
    "Books": Path("/ICFO/groups/NOE/Papers & Books"),
}
OUT_FILES = {
    "Manuscripts": Path("/tmp/confirmed_papers_manuscripts.txt"),
    "Theses":      Path("/tmp/confirmed_papers_theses.txt"),
    "Books":       Path("/tmp/confirmed_papers_books.txt"),
}

def resolve_path(base: Path, rel: str) -> Path | None:
    """Return the full path, handling '...' truncation via find."""
    if "..." not in rel:
        p = base / rel
        return p if p.exists() else None

    # Split on first '...' occurrence — could be in dir name or filename
    parts = rel.split("...")
    prefix = parts[0].rstrip("/")
    suffix = parts[-1].lstrip("/")
    filename = Path(suffix).name if suffix else None

    # Search under base/prefix* for the filename
    search_root = base / prefix if prefix else base
    # Find the closest matching parent dir using glob
    candidates = list(base.glob(f"{prefix}*")) if prefix else [base]
    for cand in candidates:
        if cand.is_dir():
            # Search for filename under this dir
            try:
                result = subprocess.run(
                    ["find", str(cand), "-name", filename, "-type", "f"],
                    capture_output=True, text=True, timeout=30
                )
                matches = [Path(l.strip()) for l in result.stdout.splitlines() if l.strip()]
                if matches:
                    return matches[0]
            except Exception:
                pass
    return None


def parse_section(text: str, section_header: str) -> list[str]:
    """Extract Y-marked filenames from a markdown table section."""
    # Find section
    start = text.find(f"## {section_header}")
    if start == -1:
        return []
    end = text.find("\n## ", start + 1)
    section = text[start:end] if end != -1 else text[start:]

    confirmed = []
    for line in section.splitlines():
        # Match table rows: | N | `path` | Y |
        m = re.match(r'\|\s*\d+\s*\|\s*`([^`]+)`\s*\|\s*Y\s*\|', line)
        if m:
            confirmed.append(m.group(1))
    return confirmed


def main():
    text = REVIEW_FILE.read_text(encoding="utf-8")

    sections = [
        ("Manuscripts (315 files)", "Manuscripts"),
        ("Theses & Reports (112 files)", "Theses"),
        ("Papers & Books (W6)", "Books"),
    ]

    for header, key in sections:
        base = BASE_DIRS[key]
        out = OUT_FILES[key]
        rel_paths = parse_section(text, header)
        print(f"\n{key}: {len(rel_paths)} Y entries")

        resolved = []
        missing = []
        for rel in rel_paths:
            full = resolve_path(base, rel)
            if full:
                resolved.append(full)
            else:
                missing.append(rel)

        out.write_text("\n".join(str(p) for p in resolved) + "\n", encoding="utf-8")
        print(f"  Resolved: {len(resolved)}  Missing: {len(missing)}")
        for m in missing:
            print(f"    NOT FOUND: {m}")
        print(f"  Written to {out}")


if __name__ == "__main__":
    main()
