"""Typed orchestration errors — IPC, supervisor, watchdog."""

from __future__ import annotations


class OrchestrationError(Exception):
    """Base class for orchestration faults."""


class ChildDisconnectedError(OrchestrationError):
    """Raised when a child pipe is closed / EOF reached on read."""

    def __init__(self, role: str = "unknown") -> None:
        self.role = role
        super().__init__(f"child disconnected: {role}")


class RecvTimeoutError(OrchestrationError):
    """No envelope received within the requested deadline."""


class SpawnError(OrchestrationError):
    """Failed to spawn a child process."""


class RestartsExhaustedError(OrchestrationError):
    """The watchdog has tripped more than `max_restarts_per_child`."""

    def __init__(self, role: str, count: int) -> None:
        self.role = role
        self.count = count
        super().__init__(f"{role}: restarts exhausted after {count}")
