"""Echo child fixture — reads envelopes on stdin, echoes them on stdout.

Also exits 0 on receiving a ``shutdown`` envelope. Writes ``__env__`` keys to
stderr so integration tests can verify env stripping (NFR-12).
"""

from __future__ import annotations

import os
import sys
from datetime import UTC, datetime

from debate.sdk.payloads import MessageType, PongPayload, Role
from debate.sdk.schemas import SCHEMA_VERSION, Envelope, parse_envelope, serialize


def _emit(env: Envelope) -> None:
    sys.stdout.buffer.write(serialize(env).encode("utf-8"))
    sys.stdout.buffer.flush()


def _pong(turn_id: int) -> Envelope:
    return Envelope(
        v=SCHEMA_VERSION,
        ts=datetime.now(UTC),
        turn_id=turn_id,
        role=Role.PRO,
        type=MessageType.PONG,
        payload=PongPayload(turn_id=turn_id),
    )


def main() -> int:
    keys = sorted(k for k in os.environ if k.endswith("_API_KEY"))
    sys.stderr.write("__env__=" + ",".join(keys) + "\n")
    sys.stderr.flush()
    buf = bytearray()
    while True:
        chunk = sys.stdin.buffer.read(1)
        if not chunk:
            return 0
        buf.extend(chunk)
        if not buf.endswith(b"\n"):
            continue
        line = buf.decode("utf-8")
        buf.clear()
        env = parse_envelope(line)
        if env.type == MessageType.SHUTDOWN:
            return 0
        if env.type == MessageType.PING:
            _emit(_pong(env.turn_id))
            continue
        _emit(env)


if __name__ == "__main__":
    sys.exit(main())
