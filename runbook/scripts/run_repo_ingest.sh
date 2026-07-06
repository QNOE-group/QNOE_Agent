#!/bin/bash
# Ingest all cloned GitHub repos into Qdrant.
# Run as yzamir or qnoe-ai.
# Safe to re-run — hash-based dedup skips unchanged files.

set -e

cd /opt/qnoe-agent
export QDRANT_URL=http://localhost:6333
export AGENT_DATA_DIR=/opt/qnoe-agent/memory
export EMBED_MODEL_PATH=/opt/qnoe-agent/models/nomic-embed
export TRANSFORMERS_OFFLINE=1
export HF_HUB_OFFLINE=1

echo "Starting repo ingestion at $(date)"
/opt/qnoe-agent/venv/bin/python -m agent.ingest.ingest_all \
    --repos-dir /opt/qnoe-agent/repos \
    --config /opt/qnoe-agent/config/repo_collections.yaml \
    "$@"
echo "Finished at $(date)"
