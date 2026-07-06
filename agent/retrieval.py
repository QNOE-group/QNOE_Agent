"""Qdrant RAG retrieval using nomic-embed-text-v1.5 + cross-encoder reranker.

Retrieval flow:
  1. Embed query with nomic-embed (search_query prefix)
  2. Query each collection for this agent, top-20 each
  3. Merge by score, deduplicate
  4. Take top-20 candidates, rerank with cross-encoder
  5. Return top-5 by cross-encoder score
  6. If best rerank score < RERANK_THRESHOLD → return empty list
"""
import asyncio
import os
import logging
from functools import lru_cache

from qdrant_client import AsyncQdrantClient
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

# Never call HuggingFace Hub — all models are local
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


@lru_cache(maxsize=1)
def _load_reranker():
    from sentence_transformers import CrossEncoder
    logger.info("Loading cross-encoder from %s", RERANK_MODEL_PATH)
    return CrossEncoder(RERANK_MODEL_PATH, device="cpu")


def _rerank(query: str, chunks: list[dict], top_k: int = TOP_K) -> list[dict]:
    """Re-score chunks using cross-encoder and return top-k."""
    if not chunks:
        return []
    reranker = _load_reranker()
    pairs = [(query, c["text"]) for c in chunks]
    scores = reranker.predict(pairs)
    for chunk, score in zip(chunks, scores):
        chunk["rerank_score"] = float(score)
    ranked = sorted(chunks, key=lambda c: c["rerank_score"], reverse=True)
    return ranked[:top_k]


@lru_cache(maxsize=1)
def _load_model() -> SentenceTransformer:
    logger.info("Loading nomic-embed from %s", EMBED_MODEL_PATH)
    model = SentenceTransformer(EMBED_MODEL_PATH, trust_remote_code=True, device="cpu")
    return model


@lru_cache(maxsize=1)
def _get_qdrant() -> AsyncQdrantClient:
    return AsyncQdrantClient(url=QDRANT_URL)


def _embed_query(text: str) -> list[float]:
    # nomic-embed uses task-specific prefix for retrieval queries
    model = _load_model()
    return model.encode(f"search_query: {text}", normalize_embeddings=True).tolist()


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


async def retrieve(query: str, collections: list[str]) -> list[dict]:
    """Return top-K chunks across given collections.

    Returns an empty list if best rerank score < RERANK_THRESHOLD.
    """
    if not collections:
        return []

    loop = asyncio.get_running_loop()
    vector = await loop.run_in_executor(None, _embed_query, query)
    qdrant = _get_qdrant()

    async def _query_one(coll: str) -> list[dict]:
        try:
            result = await qdrant.query_points(
                collection_name=coll,
                query=vector,
                limit=TOP_K_PER_COLLECTION,
                with_payload=True,
            )
            return [_score_to_chunk(h, coll) for h in result.points]
        except Exception as exc:
            logger.warning("Qdrant search failed for collection %s: %s", coll, exc)
            return []

    per_collection = await asyncio.gather(*(_query_one(c) for c in collections))
    all_results: list[dict] = [chunk for batch in per_collection for chunk in batch]

    if not all_results:
        return []

    # Sort by score descending, deduplicate by (source, text prefix)
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

    # Anti-lost-in-middle ordering: rank-1 first, rank-2 last, rest in middle
    if len(top) >= 2:
        reordered = [top[0]] + top[2:] + [top[1]]
    else:
        reordered = top

    return reordered
