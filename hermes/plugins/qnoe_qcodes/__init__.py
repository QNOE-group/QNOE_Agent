"""QNOE QCoDeS measurement registry plugin for Hermes Agent.

Exposes a ``qcodes_search`` tool that queries the ``qcodes_registry``
SQLite table (populated by the QCoDeS scanner during ingestion/nightly
indexing). Returns structured run cards with experiment name, sample,
parameters, timestamps, and source DB path.

The registry DB lives at ``$AGENT_DATA_DIR/episodic.db`` (same DB used
by the ingestion pipeline and QCoDeS scanner).
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from typing import Any, Callable, Dict, List

from datetime import datetime, timezone

logger = logging.getLogger(__name__)

AGENT_DATA_DIR = os.environ.get("AGENT_DATA_DIR", "/home/yzamir/qnoe_server_data")
REGISTRY_DB = os.path.join(AGENT_DATA_DIR, "episodic.db")

MAX_RESULTS = 50

# ---------------------------------------------------------------------------
# Tool schema
# ---------------------------------------------------------------------------

QCODES_SEARCH_SCHEMA = {
    "name": "qcodes_search",
    "description": (
        "Search the QCoDeS measurement registry for experiment runs. "
        "Returns run cards with experiment name, sample, parameters, "
        "timestamp, and source database path. Use to find specific "
        "measurements by sample name, experiment type, or date range."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": (
                    "Free-text search across experiment name, sample name, "
                    "run name, and parameters. Matched with SQL LIKE."
                ),
            },
            "sample": {
                "type": "string",
                "description": "Filter by sample name (exact or partial match).",
            },
            "experiment": {
                "type": "string",
                "description": "Filter by experiment name (partial match).",
            },
            "date_from": {
                "type": "string",
                "description": "Start date filter (ISO format, e.g. 2026-01-01).",
            },
            "date_to": {
                "type": "string",
                "description": "End date filter (ISO format, e.g. 2026-06-30).",
            },
            "limit": {
                "type": "integer",
                "description": f"Max results to return (default 20, max {MAX_RESULTS}).",
            },
        },
        "required": [],
    },
}

# ---------------------------------------------------------------------------
# Query logic
# ---------------------------------------------------------------------------


def _iso_to_epoch(iso_str: str) -> float:
    """Convert ISO date string to Unix epoch for timestamp comparison."""
    try:
        if "T" in iso_str:
            dt = datetime.fromisoformat(iso_str)
        else:
            dt = datetime.strptime(iso_str, "%Y-%m-%d")
        return dt.replace(tzinfo=timezone.utc).timestamp()
    except (ValueError, TypeError):
        return 0.0


def _epoch_to_iso(epoch) -> str:
    """Convert Unix epoch (float or string) to ISO date string for display."""
    try:
        val = float(epoch) if epoch else 0.0
        if val > 0:
            return datetime.fromtimestamp(val, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")
        return ""
    except (ValueError, TypeError, OSError):
        return str(epoch)


def _get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(REGISTRY_DB)
    conn.row_factory = sqlite3.Row
    return conn


def _search(
    query: str = "",
    sample: str = "",
    experiment: str = "",
    date_from: str = "",
    date_to: str = "",
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """Query qcodes_registry with optional filters."""
    if not os.path.exists(REGISTRY_DB):
        return []

    conditions = []
    params: list = []

    if query:
        conditions.append(
            "(exp_name LIKE ? OR sample_name LIKE ? OR run_name LIKE ? OR parameters LIKE ?)"
        )
        q = f"%{query}%"
        params.extend([q, q, q, q])

    if sample:
        conditions.append("sample_name LIKE ?")
        params.append(f"%{sample}%")

    if experiment:
        conditions.append("exp_name LIKE ?")
        params.append(f"%{experiment}%")

    if date_from:
        conditions.append("completed_timestamp >= ?")
        params.append(_iso_to_epoch(date_from))

    if date_to:
        conditions.append("completed_timestamp <= ?")
        params.append(_iso_to_epoch(date_to + "T23:59:59"))

    where = " AND ".join(conditions) if conditions else "1=1"
    limit = min(max(1, limit), MAX_RESULTS)

    sql = f"""
        SELECT db_path, run_id, exp_name, sample_name, run_name,
               parameters, completed_timestamp
        FROM qcodes_registry
        WHERE {where}
        ORDER BY completed_timestamp DESC
        LIMIT ?
    """
    params.append(limit)

    conn = _get_db()
    try:
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _format_results(rows: List[Dict[str, Any]]) -> str:
    """Format query results as JSON string for tool output."""
    if not rows:
        return json.dumps({"result": "No matching measurements found.", "count": 0})

    results = []
    for r in rows:
        results.append({
            "db_path": r["db_path"],
            "run_id": r["run_id"],
            "experiment": r["exp_name"],
            "sample": r["sample_name"],
            "run_name": r["run_name"],
            "parameters": r["parameters"],
            "timestamp": _epoch_to_iso(r["completed_timestamp"]),
        })

    return json.dumps({"results": results, "count": len(results)})


# ---------------------------------------------------------------------------
# Tool handler
# ---------------------------------------------------------------------------


def _handle_qcodes_search(args: Dict[str, Any]) -> str:
    """Handle qcodes_search tool call."""
    try:
        rows = _search(
            query=args.get("query", ""),
            sample=args.get("sample", ""),
            experiment=args.get("experiment", ""),
            date_from=args.get("date_from", ""),
            date_to=args.get("date_to", ""),
            limit=args.get("limit", 20),
        )
        return _format_results(rows)
    except Exception as e:
        return json.dumps({"error": str(e)})


# ---------------------------------------------------------------------------
# Plugin registration
# ---------------------------------------------------------------------------


def register(ctx) -> None:
    """Register QCoDeS search tool via Hermes plugin system."""
    ctx.register_tool(
        name="qcodes_search",
        toolset="qnoe-lab",
        schema=QCODES_SEARCH_SCHEMA,
        handler=_tool_handler,
        description="Search QCoDeS measurement registry",
    )


def _tool_handler(args: Dict[str, Any] = None, **kwargs) -> str:
    """Hermes tool handler wrapper."""
    if args is None:
        args = kwargs
    return _handle_qcodes_search(args)
