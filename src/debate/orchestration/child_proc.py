"""Per-child process handle — reader thread, stderr drain, envelope queue."""

from __future__ import annotations

import subprocess
import threading
from pathlib import Path
from queue import Queue
from typing import IO

from debate.orchestration.ipc import JsonPipeReader, JsonPipeWriter
from debate.sdk.schemas import Envelope, SchemaLimits


class ChildProc:
    """Owns a ``subprocess.Popen`` + its reader/drain threads + envelope queue."""

    def __init__(
        self,
        role: str,
        process: subprocess.Popen[bytes],
        *,
        limits: SchemaLimits,
        max_bytes: int,
        stderr_path: Path,
    ) -> None:
        self.role = role
        self.process = process
        assert process.stdin is not None
        assert process.stdout is not None
        assert process.stderr is not None
        self.writer = JsonPipeWriter(process.stdin, role=role)
        self._reader = JsonPipeReader(process.stdout, max_bytes=max_bytes, limits=limits, role=role)
        self.queue: Queue[Envelope | BaseException] = Queue()
        self._read_thread = threading.Thread(target=self._pump_reader, daemon=True)
        self._stderr_thread = threading.Thread(
            target=self._drain_stderr, args=(process.stderr, stderr_path), daemon=True
        )
        self._read_thread.start()
        self._stderr_thread.start()

    def _pump_reader(self) -> None:
        try:
            while True:
                env = self._reader.read_envelope()
                self.queue.put(env)
        except BaseException as exc:
            self.queue.put(exc)

    def _drain_stderr(self, stream: IO[bytes], path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with path.open("ab") as fh:
                while True:
                    chunk = stream.read(4096)
                    if not chunk:
                        return
                    fh.write(chunk)
                    fh.flush()
        except OSError:
            return

    def join_drainers(self, timeout: float) -> None:
        self._read_thread.join(timeout=timeout)
        self._stderr_thread.join(timeout=timeout)
