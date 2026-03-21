"""Rule file management for Calx.

Rules live in .calx/rules/{domain}.md in markdown format matching production AGENTS.md:

    ### api-R001: Short Title
    Source: C001, C003 | Added: 2026-03-21 | Status: active | Type: architectural

    Rule body text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path


@dataclass
class Rule:
    """A single rule parsed from a domain rules file."""
    id: str              # api-R042
    domain: str
    type: str            # "architectural" | "process"
    source_corrections: list[str]  # ["C001", "C003"]
    added: str           # ISO date
    status: str          # "active" | "review" | "retired"
    title: str
    body: str


_RULE_PATTERN = re.compile(r"^### ([a-z]+-R\d{3}): (.+)$", re.MULTILINE)
_META_PATTERN = re.compile(
    r"Source:\s*(.+?)\s*\|\s*Added:\s*(\S+)\s*\|\s*Status:\s*(\w+)\s*\|\s*Type:\s*(\w+)"
)


def read_rules(calx_dir: Path, domain: str) -> list[Rule]:
    """Parse rules from .calx/rules/{domain}.md."""
    path = calx_dir / "rules" / f"{domain}.md"
    if not path.exists():
        return []
    return _parse_rules_file(path, domain)


def read_all_rules(calx_dir: Path) -> list[Rule]:
    """Read rules from all domain files."""
    rules_dir = calx_dir / "rules"
    if not rules_dir.exists():
        return []

    all_rules: list[Rule] = []
    for path in sorted(rules_dir.glob("*.md")):
        domain = path.stem
        all_rules.extend(_parse_rules_file(path, domain))
    return all_rules


def _parse_rules_file(path: Path, domain: str) -> list[Rule]:
    """Parse a single rules markdown file."""
    text = path.read_text(encoding="utf-8")
    rules: list[Rule] = []

    matches = list(_RULE_PATTERN.finditer(text))
    for i, match in enumerate(matches):
        rule_id = match.group(1)
        title = match.group(2)

        # Extract block between this match and the next
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        block = text[start:end].strip()

        # Parse metadata line
        meta_match = _META_PATTERN.search(block)
        if meta_match:
            source_str = meta_match.group(1).strip()
            sources = [s.strip() for s in source_str.split(",")]
            added = meta_match.group(2).strip()
            status = meta_match.group(3).strip()
            rule_type = meta_match.group(4).strip()

            # Body is everything after the metadata line
            body_start = block.find("\n", meta_match.end() - start)
            body = block[body_start:].strip() if body_start > -1 else ""
        else:
            sources = []
            added = ""
            status = "active"
            rule_type = "process"
            body = block

        rules.append(Rule(
            id=rule_id,
            domain=domain,
            type=rule_type,
            source_corrections=sources,
            added=added,
            status=status,
            title=title,
            body=body,
        ))

    return rules


def write_rule(calx_dir: Path, rule: Rule) -> None:
    """Append a rule to its domain file."""
    rules_dir = calx_dir / "rules"
    rules_dir.mkdir(parents=True, exist_ok=True)
    path = rules_dir / f"{rule.domain}.md"

    block = format_rule_block(rule)

    if path.exists():
        content = path.read_text(encoding="utf-8")
        if not content.endswith("\n\n"):
            content = content.rstrip() + "\n\n"
        content += block
    else:
        content = f"# Rules: {rule.domain}\n\n{block}"

    path.write_text(content, encoding="utf-8")


def format_rule_block(rule: Rule) -> str:
    """Render a Rule to markdown block."""
    source_str = ", ".join(rule.source_corrections) if rule.source_corrections else "seed"
    lines = [
        f"### {rule.id}: {rule.title}",
        f"Source: {source_str} | Added: {rule.added} | Status: {rule.status} | Type: {rule.type}",
        "",
        rule.body,
        "",
    ]
    return "\n".join(lines)


def update_rule_status(calx_dir: Path, rule_id: str, new_status: str) -> None:
    """Update a rule's status in its domain file."""
    # Extract domain from rule_id (e.g., "api-R001" -> "api")
    domain = rule_id.rsplit("-R", 1)[0]
    path = calx_dir / "rules" / f"{domain}.md"
    if not path.exists():
        return

    text = path.read_text(encoding="utf-8")
    # Find and replace the status in the metadata line for this rule
    pattern = re.compile(
        rf"(### {re.escape(rule_id)}: .+\nSource: .+\| Status: )\w+(\s*\|)"
    )
    text = pattern.sub(rf"\g<1>{new_status}\g<2>", text)
    path.write_text(text, encoding="utf-8")


def next_rule_id(calx_dir: Path, domain: str) -> str:
    """Generate the next sequential rule ID for a domain."""
    existing = [r.id for r in read_rules(calx_dir, domain)]
    prefix = f"{domain}-R"

    from calx.core.ids import next_sequential_id
    return next_sequential_id(prefix, existing)
