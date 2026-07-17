#!/usr/bin/env python3
"""Seed the Tier-1 QTM factual anchor into the Cognee graph (deterministic, NO LLM).

Reads the QCoDeS registry read-only for L110 QTM runs and inserts typed anchor
nodes (Setup, Sample, MeasurementType) via `add_data_points`, so the Tier-2
concepts extracted from the QTOM docs can link onto real lab entities. Runs
themselves are NOT seeded (too many; concepts link to setups/samples, not
individual runs).

Env: AGENT_DATA_DIR (registry path), COGNEE_DATA. Requires the same cognee
config as run_pilot (call configure() there or import).

Usage (DGX):
  ENABLE_BACKEND_ACCESS_CONTROL=false /home/yzamir/cognee-pilot/venv/bin/python \
    seed_anchor.py --dataset qtom_pilot
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import re
import sqlite3
import sys

REGISTRY_DBS = [
    os.path.join(os.environ.get("AGENT_DATA_DIR", "/home/yzamir/qnoe_server_data"), "episodic.db"),
    "/opt/qnoe-agent/memory/episodic.db",
]
SETUP_LIKE = os.environ.get("QTM_SETUP_LIKE", "%L110 QTM%")

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("seed_anchor")

# measurement-type phrase rules (mirror grounding_validator._TYPE_RULES intent)
_TYPES = [
    ("gate-sweep", re.compile(r"gate[\s_-]*sweep|sweep[\s_-]*gate|\bvg[\s_-]*sweep", re.I)),
    ("IV", re.compile(r"\biv\b|\bi[\s_-]?v[\s_-]|bias[\s_-]*sweep|current[\s_-]*voltage", re.I)),
    ("photocurrent", re.compile(r"photo[\s_-]*current", re.I)),
    ("temperature", re.compile(r"temp[\s_-]*depend|temperature|cooldown|vs[\s_-]*t\b", re.I)),
]


def _connect_ro(db: str) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=3)


def read_l110_qtm() -> dict:
    """Return {samples: {name->crystal}, mtypes: set} from L110 QTM registry rows."""
    samples: dict[str, str] = {}
    mtypes: set[str] = set()
    for db in REGISTRY_DBS:
        if not os.path.exists(db):
            continue
        try:
            con = _connect_ro(db)
            try:
                for run_name, sample_name in con.execute(
                    "SELECT run_name, sample_name FROM qcodes_registry WHERE db_path LIKE ?",
                    (SETUP_LIKE,),
                ):
                    if sample_name:
                        samples.setdefault(sample_name.strip(), sample_name.strip())
                    text = f"{run_name or ''}".lower()
                    for label, rx in _TYPES:
                        if rx.search(text):
                            mtypes.add(label)
            finally:
                con.close()
        except sqlite3.Error as e:
            logger.warning("registry read %s: %s", db, e)
    return {"samples": samples, "mtypes": mtypes}


async def seed(dataset: str) -> int:
    from cognee.infrastructure.engine import DataPoint
    from cognee.tasks.storage import add_data_points

    class Setup(DataPoint):
        name: str
        metadata: dict = {"index_fields": ["name"]}

    class Sample(DataPoint):
        name: str
        crystal: str = ""
        metadata: dict = {"index_fields": ["name", "crystal"]}

    class MeasurementType(DataPoint):
        name: str
        metadata: dict = {"index_fields": ["name"]}

    facts = read_l110_qtm()
    setup = Setup(name="L110 QTM")
    samples = [Sample(name=n, crystal=c) for n, c in facts["samples"].items()]
    mtypes = [MeasurementType(name=m) for m in sorted(facts["mtypes"])]
    nodes = [setup, *samples, *mtypes]
    logger.info("seeding %d anchor nodes: 1 Setup, %d Sample, %d MeasurementType",
                len(nodes), len(samples), len(mtypes))
    await add_data_points(dataset, nodes)
    logger.info("seeded L110 QTM anchor into dataset=%s", dataset)
    return 0


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dataset", default="qtom_pilot")
    args = ap.parse_args(argv)
    # cognee config comes from run_pilot.configure(); import + call it here too
    from run_pilot import configure
    configure()
    return asyncio.run(seed(args.dataset))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
