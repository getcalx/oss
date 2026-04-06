# getcalx (OSS)

## What This Is

The open-source Calx SDK. Behavioral governance for AI agents. Ships as `getcalx` on PyPI (v0.7.2, MIT licensed, 825 installs/week, 672 tests).

This is the downstream OSS extract. Upstream development happens in ~/calx/ (private, getcalx/calx). Mara extracts OSS scope from upstream to here for testing and PyPI publishing.

## Agent: Mara (OSS Lead)

Full agent definition: ~/.claude/agents/oss-lead.md
ACE artifacts: ~/ops/agents/mara/rules.md, ~/ops/agents/mara/lessons.md

Read the agent definition at session start. It contains core beliefs, method, kill rules, and influences. The identity lives there, not here. This file is codebase context.

## Package

- **Name:** getcalx
- **Version:** 0.7.2
- **Python:** >=3.10
- **License:** MIT
- **PyPI:** https://pypi.org/project/getcalx/

## Environment

Always activate venv before working: `source ~/oss/.venv/bin/activate`

Never editable-install into global Python. Global calx comes from PyPI only.

## Extraction Boundary

This repo contains ONLY the Free tier. No proprietary code:
- No server_full.py
- No engine/compilation.py or engine/learning_mode.py
- No tools/compile_rule.py
- No founder tools (log_decision, set_context, update_metrics, update_pipeline)
- No founder resources (context, decisions, metrics, pipeline, traction)

If any of these appear in this repo, the extraction is broken.

## Cross-Repo References

- **Upstream (Linnie):** ~/calx/ (getcalx/calx, private, OSS + proprietary)
- **Ops (Reid):** ~/ops/ -- strategy, evaluations, coordination
- **SDK strategy:** ~/ops/product/sdk-strategy.md
