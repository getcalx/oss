from dataclasses import dataclass, field


@dataclass
class ClassificationResult:
    mode: str            # "architectural" | "process"
    confidence: str      # "high" | "medium" | "low"
    signals: list[str] = field(default_factory=list)  # Reasons for classification


# Category -> base mode mapping
_CATEGORY_MODE: dict[str, str] = {
    "factual": "architectural",
    "structural": "architectural",
    "tonal": "process",
    "procedural": "process",
}

# Keywords that upgrade a process classification to architectural
_ARCHITECTURAL_KEYWORDS: list[str] = [
    "schema",
    "migration",
    "architecture",
    "config",
    "type",
    "interface",
]

# Phrases that downgrade an architectural classification to process
_PROCESS_PHRASES: list[str] = [
    "remember to",
    "don't forget",
    "make sure to",
    "always check",
]


def classify_correction(
    category: str,
    correction_text: str,
    severity: str = "medium",
) -> ClassificationResult:
    """Classify a correction as architectural or process."""
    text_lower = correction_text.lower()

    # Base classification from category (unknown defaults to process)
    base_mode = _CATEGORY_MODE.get(category, "process")
    signals = [f"category:{category}"]

    # Check for keyword overrides
    upgrade_match = None
    for kw in _ARCHITECTURAL_KEYWORDS:
        if kw in text_lower:
            upgrade_match = kw
            break

    downgrade_match = None
    for phrase in _PROCESS_PHRASES:
        if phrase in text_lower:
            downgrade_match = phrase
            break

    # Apply overrides: downgrade takes priority over upgrade when both present
    # (checklist language signals process regardless of content keywords)
    if downgrade_match and base_mode == "architectural":
        signals.append(f"keyword_downgrade:{downgrade_match}")
        return ClassificationResult(
            mode="process",
            confidence="medium",
            signals=signals,
        )

    if upgrade_match and base_mode == "process":
        signals.append(f"keyword_upgrade:{upgrade_match}")
        return ClassificationResult(
            mode="architectural",
            confidence="medium",
            signals=signals,
        )

    return ClassificationResult(
        mode=base_mode,
        confidence="high",
        signals=signals,
    )
