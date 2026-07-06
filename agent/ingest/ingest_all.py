"""Index all cloned repos into Qdrant.

Usage:
  python -m agent.ingest.ingest_all              # index all repos
  python -m agent.ingest.ingest_all --force      # re-index even if unchanged
  python -m agent.ingest.ingest_all --dry-run    # print plan without writing

Reads repo→collection mapping from:
  /opt/qnoe-agent/config/repo_collections.yaml

Iterates over every directory in REPOS_DIR and maps it to a Qdrant collection
using the rules in repo_collections.yaml. Repos matching no rule go to group-wide.

Skips files whose SHA-256 hash has not changed since last run (hash-based dedup
in the index_manifest SQLite table — same as run_ingest.py).
"""
import argparse
import logging
import os
import sys
from pathlib import Path

import yaml

from .run_ingest import ingest_directory

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

REPOS_DIR = Path(os.environ.get("REPOS_DIR", "/opt/qnoe-agent/repos"))
COLLECTIONS_CONFIG = Path(os.environ.get(
    "COLLECTIONS_CONFIG",
    "/opt/qnoe-agent/config/repo_collections.yaml",
))


def _load_config() -> dict:
    if not COLLECTIONS_CONFIG.exists():
        logger.error("Collections config not found: %s", COLLECTIONS_CONFIG)
        sys.exit(1)
    with open(COLLECTIONS_CONFIG) as f:
        return yaml.safe_load(f)


def _resolve_collection(repo_name: str, config: dict) -> str:
    """Return the Qdrant collection for a given repo name."""
    repo_lower = repo_name.lower()
    for collection, patterns in config.get("collections", {}).items():
        for pattern in patterns:
            if pattern.lower() in repo_lower:
                return collection
    return config.get("default", "group-wide")


def main() -> None:
    parser = argparse.ArgumentParser(description="Index all cloned repos into Qdrant")
    parser.add_argument("--force", action="store_true", help="Re-index unchanged files")
    parser.add_argument("--force-ext", metavar="EXT", nargs="+", help="Re-index only files with these extensions (e.g. --force-ext .pdf .docx)")
    parser.add_argument("--dry-run", action="store_true", help="Print plan without writing")
    parser.add_argument(
        "--repo", default=None,
        help="Only process this repo name (default: all)"
    )
    args = parser.parse_args()

    if not REPOS_DIR.exists():
        logger.error(
            "Repos directory not found: %s\n"
            "Run `python -m agent.ingest.clone_org` first.", REPOS_DIR
        )
        sys.exit(1)

    config = _load_config()
    excluded = set(config.get("exclude", []))
    repos = sorted(d for d in REPOS_DIR.iterdir() if d.is_dir() and not d.name.startswith("."))
    repos = [r for r in repos if r.name not in excluded]

    if args.repo:
        repos = [r for r in repos if r.name == args.repo]
        if not repos:
            logger.error("Repo not found in %s: %s", REPOS_DIR, args.repo)
            sys.exit(1)

    # Print plan
    logger.info("Repos to index: %d", len(repos))
    for repo in repos:
        collection = _resolve_collection(repo.name, config)
        logger.info("  %-40s → %s", repo.name, collection)

    if args.dry_run:
        logger.info("[dry-run] Exiting before writing.")
        return

    # Run ingestion
    for repo in repos:
        collection = _resolve_collection(repo.name, config)
        logger.info("=" * 60)
        logger.info("Indexing %s → collection: %s", repo.name, collection)
        try:
            force_extensions = {e if e.startswith(".") else f".{e}" for e in args.force_ext} if args.force_ext else None
            ingest_directory(
                team=collection,
                repo_path=repo,
                repo_name=repo.name,
                force=args.force,
                dry_run=False,
                force_extensions=force_extensions,
            )
        except Exception as exc:
            logger.error("Failed to index %s: %s", repo.name, exc, exc_info=True)
            # Continue with remaining repos

    logger.info("=" * 60)
    logger.info("Ingestion complete.")


if __name__ == "__main__":
    main()
