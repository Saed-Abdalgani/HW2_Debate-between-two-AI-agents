"""Environment passed to Pro/Con child processes."""

from __future__ import annotations

import os

from debate.shared.secrets import get_env


def debate_child_env(*, use_stub: bool = False) -> dict[str, str]:
    """Copy parent env with settings required for pipe IPC and debaters."""
    env = dict(os.environ)
    env["PYTHONUNBUFFERED"] = "1"
    if use_stub or not get_env("LLM_API_KEY"):
        env["DEBATE_STUB_LLM"] = "echo"
    env.pop("SEARCH_API_KEY", None)
    return env
