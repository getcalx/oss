#!/usr/bin/env bash
# Calx orientation gate — PreToolUse on Edit|Write
# Blocks file modifications until rules have been read.
# Exit 0 = allow, Exit 2 = block with message.
set -euo pipefail

CALX_DIR="${CLAUDE_PROJECT_DIR:-.}/.calx"
SESSION_ID="${CLAUDE_SESSION_ID:-$$}"
MARKER="${CALX_DIR}/health/.session-oriented-${SESSION_ID}"

if [ -f "$MARKER" ]; then
  exit 0
fi

# Fallback: check for any recent oriented marker from this project
RECENT=$(find "${CALX_DIR}/health" -maxdepth 1 -name ".session-oriented-*" -mmin -60 2>/dev/null | head -1)
if [ -n "$RECENT" ]; then
  exit 0
fi

cat <<EOF
BLOCKED: Read project rules before editing files.

Calx requires the session-start hook to run before any file modifications.
This ensures domain rules are loaded and acknowledged.

To unblock manually: mkdir -p "${CALX_DIR}/health" && touch "$MARKER"
EOF

exit 2
