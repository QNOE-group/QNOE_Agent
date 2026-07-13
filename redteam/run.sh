#!/bin/bash
# Red-team harness launcher. MUST be invoked as qnoe-ai:
#   sudo -u qnoe-ai bash /opt/qnoe-agent/redteam/run.sh [--dry-run] [--class C] [--profile P] [--list]
# (The profile home is mode 700 — running as any other user fails on .env.)
set -euo pipefail
exec /opt/qnoe-agent/hermes-venv/bin/python3 /opt/qnoe-agent/redteam/runner.py "$@"
