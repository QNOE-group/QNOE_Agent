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
# Mem0 fact-extraction LLM — must match the vLLM served model id exactly
export MEM0_LLM_MODEL=gpt-oss-120b

# Data paths
export AGENT_DATA_DIR=/home/yzamir/qnoe_server_data

# Offline mode for transformers (models are local)
export TRANSFORMERS_OFFLINE=1
export HF_HUB_OFFLINE=1
export HF_DATASETS_OFFLINE=1

# Allow all Teams users (no allowlist filtering)
export GATEWAY_ALLOW_ALL_USERS=true

# Home channel for cron job delivery and cross-platform messages (Yuval's DM)
export TEAMS_POLLING_HOME_CHANNEL="19:862ec907-3e65-4c00-aa0c-02948656ae7f_aa2b5ee6-797a-4d95-9cf2-485c04f3958e@unq.gbl.spaces"

# Load Teams credentials.
# Under the B7-sandboxed unit (see 50-b7-readonly.conf), secrets/ is
# InaccessiblePaths= and systemd delivers teams.env via LoadCredential=
# ($CREDENTIALS_DIRECTORY). The direct path is kept as fallback so the bare
# (rollback) unit still works.
if [ -n "${CREDENTIALS_DIRECTORY:-}" ] && [ -r "${CREDENTIALS_DIRECTORY}/teams.env" ]; then
    set -a
    source "${CREDENTIALS_DIRECTORY}/teams.env"
    set +a
elif [ -r /opt/qnoe-agent/secrets/teams.env ]; then
    set -a
    source /opt/qnoe-agent/secrets/teams.env
    set +a
fi

# Launch Hermes gateway (uses active profile: qnoe-orchestrator)
exec /opt/qnoe-agent/hermes-venv/bin/hermes gateway run --replace -v
