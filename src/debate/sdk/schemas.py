"""IPC envelope parse/serialize — single-line JSON (see module doc in payloads)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import jsonschema
from pydantic import BaseModel, ConfigDict, ValidationError

from debate.sdk.payloads import (
    PAYLOAD_BY_TYPE,
    MessageType,
    PayloadModel,
    Role,
    VerdictPayload,
)

SCHEMA_VERSION = 1
_ROOT = Path(__file__).resolve().parents[3]
_VERDICT_SCHEMA_PATH = _ROOT / "config" / "prompts" / "verdict.schema.json"
_DEFAULT_CONFIG_PATH = _ROOT / "config" / "debate.json"


class SchemaError(Exception):
    pass


class SchemaVersionError(SchemaError):
    pass


class MessageTooLargeError(SchemaError):
    pass


class ClockSkewError(SchemaError):
    pass


class VerdictValidationError(SchemaError):
    pass


class SchemaLimits(BaseModel):
    model_config = ConfigDict(extra="forbid")
    max_message_bytes: int
    max_clock_skew_sec: float


class Envelope(BaseModel):
    model_config = ConfigDict(extra="forbid")
    v: int
    ts: datetime
    turn_id: int
    role: Role
    type: MessageType
    payload: PayloadModel


def load_schema_limits(path: Path | None = None) -> SchemaLimits:
    cfg_path = path or _DEFAULT_CONFIG_PATH
    data = json.loads(cfg_path.read_text(encoding="utf-8"))
    return SchemaLimits(
        max_message_bytes=data["max_message_bytes"],
        max_clock_skew_sec=data["max_clock_skew_sec"],
    )


def _validate_payload(msg_type: MessageType, payload: dict[str, Any]) -> PayloadModel:
    model = PAYLOAD_BY_TYPE.get(msg_type)
    if model is None:
        raise SchemaError(f"unknown message type: {msg_type}")
    return model.model_validate(payload)  # type: ignore[return-value]


def _check_newlines(value: Any) -> None:
    if isinstance(value, str) and ("\n" in value or "\r" in value):
        raise SchemaError("payload must not contain newline characters")
    if isinstance(value, dict):
        for item in value.values():
            _check_newlines(item)
    elif isinstance(value, list):
        for item in value:
            _check_newlines(item)


def parse_envelope(line: str, *, limits: SchemaLimits | None = None) -> Envelope:
    limits = limits or load_schema_limits()
    encoded = (line if line.endswith("\n") else line + "\n").encode("utf-8")
    if len(encoded) > limits.max_message_bytes:
        raise MessageTooLargeError(
            f"message size {len(encoded)} exceeds max {limits.max_message_bytes}"
        )
    try:
        data = json.loads(line.strip())
    except json.JSONDecodeError as exc:
        raise SchemaError("invalid JSON") from exc
    if data.get("v") != SCHEMA_VERSION:
        raise SchemaVersionError(f"schema version {data.get('v')!r} != expected {SCHEMA_VERSION}")
    msg_type = MessageType(data["type"])
    try:
        payload = _validate_payload(msg_type, data["payload"])
    except ValidationError as exc:
        raise SchemaError(str(exc)) from exc
    ts = datetime.fromisoformat(data["ts"].replace("Z", "+00:00"))
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    skew = abs((datetime.now(UTC) - ts.astimezone(UTC)).total_seconds())
    if skew > limits.max_clock_skew_sec:
        raise ClockSkewError(f"timestamp skew {skew}s exceeds {limits.max_clock_skew_sec}s")
    return Envelope(
        v=data["v"],
        ts=ts,
        turn_id=data["turn_id"],
        role=Role(data["role"]),
        type=msg_type,
        payload=payload,
    )


def serialize(env: Envelope) -> str:
    _check_newlines(env.payload.model_dump(mode="json"))
    body = {
        "v": env.v,
        "ts": env.ts.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
        "turn_id": env.turn_id,
        "role": env.role.value,
        "type": env.type.value,
        "payload": env.payload.model_dump(mode="json"),
    }
    line = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
    if "\n" in line:
        raise SchemaError("serialized envelope must not contain newlines")
    return line + "\n"


def validate_verdict(data: dict[str, Any]) -> VerdictPayload:
    schema = json.loads(_VERDICT_SCHEMA_PATH.read_text(encoding="utf-8"))
    try:
        jsonschema.validate(instance=data, schema=schema)
    except jsonschema.ValidationError as exc:
        raise VerdictValidationError(str(exc.message)) from exc
    try:
        return VerdictPayload.model_validate(data)
    except ValidationError as exc:
        raise VerdictValidationError(str(exc)) from exc