# Deploy Patterns
*Last updated: 2026-07-13 (added "DGX ≠ master — code drift is real")*

> Standard procedures for deploying code and files to the DGX.
> Ownership pitfalls: [[memory/mistakes#M11 — DGX file ownership]] · Infrastructure: [[memory/infrastructure]] · Full setup: [[DGX_SETUP]]

## Standard Deploy Flow

1. Write file locally or to `/tmp/` on DGX
2. `scp` to DGX `/tmp/` if written locally
3. `sudo cp /tmp/file /opt/qnoe-agent/target/`
4. `sudo chown -R qnoe-ai:qnoe-ai /opt/qnoe-agent/target/`
5. `sudo chmod -R g+w /opt/qnoe-agent/target/`

## Restarting Services

```bash
# Agent (Docker container)
sudo systemctl restart qnoe-agent

# Watcher daemon
sudo systemctl restart qnoe-watcher

# vLLM — AVOID unless absolutely necessary (5+ min reload)
sudo systemctl restart vllm
```

## File Ownership Rules

- `/opt/qnoe-agent/` owned by `qnoe-ai:qnoe-ai` (uid 1001)
- User `yzamir` is in `qnoe-ai` group but NOT owner
- Always set group write: `sudo chmod -R g+w`
- Pre-create dirs Hermes might need at runtime

## Docker Image Rebuild

```bash
cd /opt/qnoe-agent
sudo docker build -t qnoe-agent:latest .
sudo systemctl restart qnoe-agent
```

## Checking Logs

```bash
# Agent logs
tail -f /opt/qnoe-agent/logs/agent.log

# Watcher logs
journalctl -u qnoe-watcher -f

# vLLM logs
journalctl -u vllm -f

# Nightly job logs
tail -f /opt/qnoe-agent/logs/nightly_reindex.log
```

## DGX ≠ master — code drift is real (mapped 2026-07-13)

The DGX does **not** track `master`. It runs a hand-deployed mix, and several feature branches are pushed-but-never-merged (per lab convention, merges to `main`/`master` need PI approval). Before deploying, **compare `md5sum` of the target file on the DGX against the intended source** — don't assume the repo == what's running.

Snapshot when the SP-poller-reporting fix went out (2026-07-13):
- **Unmerged feature branches** (deployed on DGX in part, not on master): `feature/gpt-oss-cutover` (the inference stack actually running), `feature/mem0-per-user`, `feature/context-pressure`, `feature/gpt-oss-pilot`. `master` HEAD (`08d89a7`) predates the cutover in git even though the cutover is live on the box.
- **Uncommitted DGX-only edits** (match no commit on any branch — at risk of being clobbered by a repo redeploy; pull them back into git): `agent/ingest/clone_org.py`, `agent/ingest/ingest_server.py`.
- **DGX behind master** on the reporting files: at deploy time `sharepoint_sync.py`/`nightly_run.py` were at commit `2b7fd26` and `post_report.py` at `b5c0c78` — i.e. the committed `8109af0` "new vs updated report" feature had never been deployed. Deploying the SP-poller fix (from master) also shipped that.
- **Legacy cruft on DGX, removed from repo:** `agent/{graph,main,llm,teams,tools,state,prompts,retrieval,episodic,teams_check,__init__}.py` — pre-Hermes LangGraph modules, no longer run.

**Pin-a-file-to-a-commit recipe** (which version is deployed?): `for c in $(git log --format=%h -40 <ref> -- <file>); do [ "$(git show $c:<file>|md5sum|cut -d' ' -f1)" = "<dgx_md5>" ] && echo $c; done`. Iterate over `git for-each-ref refs/heads refs/remotes` to search all branches, not just the current one.
