#!/bin/bash
# Quick health check for all QNOE agent components.

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

ok()  { echo -e "${GREEN}[OK]${NC}  $1"; }
err() { echo -e "${RED}[FAIL]${NC} $1"; }

echo "=== QNOE Agent Health Check ==="
echo

# vLLM
if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
    ok "vLLM (port 8000)"
else
    err "vLLM (port 8000) — check: sudo systemctl status vllm"
fi

# Qdrant
if curl -sf http://localhost:6333/healthz > /dev/null 2>&1; then
    ok "Qdrant (port 6333)"
else
    err "Qdrant (port 6333) — check: docker ps"
fi

# OpenShell gateway
if sudo systemctl is-active --quiet openshell-gateway 2>/dev/null; then
    ok "OpenShell gateway (systemd)"
else
    err "OpenShell gateway — check: sudo systemctl status openshell-gateway"
fi

# Agent service
if sudo systemctl is-active --quiet qnoe-agent 2>/dev/null; then
    ok "Agent service (systemd)"
else
    echo "  [--]  Agent service not running (expected until Teams credentials wired)"
fi

# Network mount
if ls /ICFO/groups/NOE > /dev/null 2>&1 && [ -n "$(ls -A /ICFO/groups/NOE)" ]; then
    ok "Network mount (/ICFO/groups/NOE)"
else
    err "Network mount missing — run: bash runbook/scripts/mount_icfo.sh"
fi

# Qdrant collections
echo
echo "=== Qdrant collections ==="
for col in qtm photocurrent qed superconductivity qsim xchiral group-wide; do
    count=$(curl -s http://localhost:6333/collections/$col | \
        python3 -c "import sys,json; d=json.load(sys.stdin); print(d['result']['points_count'])" 2>/dev/null || echo "?")
    printf "  %-20s %s points\n" "$col" "$count"
done
