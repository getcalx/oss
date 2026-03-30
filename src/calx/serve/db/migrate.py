"""File-based .calx/ to SQLite migration and schema migration runner."""
from __future__ import annotations
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from calx.serve.db.sqlite import SQLiteEngine


@dataclass
class MigrationResult:
    corrections_imported: int = 0
    rules_imported: int = 0
    migrated_at: str = ""


def _extract_keywords_json(text: str) -> str:
    """Pre-compute keywords for a correction. Returns JSON-serialized set."""
    from calx.serve.engine.similarity import extract_keywords

    return json.dumps(sorted(extract_keywords(text)))


async def migrate_from_files(db: SQLiteEngine, calx_dir: Path) -> MigrationResult:
    """Import file-based .calx/ data into SQLite. Idempotent."""
    from calx.serve.db.engine import CorrectionRow, RuleRow

    result = MigrationResult()

    # --- Corrections from corrections.jsonl ---
    jsonl_path = calx_dir / "corrections.jsonl"
    if jsonl_path.exists():
        events = _read_jsonl_events(jsonl_path)
        states = _materialize_corrections(events)
        for state in states:
            if not await db.correction_exists(state["uuid"]):
                correction = CorrectionRow(
                    id=state["id"],
                    uuid=state["uuid"],
                    correction=state["description"],
                    domain=state["domain"],
                    category=state.get("type", "procedural"),
                    surface="cli",
                    keywords=_extract_keywords_json(state["description"]),
                    recurrence_of=state.get("recurrence_of"),
                    root_correction_id=state.get("root_correction_id"),
                    recurrence_count=state.get("recurrence_count", 1),
                )
                await db.insert_correction(correction)
                result.corrections_imported += 1

    # --- Rules from rules/*.md ---
    rules_dir = calx_dir / "rules"
    if rules_dir.exists():
        for rule_file in rules_dir.glob("*.md"):
            parsed_rules = _parse_rule_file(rule_file)
            for pr in parsed_rules:
                if not await db.rule_exists(pr["id"]):
                    rule = RuleRow(
                        id=pr["id"],
                        rule_text=pr["body"],
                        domain=pr["domain"],
                        source_correction_id=pr.get("source_correction_id"),
                    )
                    await db.insert_rule(rule)
                    result.rules_imported += 1

    result.migrated_at = datetime.now(timezone.utc).isoformat()
    return result


def _read_jsonl_events(path: Path) -> list[dict]:
    """Read events from a JSONL file, skipping malformed lines."""
    events = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return events


def _materialize_corrections(events: list[dict]) -> list[dict]:
    """Replay events into materialized correction states."""
    corrections: dict[str, dict] = {}
    recurrence_map: dict[str, str] = {}  # child_id -> original_id

    for event in events:
        etype = event.get("event_type")
        cid = event.get("correction_id", "")
        data = event.get("data", {})

        if etype == "created":
            corrections[cid] = {
                "id": cid,
                "uuid": data.get("uuid", cid),
                "description": data.get("description", ""),
                "domain": data.get("domain", "general"),
                "type": data.get("type", "process"),
                "recurrence_count": 1,
                "recurrence_of": None,
                "root_correction_id": None,
            }
        elif etype == "recurrence":
            original_id = data.get("original_id")
            if original_id and cid in corrections:
                corrections[cid]["recurrence_of"] = original_id
                # Walk to root
                root = original_id
                while root in recurrence_map:
                    root = recurrence_map[root]
                corrections[cid]["root_correction_id"] = root
                recurrence_map[cid] = original_id
                # Increment root's count
                if root in corrections:
                    corrections[root]["recurrence_count"] += 1

    return list(corrections.values())


def _parse_rule_file(path: Path) -> list[dict]:
    """Parse a markdown rule file into rule dicts."""
    import re

    content = path.read_text()
    domain = path.stem  # filename without extension

    rules = []
    pattern = re.compile(r"^### ([a-zA-Z_]+-R\d{3}): (.+)$", re.MULTILINE)

    for match in pattern.finditer(content):
        rule_id = match.group(1)
        title = match.group(2)

        # Extract body: everything between this header and the next (or EOF)
        start = match.end()
        next_match = pattern.search(content, start)
        end = next_match.start() if next_match else len(content)
        body_section = content[start:end].strip()

        # Skip the metadata line (Source: ... | Added: ... | ...)
        lines = body_section.split("\n")
        body_lines = []
        for line in lines:
            if line.startswith("Source:") and "|" in line:
                # Extract source correction IDs
                source_part = line.split("|")[0].replace("Source:", "").strip()
                continue
            body_lines.append(line)

        body = "\n".join(body_lines).strip()
        if not body:
            body = title

        rules.append({
            "id": rule_id,
            "domain": domain,
            "title": title,
            "body": body,
        })

    return rules
