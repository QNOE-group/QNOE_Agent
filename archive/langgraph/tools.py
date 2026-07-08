"""Agent tools — functions the LLM can call via tool_calls.

Phase 1 tools: read_file, list_directory, search_files.
All tools are synchronous (run in executor).
"""
import fnmatch
import json
import os
import subprocess

# Allowed path prefixes (read-only access)
ALLOWED_ROOTS = (
    "/ICFO/groups/NOE",
    "/opt/qnoe-agent/repos",
)

MAX_LINES_DEFAULT = 200  # default lines returned per read
MAX_LINES_CAP = 500      # hard cap to protect context window

# OpenAI-format tool definitions for vLLM
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": (
                "Read lines from a file on the lab server or cloned repos. "
                "Returns numbered lines. For large files, use start_line and "
                "end_line to read specific sections. If called without line "
                "range, returns the first 200 lines plus a summary of total "
                "line count. Paths start with /ICFO/groups/NOE/ (lab server) "
                "or /opt/qnoe-agent/repos/ (GitHub clones)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": (
                            "Absolute path to the file, e.g. "
                            "/ICFO/groups/NOE/Notebook/QTM/script.py or "
                            "/opt/qnoe-agent/repos/QTM_CodeBase/src/main.py"
                        ),
                    },
                    "start_line": {
                        "type": "integer",
                        "description": (
                            "First line to read (1-based). Defaults to 1."
                        ),
                    },
                    "end_line": {
                        "type": "integer",
                        "description": (
                            "Last line to read (inclusive). Defaults to "
                            "start_line + 199. Max 500 lines per call."
                        ),
                    },
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": (
                "List files and subdirectories in a directory on the lab server "
                "or cloned repos. Use this to explore folder structure before "
                "reading specific files."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": (
                            "Absolute path to the directory, e.g. "
                            "/ICFO/groups/NOE/Notebook/QTM/ or "
                            "/opt/qnoe-agent/repos/QTM_CodeBase/src/"
                        ),
                    },
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_files",
            "description": (
                "Search for files by name pattern across the lab server and "
                "cloned repos. Supports glob patterns (*.py, **/*.ipynb) and "
                "optional content matching. Use this to find files when you "
                "don't know the exact path. Returns matching file paths with "
                "size and modification date."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": (
                            "Glob pattern to match filenames. Examples: "
                            "'*.py' (Python files), '**/*.ipynb' (notebooks "
                            "in any subdirectory), '*gate_sweep*' (files "
                            "with gate_sweep in the name), 'README*'."
                        ),
                    },
                    "path": {
                        "type": "string",
                        "description": (
                            "Directory to search in. Must start with "
                            "/ICFO/groups/NOE/ or /opt/qnoe-agent/repos/. "
                            "Defaults to /opt/qnoe-agent/repos/ if omitted."
                        ),
                    },
                    "max_depth": {
                        "type": "integer",
                        "description": (
                            "Maximum directory depth to search. Default 5. "
                            "Use 1 for current directory only."
                        ),
                    },
                    "max_results": {
                        "type": "integer",
                        "description": (
                            "Maximum number of results to return. Default 50."
                        ),
                    },
                },
                "required": ["pattern"],
            },
        },
    },
]


# ---------------------------------------------------------------------------
# Limits
# ---------------------------------------------------------------------------

SEARCH_MAX_RESULTS_CAP = 100   # hard cap on search results
SEARCH_MAX_DEPTH_CAP = 8       # hard cap on directory depth
SEARCH_TIMEOUT_SECONDS = 30    # hard timeout for find subprocess

# Directories to always skip (junk, caches, huge trees)
SEARCH_SKIP_DIRS = frozenset({
    ".git", "__pycache__", "node_modules", ".ipynb_checkpoints",
    ".tox", ".mypy_cache", ".pytest_cache", "venv", ".venv",
    "egg-info", ".eggs", "dist", "build",
})

# File names to always skip
SEARCH_SKIP_FILES = frozenset({
    "Thumbs.db", ".DS_Store", "desktop.ini",
})


def _validate_path(path: str) -> str | None:
    """Return an error message if path is not allowed, else None."""
    path = os.path.normpath(path)
    if ".." in path.split(os.sep):
        return "Path traversal (..) is not allowed."
    if not any(path.startswith(root) for root in ALLOWED_ROOTS):
        return (
            f"Access denied. Allowed paths: {', '.join(ALLOWED_ROOTS)}"
        )
    return None


def read_file(path: str, start_line: int = 1, end_line: int | None = None) -> str:
    """Read lines from a file, returning numbered content or an error message."""
    path = os.path.normpath(path)
    err = _validate_path(path)
    if err:
        return err
    if os.path.isdir(path):
        return f"This is a directory, not a file. Use list_directory to see its contents."
    if not os.path.isfile(path):
        return f"File not found: {path}"
    # Binary file check
    _, ext = os.path.splitext(path)
    if ext.lower() in (".db", ".sqlite", ".sqlite3"):
        return (
            f"This is a SQLite database file ({os.path.getsize(path):,} bytes). "
            f"read_file cannot open binary databases. "
            f"The qcodes-runs Qdrant collection already indexes measurement "
            f"metadata from QCoDeS databases — try asking about the measurements "
            f"directly and RAG will surface the relevant run cards."
        )
    try:
        with open(path, "r", errors="replace") as f:
            all_lines = f.readlines()

        total = len(all_lines)
        if total == 0:
            return "(empty file)"

        # Clamp start_line
        start_line = max(1, start_line)
        if start_line > total:
            return f"start_line {start_line} is past end of file ({total} lines)."

        # Default end_line
        if end_line is None:
            end_line = start_line + MAX_LINES_DEFAULT - 1
        end_line = min(end_line, total)

        # Cap number of lines
        if end_line - start_line + 1 > MAX_LINES_CAP:
            end_line = start_line + MAX_LINES_CAP - 1

        # Extract lines (convert to 0-based)
        selected = all_lines[start_line - 1 : end_line]
        numbered = []
        for i, line in enumerate(selected, start=start_line):
            numbered.append(f"{i:>6}\t{line.rstrip()}")

        result = "\n".join(numbered)

        # Add file info header
        header = f"[{path} — lines {start_line}-{end_line} of {total}]"
        if end_line < total:
            header += f" (use start_line={end_line + 1} to continue)"

        return header + "\n" + result
    except Exception as e:
        return f"Error reading file: {e}"


def list_directory(path: str) -> str:
    """List directory contents, returning a formatted string."""
    path = os.path.normpath(path)
    err = _validate_path(path)
    if err:
        return err
    if not os.path.isdir(path):
        return f"Directory not found: {path}"
    try:
        entries = sorted(os.listdir(path))
        if not entries:
            return "(empty directory)"
        if len(entries) > 200:
            entries = entries[:200]
            truncated = True
        else:
            truncated = False
        lines = []
        for name in entries:
            full = os.path.join(path, name)
            suffix = "/" if os.path.isdir(full) else ""
            lines.append(f"  {name}{suffix}")
        result = "\n".join(lines)
        if truncated:
            result += f"\n  ... ({len(os.listdir(path))} total entries, showing first 200)"
        return result
    except Exception as e:
        return f"Error listing directory: {e}"


def search_files(
    pattern: str,
    path: str = "/opt/qnoe-agent/repos",
    max_depth: int = 5,
    max_results: int = 50,
) -> str:
    """Search for files matching a glob pattern under an allowed directory.

    Uses `find` on Linux for performance on large CIFS mounts.
    Falls back to pure-Python os.walk if find is unavailable.
    """
    path = os.path.normpath(path)
    err = _validate_path(path)
    if err:
        return err
    if not os.path.isdir(path):
        return f"Directory not found: {path}"

    # Clamp limits
    max_depth = min(max(1, max_depth), SEARCH_MAX_DEPTH_CAP)
    max_results = min(max(1, max_results), SEARCH_MAX_RESULTS_CAP)

    # Try fast path: GNU find (available on Linux/DGX)
    matches = _search_with_find(path, pattern, max_depth, max_results)
    if matches is None:
        # Fallback: pure Python (works on Windows dev machines too)
        matches = _search_with_walk(path, pattern, max_depth, max_results)

    if not matches:
        return f"No files matching '{pattern}' found under {path} (depth {max_depth})."

    # Format results with metadata
    lines = []
    for fpath in matches:
        try:
            st = os.stat(fpath)
            size = _human_size(st.st_size)
            # Show path relative to search root for readability
            rel = os.path.relpath(fpath, path)
            lines.append(f"  {rel}  ({size})")
        except OSError:
            rel = os.path.relpath(fpath, path)
            lines.append(f"  {rel}")

    header = f"[{len(lines)} files matching '{pattern}' under {path}]"
    if len(matches) >= max_results:
        header += f" (capped at {max_results} — narrow your search)"

    return header + "\n" + "\n".join(lines)


def _search_with_find(
    root: str, pattern: str, max_depth: int, max_results: int,
) -> list[str] | None:
    """Use GNU find for fast searching. Returns None if find is unavailable."""
    # Build prune clause for skipped directories
    prune_args = []
    for d in sorted(SEARCH_SKIP_DIRS):
        prune_args.extend(["-name", d, "-o"])
    # Remove trailing -o
    if prune_args:
        prune_args = ["("] + prune_args[:-1] + [")", "-prune", "-o"]

    cmd = [
        "find", root,
        "-maxdepth", str(max_depth),
        *prune_args,
        "-type", "f",
        "-iname", pattern,
        "-print",
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=SEARCH_TIMEOUT_SECONDS,
        )
    except FileNotFoundError:
        return None  # find not available (Windows)
    except subprocess.TimeoutExpired:
        return None  # too slow, fall back

    if result.returncode not in (0, 1):
        # find returns 1 on permission errors but still outputs matches
        return None

    raw_paths = result.stdout.strip().split("\n") if result.stdout.strip() else []
    # Filter out skip files and limit results
    filtered = []
    for p in raw_paths:
        basename = os.path.basename(p)
        if basename in SEARCH_SKIP_FILES:
            continue
        filtered.append(p)
        if len(filtered) >= max_results:
            break

    return filtered


def _search_with_walk(
    root: str, pattern: str, max_depth: int, max_results: int,
) -> list[str]:
    """Pure-Python fallback using os.walk with depth limiting."""
    root_depth = root.rstrip(os.sep).count(os.sep)
    matches = []

    for dirpath, dirnames, filenames in os.walk(root):
        # Depth check
        current_depth = dirpath.rstrip(os.sep).count(os.sep) - root_depth
        if current_depth >= max_depth:
            dirnames.clear()
            continue

        # Prune skipped directories (in-place to prevent os.walk descent)
        dirnames[:] = [
            d for d in dirnames
            if d not in SEARCH_SKIP_DIRS
        ]

        for fname in filenames:
            if fname in SEARCH_SKIP_FILES:
                continue
            # Case-insensitive glob match
            if fnmatch.fnmatch(fname.lower(), pattern.lower()):
                matches.append(os.path.join(dirpath, fname))
                if len(matches) >= max_results:
                    return matches

    return matches


def _human_size(nbytes: int) -> str:
    """Format byte count as human-readable string."""
    for unit in ("B", "KB", "MB", "GB"):
        if abs(nbytes) < 1024:
            if unit == "B":
                return f"{nbytes} B"
            return f"{nbytes:.1f} {unit}"
        nbytes /= 1024
    return f"{nbytes:.1f} TB"


# Dispatch table
TOOL_FUNCTIONS = {
    "read_file": read_file,
    "list_directory": list_directory,
    "search_files": search_files,
}


def execute_tool_call(name: str, arguments: str | dict) -> str:
    """Execute a tool call by name. Returns the result string."""
    fn = TOOL_FUNCTIONS.get(name)
    if fn is None:
        return f"Unknown tool: {name}"
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except json.JSONDecodeError:
            return f"Invalid JSON arguments: {arguments}"
    return fn(**arguments)
