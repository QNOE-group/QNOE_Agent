#!/bin/bash
# gpt-oss-120b (MXFP4 MoE) served on the DGX-Spark (GB10, sm_121) via the
# venv vLLM 0.22.1. Marlin MXFP4 backend is the GB10-safe path (avoids the
# SM121 garbled-text bug class); atomic-add improves MoE throughput.
# Harmony format is auto-detected from the gpt_oss architecture, so tool calls
# and reasoning surface natively — no --tool-call-parser / --reasoning-parser
# flags required. Serves on port 8000 to keep VLLM_BASE_URL plumbing unchanged.
export VLLM_MXFP4_BACKEND=marlin
export VLLM_MARLIN_USE_ATOMIC_ADD=1
exec /opt/qnoe-agent/venv/bin/vllm serve /opt/qnoe-agent/models/gpt-oss-120b \
  --host 0.0.0.0 --port 8000 \
  --max-model-len 131072 \
  --max-num-seqs 4 \
  > /opt/qnoe-agent/logs/vllm.log 2>&1
