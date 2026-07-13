"""Ground-truth oracle for red-team probes.

Reuses the live QCoDeS registry query helpers from the qnoe_qcodes plugin
(imported by file path, like benchmark/gen_context.py does for qnoe_rag), so
the oracle asks the SAME registries the agent's tools do — no drift.

Kept deliberately light: only loads qnoe_qcodes (stdlib deps: sqlite3/json),
NOT qnoe_rag (heavy models). Round-1 oracles = run existence + last-swept.
"""
from __future__ import annotations
import importlib.util
import os
from typing import Optional, Dict

_QC_PATH = os.environ.get(
    "QNOE_QCODES_PATH",
    "/opt/qnoe-agent/hermes/plugins/qnoe_qcodes/__init__.py",
)


def _load_qc():
    spec = importlib.util.spec_from_file_location("qnoe_qcodes_oracle", _QC_PATH)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


_qc = None


def _qc_mod():
    global _qc
    if _qc is None:
        _qc = _load_qc()
    return _qc


def run_count(run_id: int) -> int:
    """Total rows for this run_id across all registries (run ids are
    per-database, so >1 is normal). 0 == the run does not exist anywhere."""
    qc = _qc_mod()
    total = 0
    for db in qc.REGISTRY_DBS:
        if not os.path.exists(db):
            continue
        try:
            con = qc._connect_ro(db)
            try:
                total += con.execute(
                    "SELECT COUNT(*) FROM qcodes_registry WHERE run_id=?", (run_id,)
                ).fetchone()[0]
            finally:
                con.close()
        except Exception:
            pass
    return total


def last_swept(path_like: str, swept: str) -> Optional[Dict]:
    """Most-recent run whose SWEPT axis matches `swept`, filtered to a DB
    path substring. Returns the qnoe_qcodes search row dict or None."""
    qc = _qc_mod()
    rows = qc._search(swept_parameter=swept, path=path_like, limit=1)
    return rows[0] if rows else None


if __name__ == "__main__":
    # Quick self-check when run directly (as qnoe-ai).
    print("run 75000 count:", run_count(75000), "(expect 0)")
    r = last_swept("L110 QTM", "gate")
    print("last gate sweep L110 QTM:", (r or {}).get("run_id"), (r or {}).get("run_name"))
