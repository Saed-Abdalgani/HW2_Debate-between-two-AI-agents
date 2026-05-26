"""Factory wiring for ``JudgeAgent.build`` (keeps judge_agent.py small).

Includes configuration validation, structured build logging, dependency
checks for prompt files, and error wrapping with component context.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Any

import httpx

from debate.agents.judge_prompts import (
    load_round_eval_system,
    load_score_rubric,
    load_summarise_system,
    validate_prompt_files,
)
from debate.orchestration.state_machine import Ctx
from debate.orchestration.supervisor import Supervisor
from debate.sdk.llm_client import LLMClient, resolve_llm_base_url
from debate.shared.gatekeeper import Gatekeeper
from debate.shared.judge_setup import register_search_skill
from debate.shared.logger import Logger
from debate.shared.router import SkillRouter
from debate.shared.skills import (
    LLMClientProto,
    make_round_eval_skill,
    make_score_skill,
    make_summarise_skill,
)

if TYPE_CHECKING:
    from debate.agents.judge_agent import JudgeAgent
    from debate.shared.config import Config

_LOG_PREFIX = "[BUILD]"


def build_judge_agent(
    cls: type[JudgeAgent],
    cfg: Config,
    *,
    llm: LLMClientProto | None = None,
    logger: Logger | None = None,
    stderr_dir: Any = None,
    child_env: dict[str, str] | None = None,
) -> JudgeAgent:
    """Wire all components and return a ready-to-run JudgeAgent."""
    _validate_build_config(cfg)
    validate_prompt_files()
    _log("config_ok", f"rounds={cfg.rounds} model={cfg.judge_model}")

    run_logger = logger or Logger.open_run()
    run_dir = run_logger.run_dir
    gk = Gatekeeper(cfg, logger=run_logger, run_dir=run_dir)
    http = httpx.Client(timeout=cfg.http_timeout_sec)
    base_url = resolve_llm_base_url()
    judge_llm = llm or LLMClient(cfg.judge_model, cfg.temperature, http, base_url=base_url)
    score_llm = llm or LLMClient(cfg.score_model, cfg.temperature, http, base_url=base_url)
    _log("llm_ready", f"judge={cfg.judge_model} score={cfg.score_model}")

    router = SkillRouter(cfg)
    router.register(
        "score",
        make_score_skill(
            score_llm,
            gk,
            rubric=load_score_rubric(),
            model=cfg.score_model,
        ),
    )
    router.register(
        "summarise",
        make_summarise_skill(
            judge_llm,
            gk,
            system_prompt=load_summarise_system(),
            model=cfg.judge_model,
        ),
    )
    router.register(
        "round_eval",
        make_round_eval_skill(
            score_llm,
            gk,
            system_prompt=load_round_eval_system(),
            model=cfg.score_model,
        ),
    )
    register_search_skill(router, gk, cfg, http)
    sup = Supervisor(cfg, stderr_dir=stderr_dir or run_dir, child_env=child_env)

    def on_miss(role: str) -> None:
        agent.logger.event("heartbeat_miss", role=role, turn_id=agent._turn_id)
        sup.terminate(role)
        sup.spawn(role)
        from debate.agents.judge_child import send_init, send_prompt
        from debate.sdk.payloads import DebatePhase

        send_init(sup, cfg, agent._motion, role, agent._turn_id)
        last = agent._ctx.last_outbound_per_role.get(role, "opening")
        ctx = gk.select_context(role, agent._turn_id)
        opp = agent._last_con if role == "pro" else agent._last_pro
        send_prompt(
            sup,
            role,
            phase=DebatePhase(last),
            context=ctx,
            opponent_last=opp,
            turn_id=agent._turn_id,
        )

    def on_unrecoverable(role: str) -> None:
        agent.logger.event("child_unrecoverable", role=role, turn_id=agent._turn_id)
        agent._ctx.abort_reason = "child_unrecoverable"

    from debate.orchestration.watchdog import Watchdog

    wd = Watchdog(
        sup,
        heartbeat_sec=cfg.heartbeat_sec,
        max_consecutive_misses=cfg.heartbeat_max_consecutive_misses,
        max_restarts_per_child=cfg.max_restarts_per_child,
        pong_check=lambda role: (
            sup._children.get(role) is not None and sup._children.get(role).process.poll() is None
        ),
        on_miss=on_miss,
        on_unrecoverable=on_unrecoverable,
    )
    agent = cls(cfg, gk, judge_llm, sup, router, run_logger, watchdog=wd)
    agent._ctx = Ctx(round_limit=cfg.rounds)
    _log("agent_built", f"watchdog={cfg.heartbeat_sec}s")
    return agent


def _validate_build_config(cfg: Config) -> None:
    """Fail fast on clearly invalid configuration."""
    if cfg.rounds < 1:
        raise ValueError(f"rounds must be >= 1, got {cfg.rounds}")
    if not cfg.judge_model:
        raise ValueError("judge_model must not be empty")
    if cfg.http_timeout_sec <= 0:
        raise ValueError("http_timeout_sec must be positive")


def _log(event: str, detail: str = "") -> None:
    msg = f"{_LOG_PREFIX} {event}"
    if detail:
        msg += f": {detail}"
    sys.stderr.write(msg + "\n")
