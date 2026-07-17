#!/bin/bash
# Gated launcher for the targeted SharePoint re-ingest (groups B/C/D from the
# 2026-07-16 coverage audit — real PDFs/theses/pptx/ipynb/docx/py/md, plot
# exports excluded via the build step).
#
# Waits for the full-server re-ingest sprint to finish (never compete for RAM
# with it — Docling spikes 4-5 GB/worker and the box swap-death is fatal, M39),
# then runs the manifest through sharepoint_sync._process_item with a 30-min
# per-file chunk cap and the fast pypdf text-layer route.
#
# Run as yzamir (same uid as the manifest writers):
#   nohup bash /opt/qnoe-agent/scripts/run_sp_manifest_reingest.sh \
#       > /home/yzamir/sp_reingest.log 2>&1 &
# Resume after a crash: just re-run — etag dedup skips completed files.
set -u

echo "[gate] waiting for parallel_server_ingest to finish..."
while pgrep -f 'parallel_server_inges[t]' > /dev/null; do sleep 300; done
echo "[gate] sprint done. waiting for >= 30 GB free RAM..."
while [ "$(free -g | awk '/^Mem:/{print $7}')" -lt 30 ]; do sleep 120; done
echo "[gate] clear ($(free -g | awk '/^Mem:/{print $7}') GB available). starting."

set -a
source /opt/qnoe-agent/secrets/sharepoint.env
set +a

export PYTHONPATH=/opt/qnoe-agent
export PDF_TEXTLAYER_FAST=1        # born-digital PDFs via pypdf (theses fly)
export SP_FILE_CHUNK_TIMEOUT=1800  # 300 -> 1800s for Docling fallback cases
export SP_THREAD_WORKERS=3         # conservative; guard below is the backstop
export SP_MIN_FREE_GB=20

exec /opt/qnoe-agent/venv/bin/python \
    /opt/qnoe-agent/scripts/sp_manifest_reingest.py --execute
