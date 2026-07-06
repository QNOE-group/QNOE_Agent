#!/bin/bash
# Hook: PreCompact — remind Claude to save learnings before context compaction
# Outputs a reminder that gets injected into the conversation before compaction happens.

cat <<'EOF'
{
  "hookSpecificOutput": {
    "hookEventName": "PreCompact",
    "additionalContext": "CONTEXT COMPACTION IMMINENT. Before compaction, save any important learnings from this session to the Obsidian memory system:\n\n- New bugs or pitfalls → memory/mistakes.md\n- Architecture decisions → memory/decisions.md\n- Infrastructure changes → memory/infrastructure.md\n- Agent code changes → memory/agent-code.md\n- Ingestion/RAG changes → memory/ingestion.md\n- Hermes migration progress → memory/hermes-migration.md\n- Deploy procedure updates → memory/deploy-patterns.md\n- Update 'Last updated' dates on any files you modify.\n\nDo this NOW before the context is lost."
  }
}
EOF
