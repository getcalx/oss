#!/usr/bin/env bash
# Calx orientation gate — PreToolUse on Edit|Write
# Blocks file modifications until rules have been read.
# Exit 0 = allow, Exit 2 = block with message.
set -euo pipefail

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
SESSION_ID="${CLAUDE_SESSION_ID:-$$}"
PROJECT_HASH=$(echo -n "$PROJECT_DIR" | shasum -a 256 | cut -c1-12)
MARKER="/tmp/calx-oriented-${PROJECT_HASH}-${SESSION_ID}"

if [ -f "$MARKER" ]; then
  exit 0
fi

# Fallback: check for recent marker from same project
SEARCH_DIR="/tmp"
[[ -d /private/tmp ]] && SEARCH_DIR="/private/tmp"
RECENT=$(find "$SEARCH_DIR" -maxdepth 1 -name "calx-oriented-${PROJECT_HASH}-*" -mmin -60 2>/dev/null | head -1)
if [ -n "$RECENT" ]; then
  exit 0
fi

cat <<EOF
BLOCKED: Read project rules before editing files.

Calx requires the session-start hook to run before any file modifications.
This ensures domain rules are loaded and acknowledged.

To unblock manually: touch $MARKER
EOF

exit 2
