# User Preferences
*Last updated: 2026-07-01*

> How Yonatan works and communicates. Follow these always.

## Communication

- Concise, direct — no filler
- Lead with the answer, not the reasoning
- Design decisions documented in markdown before implementation

## Session Workflow

- Ask before SSH at start of each session — once approved, use freely
- Update SETUP_LOG.md as steps complete
- Read files before editing — never overwrite user's edits
- User often makes changes outside Claude sessions — always check current state

## DGX Rules

- **Never restart vLLM** unless absolutely necessary — 5+ min reload blocks the agent
- Fix issues at agent level if possible
- Cannot sudo non-interactively — give sudo commands to user to paste

## Deployment

- User runs deployment commands (sudo cp, chown, chmod, systemctl restart)
- Claude prepares files and gives clear copy-paste instructions
- User says "done" when deployment is complete
