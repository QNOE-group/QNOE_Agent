#!/bin/bash
set -e

# QNOE Lab Agent — Hermes Gateway launcher
# Runs as qnoe-ai user via systemd (no Docker needed)

# Hermes home — profiles, plugins, config, memory
export HERMES_HOME=/opt/qnoe-agent/hermes

# Model paths
export EMBED_MODEL_PATH=/opt/qnoe-agent/models/nomic-embed
export RERANK_MODEL_PATH=/opt/qnoe-agent/models/cross-encoder-msmarco

# Infrastructure endpoints
export QDRANT_URL=http://localhost:6333
export VLLM_BASE_URL=http://localhost:8000/v1

# Data paths
export AGENT_DATA_DIR=/home/yzamir/qnoe_server_data

# Offline mode for transformers (models are local)
export TRANSFORMERS_OFFLINE=1
export HF_HUB_OFFLINE=1
export HF_DATASETS_OFFLINE=1

# Allow all Teams users (no allowlist filtering)
export GATEWAY_ALLOW_ALL_USERS=true

# Load Teams credentials
if [ -r /opt/qnoe-agent/secrets/teams.env ]; then
    set -a
    source /opt/qnoe-agent/secrets/teams.env
    set +a
fi

# Launch Hermes gateway (uses active profile: qnoe-orchestrator)
exec /opt/qnoe-agent/hermes-venv/bin/hermes gateway run --replace -v
