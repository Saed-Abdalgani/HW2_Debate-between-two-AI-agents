"""Test-only LLM stubs — activated via ``DEBATE_STUB_LLM`` env var."""

from __future__ import annotations

from debate.agents.stub_llm_basic import EchoStubLLM, ErrorStubLLM, RateLimitStubLLM
from debate.agents.stub_llm_tooling import (
    CountingStubLLM,
    FactCheckStubLLM,
    ToolStormStubLLM,
)


def stub_from_env(
    name: str | None,
) -> EchoStubLLM | ToolStormStubLLM | ErrorStubLLM | None:
    """Create a stub LLM from the DEBATE_STUB_LLM env var value."""
    if name == "echo":
        return EchoStubLLM()
    if name in {"tool_storm", "tool_loop"}:
        return ToolStormStubLLM()
    if name == "error":
        return ErrorStubLLM()
    return None


__all__ = [
    "CountingStubLLM",
    "EchoStubLLM",
    "ErrorStubLLM",
    "FactCheckStubLLM",
    "RateLimitStubLLM",
    "ToolStormStubLLM",
    "stub_from_env",
]
