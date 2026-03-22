"""calx distill — trigger graduation flow."""
from __future__ import annotations

import click

from calx.core.config import find_calx_dir, load_config


@click.command()
@click.option("--review", is_flag=True, help="Trigger Tier 3 weekly batch review")
def distill(review: bool):
    """Run the distillation flow — promote recurring corrections to rules."""
    calx_dir = find_calx_dir()
    if not calx_dir:
        click.echo("Not a Calx project. Run `calx init` first.", err=True)
        raise SystemExit(1)

    config = load_config(calx_dir)

    if review:
        _run_review(calx_dir)
    else:
        _run_promotion(calx_dir, config)


def _run_promotion(calx_dir, config):
    """Tier 2: binary approve/reject."""
    try:
        from calx.distillation.promotion import (
            get_pending_promotions,
            promote,
            reject_promotion,
        )
    except ImportError:
        click.echo("Promotion module not available.")
        return

    candidates = get_pending_promotions(
        calx_dir,
        config.promotion_threshold,
        config.max_prompts_per_session,
    )

    if not candidates:
        click.echo("No corrections ready for promotion.")
        return

    click.echo(f"{len(candidates)} correction(s) ready for promotion:\n")

    for candidate in candidates:
        click.echo(candidate.prompt)
        choice = click.prompt("", type=click.Choice(["y", "n"]), default="n")
        if choice == "y":
            rule = promote(calx_dir, candidate.chain)
            click.echo(f"  -> Created rule {rule.id}: {rule.title}\n")
        else:
            reject_promotion(calx_dir, candidate.chain.original_id)
            click.echo("  -> Skipped. Will resurface if it keeps recurring.\n")


def _run_review(calx_dir):
    """Tier 3: weekly batch review."""
    try:
        from calx.distillation.review import (
            ReviewDecision,
            apply_review,
            generate_review,
        )
    except ImportError:
        click.echo("Review module not available.")
        return

    doc = generate_review(calx_dir)
    if not doc.items:
        click.echo("No items to review. Your rule set is clean.")
        return

    click.echo(doc.formatted)
    click.echo()

    decisions: list = []
    for i, item in enumerate(doc.items):
        choice = click.prompt(
            f"Item {i + 1} ({item.type})",
            type=click.Choice(["accept", "reject", "skip"]),
            default="skip",
        )
        decisions.append(ReviewDecision(item_index=i, action=choice))

    apply_review(calx_dir, decisions)
    accepted = sum(1 for d in decisions if d.action == "accept")
    click.echo(f"\n{accepted} decision(s) applied.")
