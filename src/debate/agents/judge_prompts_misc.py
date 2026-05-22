"""Optional judge prompt utilities (stats, injection heuristics, retry notes)."""


def prompt_stats(text: str) -> dict[str, int]:
    """Return basic statistics about a prompt string."""
    lines = text.strip().splitlines()
    words = text.split()
    return {
        "chars": len(text),
        "lines": len(lines),
        "words": len(words),
    }


def detect_prompt_injection(motion: str) -> bool:
    """Quick check for common prompt-injection phrases."""
    lowered = motion.lower()
    dangerous = [
        "ignore previous",
        "disregard above",
        "override rules",
        "reveal system prompt",
        "you are now",
    ]
    return any(phrase in lowered for phrase in dangerous)


def format_retry_note(raw_note: str) -> str:
    """Build a structured retry note from a raw failure description."""
    note = raw_note.strip()
    if not note:
        return ""
    parts = [
        f"Previous verdict was invalid: {note}",
        "Fix all issues listed above.",
        "Return valid JSON only — no markdown fences.",
    ]
    return "\n".join(parts)
