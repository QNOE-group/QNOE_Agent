#!/bin/bash
source /home/qnoe-ai/.profile
export OPENSHELL_LOCAL_TLS_DIR=/home/qnoe-ai/.local/state/openshell/tls
openshell sandbox create \
  --name qnoe-agent \
  --from qnoe-agent:latest \
  --policy /opt/qnoe-agent/config/sandbox-policy.yaml \
  --provider local-vllm \
  --driver-config-json '{"docker":{"mounts":[{"source":"/opt/qnoe-agent","target":"/opt/qnoe-agent","type":"bind"},{"source":"/ICFO/groups/NOE","target":"/ICFO/groups/NOE","type":"bind","read_only":true}]}}' \
  -- echo "sandbox ok"
