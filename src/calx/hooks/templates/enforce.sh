#!/bin/sh
# Calx enforcement gate -- PreToolUse on Edit|Write
# Checks orientation, increments tool call count, runs collapse guard.
# Exit 0 = allow, Exit 2 = block.
python3 -m calx.serve.hooks.enforce "$@" 2>>.calx/hook-errors.log
