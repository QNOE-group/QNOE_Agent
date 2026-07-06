#!/bin/bash
# Hook: SessionStart — inject HOME.md into conversation context
# This ensures Claude Code always has the memory index loaded at session start.

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
HOME_MD="$PROJECT_DIR/HOME.md"

if [ -f "$HOME_MD" ]; then
  CONTENT=$(cat "$HOME_MD")
  cat <<EOF
{
  "hookSpecificOutput": {
    "hookEventName": "SessionStart",
    "additionalContext": "MEMORY SYSTEM LOADED. Contents of HOME.md (master memory index):\n\n$(echo "$CONTENT" | sed 's/\\/\\\\/g; s/"/\\"/g; s/\t/\\t/g' | sed ':a;N;$!ba;s/\n/\\n/g')"
  }
}
EOF
else
  echo '{"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": "WARNING: HOME.md not found. Memory system not loaded."}}'
fi
