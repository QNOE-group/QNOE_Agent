#!/bin/bash
# Clone all repos from the QNOE-group GitHub org.
# Requires a GitHub PAT with read:org + repo scopes at /opt/qnoe-agent/secrets/github_pat

set -e

GITHUB_TOKEN=$(cat /opt/qnoe-agent/secrets/github_pat)
REPOS_DIR=/opt/qnoe-agent/repos

mkdir -p "$REPOS_DIR"

echo "Cloning QNOE-group repos to $REPOS_DIR ..."
cd /opt/qnoe-agent
export GITHUB_TOKEN

/opt/qnoe-agent/venv/bin/python agent/ingest/clone_org.py \
    --org QNOE-group \
    --dest "$REPOS_DIR" \
    --token "$GITHUB_TOKEN"

echo "Done. Repos in $REPOS_DIR:"
ls "$REPOS_DIR"
