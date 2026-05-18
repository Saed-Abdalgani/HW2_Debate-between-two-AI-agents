"""Factory wiring for ``JudgeAgent.build`` (keeps judge_agent.py under LOC cap)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import httpx

from debate.agents.judge_prompts import load_score_rubric, load_summarise_system
from debate.orchestration.state_machine import Ctx
from debate.orchestration.supervisor import Supervisor
from debate.sdk.llm_client import LLMClient
from debate.shared.gatekeeper import Gatekeeper
from debate.shared.judge_setup import register_search_skill
from debate.shared.logger import Logger
from debate.shared.router import SkillRouter
from debate.shared.skills import LLMClientProto, make_score_skill, make_summarise_skill

if TYPE_CHECKING:
    from debate.agents.judge_agent import JudgeAgent
    from debate.shared.config import Config


def build_judge_agent(
    cls: type[JudgeAgent],
    cfg: Config,
    *,
    llm: LLMClientProto | None = None,
    logger: Logger | None = None,
    stderr_dir: Any = None,
    child_env: dict[str, str] | None = None,
) -> JudgeAgent:
    run_logger = logger or Logger.open_run()
    run_dir = run_logger.run_dir
    gk = Gatekeeper(cfg, logger=run_logger, run_dir=run_dir)
    http = httpx.Client(timeout=cfg.http_timeout_sec)
    judge_llm = llm or LLMClient(cfg.judge_model, cfg.temperature, http)
    score_llm = llm or LLMClient(cfg.score_model, cfg.temperature, http)
    router = SkillRouter(cfg)
    router.register(
        "score",
        make_score_skill(score_llm, gk, rubric=load_score_rubric(), model=cfg.score_model),
    )
    router.register(
        "summarise",
        make_summarise_skill(
            judge_llm, gk, system_prompt=load_summarise_system(), model=cfg.judge_model
        ),
    )
    register_search_skill(router, gk, cfg, http)
    sup = Supervisor(cfg, stderr_dir=stderr_dir or run_dir, child_env=child_env)
    agent = cls(cfg, gk, judge_llm, sup, router, run_logger)
    agent._ctx = Ctx(round_limit=cfg.rounds)
    return agent
