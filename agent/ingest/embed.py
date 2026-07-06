"""Embedding functions for ingestion pipeline.

nomic-embed-text-v1.5 is used for all content (prose and code).

Document prefix: "search_document: " (required by nomic-embed for indexing)
Query prefix:    "search_query: "    (used in retrieval.py)
"""
import os
import logging
from functools import lru_cache

from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("HF_DATASETS_OFFLINE", "1")
os.environ.setdefault("HF_HUB_OFFLINE", "1")

EMBED_MODEL_PATH = os.environ.get(
    "EMBED_MODEL_PATH", "/opt/qnoe-agent/models/nomic-embed"
)
EMBED_BATCH_SIZE = 64
VECTOR_DIM = 768


@lru_cache(maxsize=1)
def load_model() -> SentenceTransformer:
    logger.info("Loading embedding model from %s", EMBED_MODEL_PATH)
    return SentenceTransformer(EMBED_MODEL_PATH, trust_remote_code=True, device="cpu")


def embed_documents(texts: list[str]) -> list[list[float]]:
    """Embed a list of document strings (with search_document prefix)."""
    model = load_model()
    prefixed = [f"search_document: {t}" for t in texts]
    vectors = model.encode(
        prefixed,
        batch_size=EMBED_BATCH_SIZE,
        normalize_embeddings=True,
        show_progress_bar=len(texts) > 100,
    )
    return [v.tolist() for v in vectors]
