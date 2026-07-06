"""Shared exclusion list for find-based scanning.

Single source of truth: config/watcher.yaml → exclude_subfolders.
All find commands (run_ingest, qcodes_scanner, nightly_run) use this module.
"""
import os
from pathlib import Path

import yaml

CONFIG_PATH = Path(os.environ.get(
    "WATCHER_CONFIG", "/opt/qnoe-agent/config/watcher.yaml"
))


def get_excluded_paths(server_root: str | Path | None = None) -> list[str]:
    """Return absolute paths of excluded subfolders.

    Reads exclude_subfolders from watcher.yaml and prepends server_root.
    Falls back to SERVER_ROOT env var or /ICFO/groups/NOE.
    """
    if server_root is None:
        server_root = os.environ.get("SERVER_ROOT", "/ICFO/groups/NOE")
    server_root = str(server_root)

    try:
        with open(CONFIG_PATH) as f:
            config = yaml.safe_load(f) or {}
    except FileNotFoundError:
        return []

    return [
        os.path.join(server_root, sub)
        for sub in config.get("exclude_subfolders", [])
    ]


def find_prune_args(server_root: str | Path | None = None) -> list[str]:
    """Return find(1) prune arguments for excluded subfolders.

    Usage:
        cmd = ["find", root, *find_prune_args(), "-type", "f", ...]
    """
    args: list[str] = []
    for path in get_excluded_paths(server_root):
        args += ["-path", path, "-prune", "-o"]
    return args
