#!/usr/bin/env bash
# Calx orientation gate — PreToolUse on Edit|Write
# Blocks file modifications until rules have been read.
# Exit 0 = allow, Exit 2 = block with message.

CALX_DIR="${CLAUDE_PROJECT_DIR:-.}/.calx"

# Check for any recent oriented marker from this project
if [ -d "${CALX_DIR}/health" ]; then
  RECENT=$(find "${CALX_DIR}/health" -maxdepth 1 -name ".session-oriented-*" -mmin -60 2>/dev/null | head -1)
  if [ -n "$RECENT" ]; then
    exit 0
  fi
fi

cat <<EOF
BLOCKED: Read project rules before editing files.

Calx requires the session-start hook to run before any file modifications.
This ensures domain rules are loaded and acknowledged.

To unblock manually: mkdir -p "${CALX_DIR}/health" && touch "${CALX_DIR}/health/.session-oriented-manual"
EOF

exit 2
