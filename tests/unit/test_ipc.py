"""Unit tests — JsonPipeReader / JsonPipeWriter (P5.1)."""

from __future__ import annotations

import io

import pytest

from debate.orchestration.errors import ChildDisconnectedError
from debate.orchestration.ipc import JsonPipeReader, JsonPipeWriter
from debate.sdk.payloads import MessageType, PingPayload, Role
from debate.sdk.schemas import (
    SCHEMA_VERSION,
    Envelope,
    MessageTooLargeError,
    SchemaLimits,
    serialize,
)


def _ping(turn_id: int = 1) -> Envelope:
    from datetime import UTC, datetime

    return Envelope(
        v=SCHEMA_VERSION,
        ts=datetime.now(UTC),
        turn_id=turn_id,
        role=Role.JUDGE,
        type=MessageType.PING,
        payload=PingPayload(),
    )


class _OneByteStream(io.RawIOBase):
    """Returns one byte per read() call — simulates trickle pipes."""

    def __init__(self, data: bytes) -> None:
        self._data = data
        self._pos = 0

    def readable(self) -> bool:
        return True

    def read(self, size: int = -1) -> bytes:
        if self._pos >= len(self._data):
            return b""
        byte = self._data[self._pos : self._pos + 1]
        self._pos += 1
        return byte


@pytest.fixture
def limits() -> SchemaLimits:
    return SchemaLimits(max_message_bytes=65536, max_clock_skew_sec=3600)


@pytest.mark.unit
def test_roundtrip_through_bytesio(limits: SchemaLimits) -> None:
    env = _ping()
    stream = io.BytesIO(serialize(env).encode("utf-8"))
    reader = JsonPipeReader(stream, max_bytes=4096, limits=limits)
    parsed = reader.read_envelope()
    assert parsed.type == env.type
    assert parsed.turn_id == env.turn_id


@pytest.mark.unit
def test_partial_reads_byte_by_byte(limits: SchemaLimits) -> None:
    env = _ping(turn_id=7)
    data = serialize(env).encode("utf-8")
    reader = JsonPipeReader(_OneByteStream(data), max_bytes=4096, limits=limits)
    parsed = reader.read_envelope()
    assert parsed.turn_id == 7


@pytest.mark.unit
def test_multiple_envelopes_one_stream(limits: SchemaLimits) -> None:
    first = serialize(_ping(1)).encode("utf-8")
    second = serialize(_ping(2)).encode("utf-8")
    reader = JsonPipeReader(io.BytesIO(first + second), max_bytes=4096, limits=limits)
    assert reader.read_envelope().turn_id == 1
    assert reader.read_envelope().turn_id == 2


@pytest.mark.unit
def test_oversize_unframed_buffer_rejected(limits: SchemaLimits) -> None:
    junk = b"x" * 200 + b"\n"
    reader = JsonPipeReader(io.BytesIO(junk), max_bytes=64, limits=limits)
    with pytest.raises(MessageTooLargeError):
        reader.read_envelope()


@pytest.mark.unit
def test_eof_raises_child_disconnected(limits: SchemaLimits) -> None:
    reader = JsonPipeReader(io.BytesIO(b""), max_bytes=4096, limits=limits, role="pro")
    with pytest.raises(ChildDisconnectedError, match="pro"):
        reader.read_envelope()


@pytest.mark.unit
def test_writer_serializes_and_flushes(limits: SchemaLimits) -> None:
    sink = io.BytesIO()
    writer = JsonPipeWriter(sink)
    writer.write_envelope(_ping(turn_id=9))
    sink.seek(0)
    reader = JsonPipeReader(sink, max_bytes=4096, limits=limits)
    assert reader.read_envelope().turn_id == 9


@pytest.mark.unit
def test_writer_detects_broken_pipe() -> None:
    class _BrokenStream(io.RawIOBase):
        def writable(self) -> bool:
            return True

        def write(self, _b: bytes) -> int:
            raise BrokenPipeError("peer gone")

    writer = JsonPipeWriter(_BrokenStream(), role="con")
    with pytest.raises(ChildDisconnectedError, match="con"):
        writer.write_envelope(_ping())
