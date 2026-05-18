"""Judge Router wiring — search skill registration (parent process only)."""

from __future__ import annotations

import httpx

from debate.sdk.payloads import ToolResultPayload
from debate.shared.config import Config
from debate.shared.gatekeeper import Gatekeeper
from debate.shared.router import SkillRouter
from debate.shared.secrets import get_env
from debate.shared.skills import make_search_skill


def register_search_skill(
    router: SkillRouter, gk: Gatekeeper, cfg: Config, http: httpx.Client
) -> None:
    if not get_env("SEARCH_API_KEY"):
        router.register(
            "search",
            lambda _args: ToolResultPayload(skill="search", hits=[], cached=False),
        )
        return
    from debate.sdk.search_client import SearchClient

    client = SearchClient(cfg.search.provider, http, snippet_max_chars=cfg.search_snippet_max_chars)
    router.register("search", make_search_skill(client, gk))
