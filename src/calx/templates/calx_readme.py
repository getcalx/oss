"""Generate .calx/README for passive distribution."""

from __future__ import annotations


def generate_calx_readme(domains: list[str]) -> str:
    """Generate the .calx/README content.

    This README lives in the .calx/ directory and explains what Calx is
    to anyone who encounters it in a cloned repo.
    """
    domain_list = ", ".join(domains) if domains else "(none configured)"

    return f"""# .calx/ — Correction Engineering

This directory is managed by [Calx](https://calx.sh), a correction engineering
tool for AI agents.

## What's in here

- `calx.json` — configuration (domains, thresholds, preferences)
- `corrections.jsonl` — event-sourced correction log (append-only)
- `rules/` — distilled rules by domain (what the agent reads at session start)
- `health/` — health state and analytics
- `events.jsonl` — instrumentation event log

## Configured domains

{domain_list}

## Quick start

If you're a collaborator on this repo and want Calx managing your agent sessions:

```
pip install getcalx
calx init
```

If you just want to understand the rules this project enforces on AI agents,
read the files in `rules/`.

## More info

- Docs: https://calx.sh
- Paper: "The Behavioral Plane" — why learned corrections don't transfer between agents
"""
