#!/usr/bin/env bash
# Calx collapse guard — PreToolUse on Edit|Write
# Warns on >20% shrink of protected files. Advisory only — always exits 0.

INPUT=$(cat)

file_path=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty' 2>/dev/null)
[[ -z "$file_path" ]] && exit 0

# Only guard protected files
case "$file_path" in
  */.calx/rules/*|*/.calx/method/*|*/CLAUDE.md) ;;
  *) exit 0 ;;
esac

[[ ! -f "$file_path" ]] && exit 0

current_lines=$(wc -l < "$file_path" | tr -d ' ')
[[ "$current_lines" -eq 0 ]] && exit 0

tool_name=$(echo "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)

if [[ "$tool_name" == "Write" ]]; then
  new_lines=$(echo "$INPUT" | jq -r '.tool_input.content // empty' 2>/dev/null | wc -l | tr -d ' ')
elif [[ "$tool_name" == "Edit" ]]; then
  old_lines=$(echo "$INPUT" | jq -r '.tool_input.old_string // empty' 2>/dev/null | wc -l | tr -d ' ')
  new_edit_lines=$(echo "$INPUT" | jq -r '.tool_input.new_string // empty' 2>/dev/null | wc -l | tr -d ' ')
  delta=$((new_edit_lines - old_lines))
  new_lines=$((current_lines + delta))
else
  exit 0
fi

threshold=$((current_lines * 80 / 100))
if [[ "${new_lines:-0}" -lt "$threshold" ]]; then
  printf '{"systemMessage":"CONTEXT COLLAPSE WARNING: %s would shrink from %d to ~%d lines (>20%% reduction). Review before proceeding."}\n' \
    "$(basename "$file_path")" "$current_lines" "$new_lines"
fi

exit 0
