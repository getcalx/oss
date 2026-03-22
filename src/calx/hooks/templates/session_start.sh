#!/usr/bin/env bash
# Calx session-start hook — fires once on SessionStart
set -euo pipefail

CALX_DIR="${CLAUDE_PROJECT_DIR:-.}/.calx"
SESSION_ID="${CLAUDE_SESSION_ID:-$$}"
MARKER="${CALX_DIR}/health/.session-oriented-${SESSION_ID}"

calx _hook session-start 2>/dev/null || true

mkdir -p "${CALX_DIR}/health"
touch "$MARKER"
exit 0
