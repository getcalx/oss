"""Explicit correction capture — ``calx correct [message]``."""

from __future__ import annotations

from pathlib import Path

from calx.core.config import load_config
from calx.core.corrections import CorrectionState, create_correction


def capture_explicit(
    calx_dir: Path,
    message: str,
    domain: str | None = None,
    correction_type: str = "process",
    context: str = "",
) -> tuple[CorrectionState, str]:
    """Capture an explicit correction and return (correction, feedback).

    Domain resolution order:
    1. Explicit ``domain`` argument
    2. Auto-detect from cwd
    3. First domain in config
    """
    config = load_config(calx_dir)

    resolved_domain = domain or _auto_detect_domain(calx_dir) or _first_domain(config)

    correction = create_correction(
        calx_dir,
        domain=resolved_domain,
        description=message,
        correction_type=correction_type,
        context=context,
        source="explicit",
    )

    # Try recurrence check — distillation module may not exist yet
    feedback = f"Logged as {correction.id} in {resolved_domain} domain."
    try:
        from calx.distillation.recurrence import check_recurrence
        from calx.core.corrections import materialize

        result = check_recurrence(calx_dir, correction)
        if result.is_recurrence and result.original_id:
            # Look up the original correction's description
            all_corr = materialize(calx_dir)
            by_id = {c.id: c for c in all_corr}
            original = by_id.get(result.original_id)
            original_desc = original.description if original else result.original_id
            count = result.new_count

            threshold = config.promotion_threshold
            if count >= threshold:
                feedback = (
                    f'Logged. Matches {result.original_id}: "{original_desc}". '
                    f"({count} occurrence — promotion eligible.)"
                )
            else:
                feedback = (
                    f'Logged. Matches {result.original_id}: "{original_desc}". '
                    f"({count} occurrences.)"
                )
    except ImportError:
        pass

    return correction, feedback


def _auto_detect_domain(calx_dir: Path) -> str | None:
    """Infer domain from cwd relative to the project root.

    The project root is the parent of the ``.calx`` directory.
    If cwd is inside a subdirectory whose name matches a configured domain,
    that domain is returned.
    """
    config = load_config(calx_dir)
    if not config.domains:
        return None

    project_root = calx_dir.parent
    try:
        cwd = Path.cwd()
        relative = cwd.relative_to(project_root)
    except ValueError:
        return None

    parts = relative.parts
    for part in parts:
        if part in config.domains:
            return part

    return None


def _first_domain(config: object) -> str:
    """Return the first configured domain, or 'general' as fallback."""
    domains = getattr(config, "domains", [])
    return domains[0] if domains else "general"
