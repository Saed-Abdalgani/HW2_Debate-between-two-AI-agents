"""Child process supervisor — Popen lifecycle, IPC routing, signal hygiene."""

from __future__ import annotations

import atexit
import os
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from queue import Empty

from debate.orchestration.child_proc import ChildProc
from debate.orchestration.errors import ChildDisconnectedError, RecvTimeoutError, SpawnError
from debate.sdk.schemas import Envelope, SchemaLimits
from debate.shared.config import Config

_STRIP_FROM_CHILD_ENV = ("SEARCH_API_KEY",)


def _install_sigpipe_ignore() -> None:
    try:
        import signal as _signal

        _signal.signal(_signal.SIGPIPE, _signal.SIG_IGN)
    except (AttributeError, ValueError, OSError):
        pass


_install_sigpipe_ignore()


class Supervisor:
    """Spawn / send / recv / terminate children; never leak processes."""

    def __init__(self, cfg: Config, *, stderr_dir: Path, child_env: dict[str, str] | None = None):
        self.cfg = cfg
        self.stderr_dir = stderr_dir
        self._children: dict[str, ChildProc] = {}
        self._limits = SchemaLimits(
            max_message_bytes=cfg.max_message_bytes,
            max_clock_skew_sec=cfg.max_clock_skew_sec,
        )
        self._child_env_source = child_env if child_env is not None else os.environ
        atexit.register(self.shutdown_all)

    def spawn(self, role: str, argv: Sequence[str] | None = None) -> ChildProc:
        if role in self._children:
            raise SpawnError(f"role already running: {role}")
        self.stderr_dir.mkdir(parents=True, exist_ok=True)
        cmd = list(argv) if argv else self._default_argv(role)
        env = self._safe_child_env()
        try:
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                bufsize=0,
            )
        except OSError as exc:
            raise SpawnError(f"{role}: {exc}") from exc
        child = ChildProc(
            role,
            proc,
            limits=self._limits,
            max_bytes=self.cfg.max_message_bytes,
            stderr_path=self.stderr_dir / f"{role}.stderr.log",
        )
        self._children[role] = child
        return child

    def send(self, role: str, env: Envelope) -> None:
        self._get(role).writer.write_envelope(env)

    def recv(self, role: str, *, timeout: float) -> Envelope:
        child = self._get(role)
        try:
            item = child.queue.get(timeout=timeout)
        except Empty as exc:
            raise RecvTimeoutError(f"{role}: no envelope in {timeout}s") from exc
        if isinstance(item, BaseException):
            raise item
        return item

    def terminate(self, role: str, *, grace_sec: float | None = None) -> None:
        child = self._children.pop(role, None)
        if child is None:
            return
        grace = grace_sec if grace_sec is not None else self.cfg.child_terminate_grace_sec
        try:
            child.writer.close()
            try:
                child.process.wait(timeout=grace)
            except subprocess.TimeoutExpired:
                child.process.terminate()
                try:
                    child.process.wait(timeout=grace)
                except subprocess.TimeoutExpired:
                    child.process.kill()
                    child.process.wait(timeout=grace)
        except OSError:
            pass
        finally:
            child.join_drainers(timeout=grace)

    def shutdown_all(self) -> None:
        for role in list(self._children):
            try:
                self.terminate(role)
            except OSError:
                continue

    def _get(self, role: str) -> ChildProc:
        child = self._children.get(role)
        if child is None:
            raise ChildDisconnectedError(role)
        return child

    def _safe_child_env(self) -> dict[str, str]:
        env = dict(self._child_env_source)
        for name in _STRIP_FROM_CHILD_ENV:
            env.pop(name, None)
        return env

    @staticmethod
    def _default_argv(role: str) -> list[str]:
        """Run agent script directly so ``__main__`` bootstrap fires (runpy-safe)."""
        import importlib.util

        spec = importlib.util.find_spec(f"debate.agents.{role}_agent")
        if spec is None or not spec.origin:
            raise SpawnError(f"agent module not found: {role}")
        return [sys.executable, "-u", spec.origin]
