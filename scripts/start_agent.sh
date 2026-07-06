#!/bin/bash
source /home/qnoe-ai/.profile
export OPENSHELL_LOCAL_TLS_DIR=/home/qnoe-ai/.local/state/openshell/tls

# Remove any stale sandbox from a previous run
openshell sandbox delete qnoe-agent 2>/dev/null || true

# Launch agent sandbox — blocks until python -m agent.main exits
exec openshell sandbox create \
  --name qnoe-agent \
  --from qnoe-agent:latest \
  --policy /opt/qnoe-agent/config/sandbox-policy.yaml \
  --provider local-vllm \
  --driver-config-json '{"docker":{"mounts":[{"source":"/opt/qnoe-agent","target":"/opt/qnoe-agent","type":"bind"},{"source":"/ICFO/groups/NOE","target":"/ICFO/groups/NOE","type":"bind","read_only":true}]}}' \
  -- bash -c "cd /opt/qnoe-agent && \
    VLLM_BASE_URL=https://inference.local/v1 \
    QDRANT_URL=http://172.18.0.1:6333 \
    AGENT_DATA_DIR=/opt/qnoe-agent/memory \
    EMBED_MODEL_PATH=/opt/qnoe-agent/models/nomic-embed \
    TRANSFORMERS_OFFLINE=1 HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 \
    /opt/qnoe-agent/venv/bin/python -m agent.main"
