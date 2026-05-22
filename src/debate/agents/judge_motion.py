"""Motion string validation for the Judge."""

from __future__ import annotations

import re

_MAX_MOTION_LENGTH = 2000
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def validate_motion(motion: str) -> str:
    """Sanitise and validate the motion string."""
    cleaned = _CONTROL_CHARS.sub("", motion).strip()
    if not cleaned:
        raise ValueError("motion must not be empty")
    if len(cleaned) > _MAX_MOTION_LENGTH:
        raise ValueError(f"motion exceeds {_MAX_MOTION_LENGTH} chars (got {len(cleaned)})")
    return cleaned
