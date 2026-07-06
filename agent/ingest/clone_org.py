"""Clone (or update) all repos from the QNOE-group GitHub organisation.

Usage:
  python -m agent.ingest.clone_org

Reads GitHub PAT from /opt/qnoe-agent/secrets/github_pat (or GITHUB_PAT env var).
Clones all org repos into REPOS_DIR (default: /opt/qnoe-agent/repos/).
On subsequent runs: pulls existing repos instead of re-cloning.

Handles GitHub API pagination automatically (fetches all pages).
"""
import logging
import os
import subprocess
import sys
from pathlib import Path

import requests

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

ORG = "QNOE-group"
REPOS_DIR = Path(os.environ.get("REPOS_DIR", "/opt/qnoe-agent/repos"))
SECRETS_PATH = Path(os.environ.get(
    "GITHUB_PAT_FILE", "/opt/qnoe-agent/secrets/github_pat"
))
GITHUB_API = "https://api.github.com"


def _get_pat() -> str:
    pat = os.environ.get("GITHUB_PAT")
    if pat:
        return pat.strip()
    if SECRETS_PATH.exists():
        return SECRETS_PATH.read_text().strip()
    logger.error(
        "No GitHub PAT found. Set GITHUB_PAT env var or write to %s", SECRETS_PATH
    )
    sys.exit(1)


def _list_repos(pat: str) -> list[dict]:
    """Return all repos in the org, handling pagination."""
    headers = {
        "Authorization": f"token {pat}",
        "Accept": "application/vnd.github+json",
    }
    repos: list[dict] = []
    url = f"{GITHUB_API}/orgs/{ORG}/repos?per_page=100&type=all"

    while url:
        resp = requests.get(url, headers=headers, timeout=30)
        if resp.status_code == 401:
            logger.error("GitHub PAT is invalid or expired.")
            sys.exit(1)
        if resp.status_code == 403:
            logger.error(
                "GitHub PAT does not have access to org %s. "
                "Ensure the org owner has added qnoe-ai to the organisation "
                "and approved the PAT.", ORG
            )
            sys.exit(1)
        resp.raise_for_status()
        repos.extend(resp.json())

        # Follow next-page link if present
        next_link = resp.links.get("next", {}).get("url")
        url = next_link  # None if no next page

    return repos


def _clone_or_pull(repo: dict, pat: str) -> None:
    name = repo["name"]
    clone_url = repo["clone_url"]
    # Embed PAT in URL for HTTPS auth
    auth_url = clone_url.replace("https://", f"https://qnoe-ai:{pat}@")
    target = REPOS_DIR / name

    if target.exists():
        logger.info("Pulling  %s", name)
        result = subprocess.run(
            ["git", "-C", str(target), "pull", "--ff-only"],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            safe_err = result.stderr.replace(pat, "***").strip()
            logger.warning("Pull failed for %s: %s", name, safe_err)
    else:
        logger.info("Cloning  %s", name)
        result = subprocess.run(
            ["git", "clone", "--depth=1", auth_url, str(target)],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            # Sanitise error: git may echo the auth URL (with PAT) in error messages
            safe_err = result.stderr.replace(pat, "***").strip()
            logger.error("Clone failed for %s: %s", name, safe_err)


def main() -> None:
    pat = _get_pat()
    REPOS_DIR.mkdir(parents=True, exist_ok=True)

    logger.info("Listing repos in %s org...", ORG)
    repos = _list_repos(pat)
    logger.info("Found %d repos", len(repos))

    for repo in repos:
        if repo.get("archived"):
            logger.info("Skipping archived repo: %s", repo["name"])
            continue
        _clone_or_pull(repo, pat)

    logger.info("Done. Repos at %s", REPOS_DIR)
    logger.info("Repo list:")
    for d in sorted(REPOS_DIR.iterdir()):
        if d.is_dir():
            logger.info("  %s", d.name)


if __name__ == "__main__":
    main()
