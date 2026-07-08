"""QNOE RAG memory provider plugin for Hermes Agent.

Provides Qdrant-based retrieval-augmented generation with nomic-embed
embeddings and cross-encoder reranking. Integrates as a Hermes
MemoryProvider so RAG context is injected automatically every turn,
and also exposes an explicit ``rag_search`` tool the agent can call.

Collection routing per profile:
  qnoe-orchestrator  -> all collections
  qnoe-qtm           -> qtm, group-wide, qcodes-runs
  qnoe-photocurrent  -> photocurrent, group-wide, qcodes-runs
  (other)             -> group-wide, qcodes-runs
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
from functools import lru_cache
from typing import Any, Dict, List, Optional

from agent.memory_provider import MemoryProvider

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Environment / paths
# ---------------------------------------------------------------------------

os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("HF_DATASETS_OFFLINE", "1")
os.environ.setdefault("HF_HUB_OFFLINE", "1")

QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6333")
EMBED_MODEL_PATH = os.environ.get(
    "EMBED_MODEL_PATH", "/opt/qnoe-agent/models/nomic-embed"
)
RERANK_MODEL_PATH = os.environ.get(
    "RERANK_MODEL_PATH", "/opt/qnoe-agent/models/cross-encoder-msmarco"
)

TOP_K = 5
TOP_K_PER_COLLECTION = 20
RERANK_POOL = 20
RERANK_THRESHOLD = 0.5

# Profile name -> list of Qdrant collections to search
ALL_COLLECTIONS = [
    "group-wide", "qtm", "photocurrent", "qed",
    "superconductivity", "qsim", "xchiral", "qcodes-runs",
]

PROFILE_COLLECTIONS: Dict[str, List[str]] = {
    "qnoe-orchestrator": ALL_COLLECTIONS,
    "qnoe-qtm": ["qtm", "group-wide", "qcodes-runs"],
    "qnoe-photocurrent": ["photocurrent", "group-wide", "qcodes-runs"],
    "qnoe-qed": ["qed", "group-wide", "qcodes-runs"],
    "qnoe-superconductivity": ["superconductivity", "group-wide", "qcodes-runs"],
    "qnoe-qsim": ["qsim", "group-wide", "qcodes-runs"],
    "qnoe-xchiral": ["xchiral", "group-wide", "qcodes-runs"],
}

DEFAULT_COLLECTIONS = ["group-wide", "qcodes-runs"]

# ---------------------------------------------------------------------------
# Model loading (cached singletons)
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _load_embed_model():
    from sentence_transformers import SentenceTransformer

    logger.info("Loading nomic-embed from %s", EMBED_MODEL_PATH)
    return SentenceTransformer(
        EMBED_MODEL_PATH, trust_remote_code=True, device="cpu"
    )


@lru_cache(maxsize=1)
def _load_reranker():
    from sentence_transformers import CrossEncoder

    logger.info("Loading cross-encoder from %s", RERANK_MODEL_PATH)
    return CrossEncoder(RERANK_MODEL_PATH, device="cpu")


@lru_cache(maxsize=1)
def _get_qdrant():
    from qdrant_client import AsyncQdrantClient

    return AsyncQdrantClient(url=QDRANT_URL)


@lru_cache(maxsize=1)
def _load_sparse_model():
    from fastembed import SparseTextEmbedding

    return SparseTextEmbedding(model_name="Qdrant/bm25")


def _embed_sparse_query(text: str):
    return next(iter(_load_sparse_model().embed([text])))


# ---------------------------------------------------------------------------
# Retrieval helpers
# ---------------------------------------------------------------------------


def _embed_query(text: str) -> list[float]:
    model = _load_embed_model()
    return model.encode(
        f"search_query: {text}", normalize_embeddings=True
    ).tolist()


def _rerank(query: str, chunks: list[dict], top_k: int = TOP_K) -> list[dict]:
    if not chunks:
        return []
    reranker = _load_reranker()
    pairs = [(query, c["text"]) for c in chunks]
    scores = reranker.predict(pairs)
    for chunk, score in zip(chunks, scores):
        chunk["rerank_score"] = float(score)
    ranked = sorted(chunks, key=lambda c: c["rerank_score"], reverse=True)
    return ranked[:top_k]


def _score_to_chunk(point, collection: str) -> dict:
    payload = point.payload or {}
    return {
        "score": point.score,
        "collection": collection,
        "text": payload.get("text", ""),
        "source": payload.get("source", ""),
        "repo": payload.get("repo", ""),
        "chunk_type": payload.get("chunk_type", "prose"),
    }


async def _retrieve(query: str, collections: list[str]) -> list[dict]:
    """Hybrid (dense + BM25 sparse) retrieval across collections with RRF and reranking."""
    if not collections:
        return []

    from qdrant_client.models import Prefetch, FusionQuery, Fusion, SparseVector

    loop = asyncio.get_running_loop()
    dense_vec, sparse_emb = await asyncio.gather(
        loop.run_in_executor(None, _embed_query, query),
        loop.run_in_executor(None, _embed_sparse_query, query),
    )
    qdrant = _get_qdrant()

    async def _query_one(coll: str) -> list[dict]:
        try:
            result = await qdrant.query_points(
                collection_name=coll,
                prefetch=[
                    Prefetch(query=dense_vec, limit=TOP_K_PER_COLLECTION),
                    Prefetch(
                        query=SparseVector(
                            indices=sparse_emb.indices.tolist(),
                            values=sparse_emb.values.tolist(),
                        ),
                        using="text-sparse",
                        limit=TOP_K_PER_COLLECTION,
                    ),
                ],
                query=FusionQuery(fusion=Fusion.RRF),
                limit=TOP_K_PER_COLLECTION,
                with_payload=True,
            )
            return [_score_to_chunk(h, coll) for h in result.points]
        except Exception as exc:
            logger.warning("Qdrant hybrid search failed for %s: %s", coll, exc)
            return []

    per_collection = await asyncio.gather(
        *(_query_one(c) for c in collections)
    )
    all_results = [chunk for batch in per_collection for chunk in batch]

    if not all_results:
        return []

    # Deduplicate by (source, text prefix)
    seen: set[str] = set()
    deduped: list[dict] = []
    for chunk in sorted(all_results, key=lambda c: c["score"], reverse=True):
        key = chunk["source"] + chunk["text"][:80]
        if key not in seen:
            seen.add(key)
            deduped.append(chunk)

    pool = deduped[:RERANK_POOL]
    top = await loop.run_in_executor(None, _rerank, query, pool, TOP_K)

    if not top or top[0].get("rerank_score", 0) < RERANK_THRESHOLD:
        return []

    # Anti-lost-in-middle ordering
    if len(top) >= 2:
        return [top[0]] + top[2:] + [top[1]]
    return top


def _run_retrieve(query: str, collections: list[str]) -> list[dict]:
    """Synchronous wrapper around the async retrieval."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # Already in an async context — run in a new thread with its own loop
        result: list[dict] = []

        def _worker():
            nonlocal result
            result = asyncio.run(_retrieve(query, collections))

        t = threading.Thread(target=_worker, daemon=True)
        t.start()
        t.join(timeout=30)
        return result
    else:
        return asyncio.run(_retrieve(query, collections))


def _format_chunks(chunks: list[dict]) -> str:
    """Format retrieved chunks as context text."""
    if not chunks:
        return ""
    lines = []
    for i, c in enumerate(chunks, 1):
        source = c.get("source", "unknown")
        coll = c.get("collection", "")
        score = c.get("rerank_score", c.get("score", 0))
        lines.append(f"[{i}] ({coll}) {source} (score: {score:.2f})")
        lines.append(c["text"])
        lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tool schemas
# ---------------------------------------------------------------------------

RAG_SEARCH_SCHEMA = {
    "name": "rag_search",
    "description": (
        "Search the QNOE lab knowledge base (papers, code, documentation, "
        "measurement data). Returns relevant chunks from Qdrant collections "
        "with cross-encoder reranking. Use when you need specific information "
        "about lab code, papers, experiments, or measurement data."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Natural language search query.",
            },
            "collection": {
                "type": "string",
                "description": (
                    "Optional: specific collection to search. "
                    "One of: group-wide, qtm, photocurrent, qed, "
                    "superconductivity, qsim, xchiral, qcodes-runs. "
                    "If omitted, searches all collections for your profile."
                ),
            },
        },
        "required": ["query"],
    },
}


# ---------------------------------------------------------------------------
# MemoryProvider implementation
# ---------------------------------------------------------------------------


class QnoeRagProvider(MemoryProvider):
    """Qdrant RAG retrieval as a Hermes memory provider."""

    def __init__(self):
        self._collections: list[str] = DEFAULT_COLLECTIONS
        self._profile: str = ""
        self._prefetch_result: str = ""
        self._prefetch_lock = threading.Lock()
        self._prefetch_thread: Optional[threading.Thread] = None

    @property
    def name(self) -> str:
        return "qnoe_rag"

    def is_available(self) -> bool:
        try:
            import requests

            r = requests.get(f"{QDRANT_URL}/collections", timeout=3)
            return r.status_code == 200
        except Exception:
            return False

    def initialize(self, session_id: str, **kwargs) -> None:
        self._profile = kwargs.get("agent_identity", "")
        self._collections = PROFILE_COLLECTIONS.get(
            self._profile, DEFAULT_COLLECTIONS
        )
        logger.info(
            "QnoeRag initialized for profile=%s, collections=%s",
            self._profile,
            self._collections,
        )

    def system_prompt_block(self) -> str:
        colls = ", ".join(self._collections)
        return (
            "# QNOE RAG Knowledge Base\n"
            f"Active collections: {colls}\n"
            "RAG context is automatically injected each turn. "
            "Use the rag_search tool for explicit targeted queries."
        )

    def prefetch(self, query: str, *, session_id: str = "") -> str:
        # Wait for background prefetch if running
        if self._prefetch_thread and self._prefetch_thread.is_alive():
            self._prefetch_thread.join(timeout=10.0)

        with self._prefetch_lock:
            result = self._prefetch_result
            self._prefetch_result = ""

        if not result:
            # No prefetch available — do synchronous retrieval
            chunks = _run_retrieve(query, self._collections)
            result = _format_chunks(chunks)

        if not result:
            return ""
        return f"## RAG Context\n{result}"

    def queue_prefetch(self, query: str, *, session_id: str = "") -> None:
        def _run():
            try:
                chunks = _run_retrieve(query, self._collections)
                formatted = _format_chunks(chunks)
                with self._prefetch_lock:
                    self._prefetch_result = formatted
            except Exception as e:
                logger.warning("RAG prefetch failed: %s", e)

        self._prefetch_thread = threading.Thread(
            target=_run, daemon=True, name="rag-prefetch"
        )
        self._prefetch_thread.start()

    def sync_turn(
        self,
        user_content: str,
        assistant_content: str,
        *,
        session_id: str = "",
        messages: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        # RAG is read-only — no writes needed
        pass

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        return [RAG_SEARCH_SCHEMA]

    def handle_tool_call(self, tool_name: str, args: dict, **kwargs) -> str:
        if tool_name != "rag_search":
            return json.dumps({"error": f"Unknown tool: {tool_name}"})

        query = args.get("query", "")
        if not query:
            return json.dumps({"error": "Missing required parameter: query"})

        # Optional collection filter
        collection = args.get("collection")
        if collection:
            if collection not in ALL_COLLECTIONS:
                return json.dumps({
                    "error": f"Unknown collection: {collection}. "
                    f"Valid: {', '.join(ALL_COLLECTIONS)}"
                })
            collections = [collection]
        else:
            collections = self._collections

        chunks = _run_retrieve(query, collections)

        if not chunks:
            return json.dumps({
                "result": "No relevant results found.",
                "collections_searched": collections,
            })

        results = []
        for c in chunks:
            results.append({
                "source": c.get("source", ""),
                "collection": c.get("collection", ""),
                "score": round(c.get("rerank_score", c.get("score", 0)), 3),
                "text": c["text"][:1500],  # cap per-chunk size
            })

        return json.dumps({
            "results": results,
            "count": len(results),
            "collections_searched": collections,
        })

    def shutdown(self) -> None:
        if self._prefetch_thread and self._prefetch_thread.is_alive():
            self._prefetch_thread.join(timeout=5.0)


def register(ctx) -> None:
    """Register QNOE RAG as a memory provider plugin."""
    ctx.register_memory_provider(QnoeRagProvider())
