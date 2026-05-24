"""Judge-process diagnostics — stderr by default, file sink during Rich Live.

Rich ``Live`` renders on stdout; interleaving ``sys.stderr`` writes in the same
terminal corrupts cursor state and makes the live panel drop or desync rows.
When ``configure_diag_sink`` points at a file, lines are appended there instead.
"""

from __future__ import annotations

import sys
from typing import TextIO

_sink_path: str | None = None


def configure_diag_sink(path: str | None) -> None:
    """Set path for diagnostic lines, or ``None`` to restore stderr."""
    global _sink_path
    _sink_path = path


def write_diag_line(msg: str, *, stream: TextIO | None = None) -> None:
    """Write one diagnostic line (with trailing newline)."""
    if _sink_path is not None:
        with open(_sink_path, "a", encoding="utf-8", newline="\n") as fh:
            fh.write(msg + "\n")
        return
    (stream or sys.stderr).write(msg + "\n")
