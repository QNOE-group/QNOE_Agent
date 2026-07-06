# Deploy Patterns
*Last updated: 2026-07-01*

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
