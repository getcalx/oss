"""calx dispatch — generate dispatch prompts."""
from __future__ import annotations

import click

from calx.core.config import find_calx_dir
from calx.dispatch.generator import generate_dispatch
from calx.dispatch.review import generate_review_dispatch, suggest_reviewer


@click.command("dispatch")
@click.argument("domain")
@click.option("--task", "-t", default=None, help="Task description")
@click.option("--files", "-f", multiple=True, help="Files in scope")
@click.option("--review", is_flag=True, help="Generate review dispatch")
@click.option("--json", "as_json", is_flag=True)
def dispatch(
    domain: str,
    task: str | None,
    files: tuple[str, ...],
    review: bool,
    as_json: bool,
):
    """Generate a dispatch prompt for a domain agent."""
    calx_dir = find_calx_dir()
    if not calx_dir:
        click.echo("Not a Calx project.", err=True)
        raise SystemExit(1)

    if review:
        suggestion = suggest_reviewer(calx_dir, domain)
        if not suggestion:
            click.echo("No other domains configured for cross-domain review.")
            return
        spec = task or click.prompt("Spec content to review")
        output = generate_review_dispatch(
            calx_dir,
            domain,
            suggestion.suggested_reviewer_domain,
            spec,
        )
    else:
        task_text = task or click.prompt("Task description")
        file_list = list(files) if files else None
        output = generate_dispatch(calx_dir, domain, task_text, files=file_list)

    click.echo(output)
