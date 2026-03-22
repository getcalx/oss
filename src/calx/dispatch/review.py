"""Cross-domain review routing for Calx."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from calx.core.config import load_config
from calx.core.rules import read_rules, format_rule_block


@dataclass
class ReviewSuggestion:
    """A suggestion for which domain should review a spec."""

    spec_domain: str
    suggested_reviewer_domain: str
    reason: str


def suggest_reviewer(calx_dir: Path, domain: str) -> ReviewSuggestion | None:
    """Suggest a cross-domain reviewer for a given builder domain.

    Returns None if no other domains are configured.
    """
    config = load_config(calx_dir)
    other_domains = [d for d in config.domains if d != domain]

    if not other_domains:
        return None

    # Pick the domain with the most rules (most context to catch boundary issues)
    best = other_domains[0]
    best_count = len(read_rules(calx_dir, best))
    for d in other_domains[1:]:
        count = len(read_rules(calx_dir, d))
        if count > best_count:
            best = d
            best_count = count

    return ReviewSuggestion(
        spec_domain=domain,
        suggested_reviewer_domain=best,
        reason=(
            "Cross-domain reviewers catch boundary failures (wire format mismatches, "
            "endpoint path errors, enum value mismatches) invisible to same-domain review. "
            "Zero overlap across 18 domain-specific categories."
        ),
    )


def generate_review_dispatch(
    calx_dir: Path,
    spec_domain: str,
    review_domain: str,
    spec_content: str,
) -> str:
    """Generate a review dispatch prompt for a cross-domain reviewer."""
    reviewer_rules = read_rules(calx_dir, review_domain)

    parts: list[str] = []
    parts.append(f"# Review Dispatch: {review_domain} reviewing {spec_domain}")

    parts.append(f"\n## Your Domain Rules ({review_domain})")
    if reviewer_rules:
        for rule in reviewer_rules:
            if rule.status == "active":
                parts.append(format_rule_block(rule))
    else:
        parts.append("No rules defined for your domain.")

    parts.append(f"\n## Spec to Review ({spec_domain})")
    parts.append(spec_content)

    parts.append("\n## Review Instructions")
    parts.append(
        "Focus on boundary failures: wire format mismatches, endpoint path errors, "
        "enum value mismatches, and integration points between your domain and the spec domain. "
        "Cross-domain reviewers catch issues invisible to same-domain review."
    )
    parts.append("\nOutput: Binary — PASS or FAIL with specific findings.")

    return "\n".join(parts)
