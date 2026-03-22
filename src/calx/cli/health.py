"""calx health — rule health analysis."""
from __future__ import annotations

import json

import click

from calx.core.config import find_calx_dir
from calx.core.rules import read_all_rules, read_rules


@click.group()
def health():
    """Health analysis for your rule set."""


@health.command()
@click.option("--domain", "-d", default=None, help="Filter by domain")
@click.option("--json", "as_json", is_flag=True)
def score(domain: str | None, as_json: bool):
    """Score rules by health."""
    calx_dir = find_calx_dir()
    if not calx_dir:
        click.echo("Not a Calx project.", err=True)
        raise SystemExit(1)
    try:
        from calx.health.scoring import score_rules

        scores = score_rules(calx_dir, domain)
        if as_json:
            click.echo(
                json.dumps(
                    [
                        {
                            "rule_id": s.rule_id,
                            "score": s.score,
                            "level": s.level,
                            "factors": s.factors,
                        }
                        for s in scores
                    ],
                    indent=2,
                )
            )
        else:
            for s in scores:
                icon = {"healthy": "+", "warning": "~", "critical": "!"}[s.level]
                click.echo(f"  [{icon}] {s.rule_id}: {s.score:.2f} ({s.level})")
                for f in s.factors:
                    click.echo(f"      {f}")
    except ImportError:
        click.echo("Scoring module not available.")


@health.command()
@click.option("--domain", "-d", default=None)
@click.option("--json", "as_json", is_flag=True)
def conflicts(domain: str | None, as_json: bool):
    """Detect rule contradictions."""
    calx_dir = find_calx_dir()
    if not calx_dir:
        click.echo("Not a Calx project.", err=True)
        raise SystemExit(1)
    try:
        from calx.health.conflicts import detect_conflicts

        rules = read_rules(calx_dir, domain) if domain else read_all_rules(calx_dir)
        found = detect_conflicts(rules)
        if as_json:
            click.echo(
                json.dumps(
                    [
                        {"rule_a": c.rule_a, "rule_b": c.rule_b, "reason": c.reason}
                        for c in found
                    ],
                    indent=2,
                )
            )
        elif found:
            for c in found:
                click.echo(f"  {c.rule_a} <-> {c.rule_b}: {c.reason}")
        else:
            click.echo("No conflicts detected.")
    except ImportError:
        click.echo("Conflicts module not available.")


@health.command()
@click.option("--days", "-n", default=30, help="Staleness threshold in days")
@click.option("--json", "as_json", is_flag=True)
def staleness(days: int, as_json: bool):
    """Find stale process rules."""
    calx_dir = find_calx_dir()
    if not calx_dir:
        click.echo("Not a Calx project.", err=True)
        raise SystemExit(1)
    try:
        from calx.health.staleness import find_stale_rules

        stale = find_stale_rules(calx_dir, days)
        if as_json:
            click.echo(
                json.dumps(
                    [
                        {
                            "rule_id": s.rule_id,
                            "domain": s.domain,
                            "days_since": s.days_since,
                        }
                        for s in stale
                    ],
                    indent=2,
                )
            )
        elif stale:
            for s in stale:
                click.echo(f"  {s.rule_id} ({s.domain}): {s.days_since} days old")
        else:
            click.echo("No stale rules found.")
    except ImportError:
        click.echo("Staleness module not available.")


@health.command()
@click.option("--json", "as_json", is_flag=True)
def coverage(as_json: bool):
    """Check correction-to-rule coverage."""
    calx_dir = find_calx_dir()
    if not calx_dir:
        click.echo("Not a Calx project.", err=True)
        raise SystemExit(1)
    from calx.health.coverage import check_coverage

    report = check_coverage(calx_dir)
    if as_json:
        click.echo(
            json.dumps(
                {
                    "total": report.total_corrections,
                    "distilled": report.distilled,
                    "pending": report.pending,
                    "gaps": report.gaps,
                },
                indent=2,
            )
        )
    else:
        click.echo(
            f"Coverage: {report.distilled}/{report.total_corrections} corrections "
            f"distilled, {report.pending} pending"
        )
        for gap in report.gaps:
            click.echo(f"  Gap: {gap}")


@health.command()
@click.option("--json", "as_json", is_flag=True)
def dedup(as_json: bool):
    """Find near-duplicate rules."""
    calx_dir = find_calx_dir()
    if not calx_dir:
        click.echo("Not a Calx project.", err=True)
        raise SystemExit(1)
    try:
        from calx.health.dedup import find_duplicates

        rules = read_all_rules(calx_dir)
        dups = find_duplicates(rules)
        if as_json:
            click.echo(
                json.dumps(
                    [
                        {
                            "rule_a": d.rule_a,
                            "rule_b": d.rule_b,
                            "similarity": d.similarity,
                        }
                        for d in dups
                    ],
                    indent=2,
                )
            )
        elif dups:
            for d in dups:
                click.echo(f"  {d.rule_a} <-> {d.rule_b}: {d.similarity:.0%} similar")
        else:
            click.echo("No duplicates found.")
    except ImportError:
        click.echo("Dedup module not available.")
