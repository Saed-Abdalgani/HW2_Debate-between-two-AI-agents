"""Line-delimited JSON over binary pipes (P5.1 — FR-4, NFR-13)."""

from __future__ import annotations

from contextlib import suppress
from typing import IO

from debate.orchestration.errors import ChildDisconnectedError
from debate.sdk.schemas import (
    Envelope,
    MessageTooLargeError,
    SchemaLimits,
    load_schema_limits,
    parse_envelope,
    serialize,
)

_CHUNK = 4096


class JsonPipeReader:
    """Accumulate bytes from a blocking binary stream until ``\\n`` is seen.

    The reader carries a partial-line buffer across calls so that
    byte-at-a-time writes from the peer still produce one envelope per
    ``read_envelope()`` call. Lines exceeding ``max_bytes`` raise
    ``MessageTooLargeError`` *before* parsing (NFR-13 — bounded buffers).
    """

    def __init__(
        self,
        stream: IO[bytes],
        *,
        max_bytes: int,
        limits: SchemaLimits | None = None,
        role: str = "child",
    ) -> None:
        self._stream = stream
        self._max_bytes = max_bytes
        self._limits = limits or load_schema_limits()
        self._role = role
        self._buf = bytearray()

    def read_envelope(self) -> Envelope:
        while b"\n" not in self._buf:
            chunk = self._stream.read(_CHUNK)
            if not chunk:
                raise ChildDisconnectedError(self._role)
            self._buf.extend(chunk)
            self._guard_size()
        line, _, rest = self._buf.partition(b"\n")
        self._buf = bytearray(rest)
        text = line.decode("utf-8", errors="strict")
        return parse_envelope(text + "\n", limits=self._limits)

    def _guard_size(self) -> None:
        if len(self._buf) > self._max_bytes:
            raise MessageTooLargeError(
                f"unframed buffer {len(self._buf)}B exceeds max {self._max_bytes}B"
            )

    def close(self) -> None:
        with suppress(OSError):
            self._stream.close()


class JsonPipeWriter:
    """Single-line JSON writer with flush and broken-peer detection."""

    def __init__(self, stream: IO[bytes], *, role: str = "child") -> None:
        self._stream = stream
        self._role = role

    def write_envelope(self, env: Envelope) -> None:
        line = serialize(env).encode("utf-8", errors="strict")
        try:
            self._stream.write(line)
            self._stream.flush()
        except (BrokenPipeError, ValueError, OSError) as exc:
            raise ChildDisconnectedError(self._role) from exc

    def close(self) -> None:
        with suppress(OSError):
            self._stream.close()
