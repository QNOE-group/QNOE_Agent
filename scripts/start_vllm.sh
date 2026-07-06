#!/bin/bash
exec /opt/qnoe-agent/venv/bin/vllm serve /opt/qnoe-agent/models/hermes-3-70b-awq --host 0.0.0.0 --port 8000 --quantization awq_marlin --max-model-len 32768
