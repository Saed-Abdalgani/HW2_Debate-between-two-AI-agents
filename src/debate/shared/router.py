"""SkillRouter — dispatch tool skills with content-hash search cache (NFR-5)."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from collections import OrderedDict
from collections.abc import Callable
from threading import RLock
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from debate.sdk.payloads import ToolCallPayload, ToolResultPayload
from debate.shared.config import Config
from debate.shared.secrets import redact

_WHITESPACE = re.compile(r"\s+")


class RouterError(Exception):
    pass


class UnknownSkillError(RouterError):
    pass


class InvalidToolArgsError(RouterError):
    pass


def normalize_query(text: str) -> str:
    """Unicode-NFC, lower-case, collapse whitespace, strip URL fragments."""
    nfc = unicodedata.normalize("NFC", text).lower().strip()
    collapsed = _WHITESPACE.sub(" ", nfc)
    if "://" in collapsed:
        parts = urlsplit(collapsed)
        collapsed = urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
    return collapsed


def search_cache_key(query: str, k: int) -> str:
    """SHA-256 of normalised query + k; collisions treated as impossible at this scale."""
    payload = f"{normalize_query(query)}|{k}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class _LruCache:
    def __init__(self, max_entries: int) -> None:
        self._max = max_entries
        self._data: OrderedDict[str, ToolResultPayload] = OrderedDict()
        self._lock = RLock()

    def get(self, key: str) -> ToolResultPayload | None:
        with self._lock:
            if key not in self._data:
                return None
            self._data.move_to_end(key)
            return self._data[key]

    def put(self, key: str, value: ToolResultPayload) -> None:
        with self._lock:
            self._data[key] = value
            self._data.move_to_end(key)
            while len(self._data) > self._max:
                self._data.popitem(last=False)


class SkillRouter:
    """Route skills; search hits bypass Gatekeeper (zero token / RPM cost)."""

    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self._skills: dict[str, Callable[[dict[str, Any]], ToolResultPayload]] = {}
        self._cache = _LruCache(cfg.search_cache_max_entries)
        self._inflight: dict[str, RLock] = {}
        self._inflight_guard = RLock()

    def register(self, name: str, fn: Callable[[dict[str, Any]], ToolResultPayload]) -> None:
        self._skills[name] = fn

    def dispatch(self, tool_call: ToolCallPayload) -> ToolResultPayload:
        skill = tool_call.skill
        if skill not in self._skills:
            raise UnknownSkillError(skill)
        args = self._validate_args(skill, tool_call.args)
        key: str | None = None
        if skill == "search" and self.cfg.search.cache:
            key = search_cache_key(str(args["query"]), int(args["k"]))
            cached = self._cache.get(key)
            if cached is not None:
                return cached.model_copy(update={"cached": True})
            lock = self._lock_for(key)
            with lock:
                cached = self._cache.get(key)
                if cached is not None:
                    return cached.model_copy(update={"cached": True})
                result = self._finish(skill, args)
                self._cache.put(key, result.model_copy(update={"cached": True}))
                return result.model_copy(update={"cached": False})
        return self._finish(skill, args)

    def _lock_for(self, key: str) -> RLock:
        with self._inflight_guard:
            return self._inflight.setdefault(key, RLock())

    def _finish(self, skill: str, args: dict[str, Any]) -> ToolResultPayload:
        result = self._skills[skill](args)
        safe = redact(result.model_dump(mode="json"))
        return ToolResultPayload.model_validate({**safe, "cached": False})

    def invoke(self, skill: str, args: dict[str, Any]) -> Any:
        """Judge-internal skills (summarise, score) — not framed as child tool_call."""
        if skill not in self._skills:
            raise UnknownSkillError(skill)
        if skill == "search":
            return self.dispatch(ToolCallPayload(skill="search", args=args))
        return self._skills[skill](args)

    @staticmethod
    def _validate_args(skill: str, args: dict[str, Any]) -> dict[str, Any]:
        if skill == "search":
            query = args.get("query")
            k = args.get("k", 5)
            if not isinstance(query, str) or not query.strip():
                raise InvalidToolArgsError("search requires non-empty query string")
            if not isinstance(k, int) or k < 1:
                raise InvalidToolArgsError("search requires integer k >= 1")
            return {"query": query, "k": k}
        raise InvalidToolArgsError(f"unsupported skill args: {skill}")
