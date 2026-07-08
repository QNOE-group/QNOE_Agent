"""One-time ingestion of QCoDeS .db files from SharePoint into the qcodes-runs collection.

Downloads each .db file to a temp path, runs scan_specific_dbs (same pipeline as CIFS),
then deletes the temp file. Results land in qcodes_registry + qcodes-runs Qdrant collection.

Run once:
  cd /opt/qnoe-agent && source venv/bin/activate
  PYTHONPATH=/opt/qnoe-agent \\
    SHAREPOINT_USERNAME=$(grep SHAREPOINT_USERNAME secrets/sharepoint.env | cut -d= -f2) \\
    SHAREPOINT_PASSWORD=$(grep SHAREPOINT_PASSWORD secrets/sharepoint.env | cut -d= -f2) \\
    nohup venv/bin/python -m agent.ingest.ingest_sp_qcodes \\
    > logs/sp_qcodes_ingest.log 2>&1 &

Do NOT run again after completion — SharePoint DBs are treated as historic snapshots only.
"""
import asyncio
import logging
import os
from pathlib import Path

import yaml

from .sharepoint_client import authenticate, download_to_temp, get_delta, get_drive_id, get_site_id
from .qcodes_scanner import scan_specific_dbs

logger = logging.getLogger(__name__)

SP_CONFIG_PATH = os.environ.get("SHAREPOINT_CONFIG", "/opt/qnoe-agent/config/sharepoint.yaml")
TEMP_DIR = Path(os.environ.get("SP_TEMP_DIR", "/tmp/qnoe-sharepoint-qcodes/"))
MAX_FILE_MB = int(os.environ.get("SP_QCODES_MAX_MB", "3000"))  # allow larger DBs than doc sync


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    with open(SP_CONFIG_PATH) as f:
        cfg = yaml.safe_load(f)

    token = authenticate(cfg["auth"])
    logger.info("Authentication OK")

    total_dbs = 0
    total_new_runs = 0
    total_errors = 0

    for site in cfg["sites"]:
        site_name = site["name"]
        site_id = get_site_id(site["teams_group_id"], token)
        logger.info("Site: %s → %s", site_name, site_id)

        for drive_name in site.get("drives", ["Documents"]):
            drive_id = get_drive_id(site_id, drive_name, token)
            logger.info("Drive: %s → %s", drive_name, drive_id)

            logger.info("Listing all items via delta endpoint...")
            all_items, _ = get_delta(drive_id, None, token, auth_cfg=cfg["auth"])
            _SKIP_DB_NAMES = {"thumbs.db", "desktop.ini"}
            db_items = [
                i for i in all_items
                if "file" in i
                and not i.get("deleted")
                and Path(i.get("name", "")).suffix.lower() == ".db"
                and i.get("name", "").lower() not in _SKIP_DB_NAMES
            ]
            logger.info("Found %d .db files in %s / %s", len(db_items), site_name, drive_name)

            for item in db_items:
                name = item["name"]
                size_mb = item.get("size", 0) / (1024 * 1024)
                if size_mb > MAX_FILE_MB:
                    logger.warning("Skipping oversized DB (%.0f MB): %s", size_mb, name)
                    continue

                parent_path = item.get("parentReference", {}).get("path", "")
                if "root:" in parent_path:
                    parent_path = parent_path.split("root:", 1)[1].lstrip("/")
                rel_path = f"{parent_path}/{name}".lstrip("/") if parent_path else name

                dest = TEMP_DIR / site_name / rel_path
                dest.parent.mkdir(parents=True, exist_ok=True)

                logger.info("Downloading (%.0f MB): %s", size_mb, rel_path)
                try:
                    download_to_temp(drive_id, item["id"], dest, token)
                    stats = asyncio.run(scan_specific_dbs([dest]))
                    new_runs = stats.get("new_runs", 0)
                    logger.info(
                        "  → %d new runs, %d cards upserted", new_runs, stats.get("cards_upserted", 0)
                    )
                    total_dbs += 1
                    total_new_runs += new_runs
                except Exception as exc:
                    logger.error("Failed to process %s: %s", name, exc)
                    total_errors += 1
                finally:
                    dest.unlink(missing_ok=True)

    logger.info(
        "Done. %d DBs processed, %d new runs ingested, %d errors.",
        total_dbs, total_new_runs, total_errors,
    )


if __name__ == "__main__":
    main()
