#!/bin/bash
# Gated launcher for the targeted SharePoint re-ingest (groups B/C/D from the
# 2026-07-16 coverage audit — real PDFs/theses/pptx/ipynb/docx/py/md, plot
# exports excluded via the build step).
#
# Waits for the full-server re-ingest sprint to finish (never compete for RAM
# with it — Docling spikes 4-5 GB/worker and the box swap-death is fatal, M39),
# then runs the manifest under a MEMORY-GATED SEMAPHORE over recycled
# subprocess batches (the parallel_server_ingest model): a new batch launches
# only when (running < WORKERS) AND (free RAM >= MIN_FREE_GB); each batch is a
# fresh process that exits when done, so memory is recycled. 30-min per-file
# chunk cap; born-digital PDFs take the fast pypdf route.
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
export WORKERS=6                   # semaphore: max concurrent batch processes
export BATCH_SIZE=25               # items per fresh subprocess (memory recycled)
export MIN_FREE_GB=25              # do not launch a new batch below this

exec /opt/qnoe-agent/venv/bin/python \
    /opt/qnoe-agent/scripts/sp_manifest_reingest.py --execute
