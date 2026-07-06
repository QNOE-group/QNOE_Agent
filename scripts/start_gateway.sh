#!/bin/bash
set -e
export OPENSHELL_LOCAL_TLS_DIR=/home/qnoe-ai/.local/state/openshell/tls
source /home/qnoe-ai/.profile

# Kill any existing gateway from a previous run
pkill -f openshell-gateway 2>/dev/null || true
sleep 1

# Generate fresh certs (always regenerate — stateless and safe)
rm -rf "$OPENSHELL_LOCAL_TLS_DIR"
mkdir -p "$OPENSHELL_LOCAL_TLS_DIR"
/usr/bin/openshell-gateway generate-certs \
  --output-dir "$OPENSHELL_LOCAL_TLS_DIR" \
  --server-san 127.0.0.1 \
  --server-san 172.18.0.1 \
  --server-san host.openshell.internal

# Start gateway in background so we can register the CLI
/usr/bin/openshell-gateway --drivers docker &
GATEWAY_PID=$!

# Wait for gateway to be ready, then register CLI
sleep 5
openshell gateway remove openshell 2>/dev/null || true
openshell gateway add --local https://127.0.0.1:17670

# Hold foreground — systemd tracks this process; exits when gateway exits
wait $GATEWAY_PID
