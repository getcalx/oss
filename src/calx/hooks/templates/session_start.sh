#!/usr/bin/env bash
# Calx session-start hook — fires once on SessionStart
set -euo pipefail

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
SESSION_ID="${CLAUDE_SESSION_ID:-$$}"
PROJECT_HASH=$(echo -n "$PROJECT_DIR" | shasum -a 256 | cut -c1-12)
MARKER="/tmp/calx-oriented-${PROJECT_HASH}-${SESSION_ID}"

touch "$MARKER"

calx _hook session-start 2>/dev/null || true
exit 0
