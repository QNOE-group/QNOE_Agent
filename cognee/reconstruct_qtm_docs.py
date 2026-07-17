#!/usr/bin/env python3
"""Reconstruct QTM + QTOM SharePoint documents from their indexed Qdrant chunks.

Source selection is PRECISE (no text search): the SharePoint manifest
(`sp_manifest`) lists every indexed item with its folder `item_path` and the
exact `point_ids` of its chunks in Qdrant. We take the QTM/ and QTOM/ shared
folders and pull each file's chunks by id, so nothing is re-fetched from
SharePoint and no fuzzy `source` match is used.

Chunk ordering: SP-doc chunks have no `start_line`, so we preserve the manifest
`point_ids` order (the ingest/chunk order) and index the retrieved points back
onto it (Qdrant `retrieve` does not guarantee input order).

Usage (DGX):
  /home/yzamir/cognee-pilot/venv/bin/python reconstruct_qtm_docs.py \
      --out /home/yzamir/cognee-pilot/output/qtm_docs.jsonl [--limit 0] [--min-chars 200]
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sqlite3
import sys

MANIFEST_DB = os.environ.get("SP_MANIFEST_DB", "/opt/qnoe-agent/memory/sharepoint.db")
QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6333")

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("reconstruct_qtm_docs")


def load_manifest_items(db: str) -> list[dict]:
    """QTM/ + QTOM/ items from sp_manifest (read-only)."""
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        rows = con.execute(
            "SELECT item_id, item_path, web_url, collection, point_ids "
            "FROM sp_manifest "
            "WHERE item_path LIKE 'QTM/%' OR item_path LIKE 'QTOM/%' "
            "ORDER BY item_path"
        ).fetchall()
    finally:
        con.close()
    items = []
    for item_id, item_path, web_url, collection, pids in rows:
        try:
            point_ids = json.loads(pids) if isinstance(pids, str) else list(pids or [])
        except (json.JSONDecodeError, TypeError):
            point_ids = [p.strip() for p in str(pids).split(",") if p.strip()]
        items.append({
            "item_id": item_id, "item_path": item_path, "web_url": web_url,
            "collection": collection, "point_ids": point_ids,
        })
    return items


def _dedup_join(chunks: list[str]) -> str:
    """Concatenate chunks, trimming any overlap between consecutive chunks."""
    out = ""
    for ch in chunks:
        ch = ch or ""
        if out:
            # find the largest suffix of `out` that prefixes `ch` (cap 400)
            k = min(len(out), len(ch), 400)
            ov = 0
            for n in range(k, 20, -1):
                if out[-n:] == ch[:n]:
                    ov = n
                    break
            ch = ch[ov:]
        out += ("\n" if out and not out.endswith("\n") else "") + ch
    return out.strip()


def reconstruct(qc, item: dict) -> dict:
    from qdrant_client import QdrantClient  # noqa: F401 (client passed in)
    pids = item["point_ids"]
    if not pids:
        return {**item, "n_chunks": 0, "chars": 0, "text": ""}
    pts = qc.retrieve(collection_name=item["collection"], ids=pids,
                      with_payload=True, with_vectors=False)
    by_id = {str(p.id): p.payload for p in pts}
    ordered = [by_id[str(pid)] for pid in pids if str(pid) in by_id]
    prose = [pl.get("text", "") for pl in ordered
             if (pl.get("chunk_type") or "prose") == "prose"]
    text = _dedup_join(prose)
    return {
        "item_path": item["item_path"], "web_url": item["web_url"],
        "collection": item["collection"], "n_chunks": len(prose),
        "chars": len(text), "text": text,
    }


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="output/qtm_docs.jsonl")
    ap.add_argument("--limit", type=int, default=0, help="0 = all")
    ap.add_argument("--min-chars", type=int, default=200,
                    help="skip reconstructed docs shorter than this")
    args = ap.parse_args(argv)

    from qdrant_client import QdrantClient
    qc = QdrantClient(url=QDRANT_URL)

    items = load_manifest_items(MANIFEST_DB)
    if args.limit:
        items = items[: args.limit]
    logger.info("manifest QTM/QTOM items: %d", len(items))

    kept, skipped_small, skipped_empty = 0, 0, 0
    total_chars = 0
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        for it in items:
            doc = reconstruct(qc, it)
            if doc["n_chunks"] == 0:
                skipped_empty += 1
                continue
            if doc["chars"] < args.min_chars:
                skipped_small += 1
                continue
            fh.write(json.dumps(doc, ensure_ascii=False) + "\n")
            kept += 1
            total_chars += doc["chars"]

    logger.info("reconstructed docs: %d kept, %d empty, %d below --min-chars",
                kept, skipped_empty, skipped_small)
    logger.info("total chars: %d (~%d tokens rough)", total_chars, total_chars // 4)
    logger.info("wrote %s", args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
