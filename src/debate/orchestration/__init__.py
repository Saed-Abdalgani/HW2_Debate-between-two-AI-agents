"""Process orchestration — IPC, FSM, supervisor, watchdog."""

from debate.orchestration.child_proc import ChildProc
from debate.orchestration.errors import (
    ChildDisconnectedError,
    OrchestrationError,
    RecvTimeoutError,
    RestartsExhaustedError,
    SpawnError,
)
from debate.orchestration.ipc import JsonPipeReader, JsonPipeWriter
from debate.orchestration.state_machine import Ctx, Event, State, is_terminal, transition
from debate.orchestration.supervisor import Supervisor
from debate.orchestration.watchdog import Watchdog

__all__ = [
    "ChildDisconnectedError",
    "ChildProc",
    "Ctx",
    "Event",
    "JsonPipeReader",
    "JsonPipeWriter",
    "OrchestrationError",
    "RecvTimeoutError",
    "RestartsExhaustedError",
    "SpawnError",
    "State",
    "Supervisor",
    "Watchdog",
    "is_terminal",
    "transition",
]
