#!/usr/bin/env bash
# Calx session-end hook — fires once on Stop
set -euo pipefail
calx _hook session-end 2>/dev/null || true
exit 0
