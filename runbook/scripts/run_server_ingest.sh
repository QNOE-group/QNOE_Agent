#!/bin/bash
# Run server document ingestion from /ICFO/groups/NOE into Qdrant.
# Run as yzamir (not qnoe-ai — only yzamir can read the network mount).
# Safe to re-run — hash-based dedup skips already-indexed files.
# Logs: /tmp/server_ingest.log, /tmp/empty_pdfs.log, /tmp/skipped_files.log

set -e

MOUNT_POINT=/ICFO/groups/NOE

# Check mount is available
if ! ls "$MOUNT_POINT" > /dev/null 2>&1 || [ -z "$(ls -A $MOUNT_POINT)" ]; then
    echo "ERROR: $MOUNT_POINT is not mounted or is empty. Run mount_icfo.sh first."
    exit 1
fi

mkdir -p /home/yzamir/qnoe_server_data

cd /opt/qnoe-agent
export QDRANT_URL=http://localhost:6333
export AGENT_DATA_DIR=/home/yzamir/qnoe_server_data
export EMBED_MODEL_PATH=/opt/qnoe-agent/models/nomic-embed

echo "Starting server ingestion at $(date)"
/opt/qnoe-agent/venv/bin/python -m agent.ingest.ingest_server "$@"
echo "Finished at $(date)"
