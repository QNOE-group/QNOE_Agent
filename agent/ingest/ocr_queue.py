"""OCR queue processor for empty/scanned PDFs.

Reads /tmp/empty_pdfs.log (append-only, written by ingestion workers as they
encounter PDFs with < 200 chars from pypdf), deduplicates entries, skips files
already in the manifest, and re-indexes the remainder with Docling OCR enabled.

Design: the log is append-only — workers write to it, this script never modifies
it. The manifest DB is the authoritative "done" set. Running this script multiple
times is safe and idempotent: newly completed files are skipped on the next run,
and new entries added by still-running workers are picked up automatically.

Usage:
  python -m agent.ingest.ocr_queue                  # process all pending
  python -m agent.ingest.ocr_queue --dry-run        # report counts only
  python -m agent.ingest.ocr_queue --batch 200      # process up to 200 files

Environment variables:
  EMPTY_PDF_LOG   path to log file (default: /tmp/empty_pdfs.log)
  AGENT_DATA_DIR  directory containing manifest episodic.db
                  (default: /home/yzamir/qnoe_server_data)
  QDRANT_URL      Qdrant endpoint (default: http://localhost:6333)
  DOCLING_DEVICE  cpu | cuda | auto (default: cpu)
"""
import argparse
import logging
import os
import sqlite3
import sys
from pathlib import Path

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

EMPTY_PDF_LOG = Path(os.environ.get("EMPTY_PDF_LOG", "/tmp/empty_pdfs.log"))
AGENT_DATA_DIR = os.environ.get("AGENT_DATA_DIR", "/home/yzamir/qnoe_server_data")
DEFAULT_MANIFEST_DB = os.path.join(AGENT_DATA_DIR, "episodic.db")
TEAM = "group-wide"


# ── Helpers ────────────────────────────────────────────────────────────────────

def _read_log(log_path: Path) -> list[Path]:
    """Read and deduplicate paths from the log. Returns only unique entries."""
    if not log_path.exists():
        logger.error("Log file not found: %s", log_path)
        return []
    seen: set[str] = set()
    paths: list[Path] = []
    for line in log_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line in seen:
            continue
        seen.add(line)
        paths.append(Path(line))
    return paths


def _already_indexed(manifest_db: str) -> set[str]:
    """Return file paths already present in the manifest DB."""
    try:
        conn = sqlite3.connect(manifest_db)
    except Exception as exc:
        logger.warning("Could not open manifest DB %s: %s", manifest_db, exc)
        return set()
    try:
        rows = conn.execute("SELECT file_path FROM index_manifest").fetchall()
        return {r[0] for r in rows}
    except Exception as exc:
        logger.warning("Could not query manifest: %s", exc)
        return set()
    finally:
        conn.close()


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="OCR queue processor for scanned PDFs")
    parser.add_argument(
        "--log", default=str(EMPTY_PDF_LOG),
        help="Path to empty_pdfs.log (default: %(default)s)",
    )
    parser.add_argument(
        "--manifest-db", default=DEFAULT_MANIFEST_DB,
        help="Path to manifest SQLite DB (default: %(default)s)",
    )
    parser.add_argument("--team", default=TEAM, help="Qdrant collection (default: %(default)s)")
    parser.add_argument(
        "--batch", type=int, default=0, metavar="N",
        help="Process at most N pending files per run (0 = all)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Report counts without indexing")
    args = parser.parse_args()

    log_path = Path(args.log)

    # ── Step 1: read + deduplicate log ────────────────────────────────────────
    all_paths = _read_log(log_path)
    raw_lines = sum(
        1 for l in log_path.read_text(encoding="utf-8", errors="replace").splitlines() if l.strip()
    ) if log_path.exists() else 0
    logger.info("Log: %d raw lines → %d unique paths", raw_lines, len(all_paths))

    # ── Step 2: filter to files that exist on disk ────────────────────────────
    existing = [p for p in all_paths if p.exists()]
    not_on_disk = len(all_paths) - len(existing)
    if not_on_disk:
        logger.info("Skipping %d paths not found on disk (mount unavailable or moved)", not_on_disk)

    # ── Step 3: skip already indexed ─────────────────────────────────────────
    done = _already_indexed(args.manifest_db)
    pending = [p for p in existing if str(p) not in done]
    logger.info(
        "Already indexed: %d  |  Pending OCR: %d",
        len(existing) - len(pending), len(pending),
    )

    if not pending:
        logger.info("Nothing to do — all known empty PDFs are either indexed or off-disk.")
        return

    # ── Step 4: apply batch limit ─────────────────────────────────────────────
    batch = pending[: args.batch] if args.batch > 0 else pending
    if args.batch > 0 and len(pending) > args.batch:
        logger.info("Batch limit: processing %d of %d pending files", len(batch), len(pending))

    if args.dry_run:
        logger.info("[dry-run] Would process %d files with DOCLING_OCR=1:", len(batch))
        for p in batch[:20]:
            logger.info("  %s", p.name)
        if len(batch) > 20:
            logger.info("  ... and %d more", len(batch) - 20)
        return

    # ── Step 5: enable OCR and ingest ─────────────────────────────────────────
    os.environ["DOCLING_OCR"] = "1"

    from .run_ingest import ingest_directory

    logger.info("Starting OCR ingestion of %d files (DOCLING_OCR=1) ...", len(batch))
    ingest_directory(
        team=args.team,
        repo_path=Path("/"),        # unused when file_list is provided
        repo_name="server/ocr",
        force=False,                # pre-filtered above; force=True set internally by file_list
        dry_run=False,
        file_list=batch,
        manifest_db=args.manifest_db,
    )
    logger.info("OCR queue run complete.")


if __name__ == "__main__":
    main()
