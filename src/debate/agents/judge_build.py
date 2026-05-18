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

    def on_miss(role: str) -> None:
        agent.logger.event("heartbeat_miss", role=role, turn_id=agent._turn_id)
        from debate.orchestration.state_machine import Event
        # We need a thread-safe way to transition, or we just emit the abort.
        # But this is test_recovery_chaos so it needs to recover!
        sup.terminate(role)
        sup.spawn(role)
        # after respawn, replay prompt
        from debate.agents.judge_child import send_prompt, send_init
        from debate.sdk.payloads import DebatePhase
        send_init(sup, cfg, agent._motion, role, agent._turn_id)
        last = agent._ctx.last_outbound_per_role.get(role, "opening")
        ctx = gk.select_context(role, agent._turn_id)
        opp = agent._last_con if role == "pro" else agent._last_pro
        send_prompt(sup, role, phase=DebatePhase(last), context=ctx, opponent_last=opp, turn_id=agent._turn_id)

    def on_unrecoverable(role: str) -> None:
        agent.logger.event("child_unrecoverable", role=role, turn_id=agent._turn_id)
        agent._ctx.abort_reason = "child_unrecoverable"
        # The main thread loop will abort if we could signal it.

    from debate.orchestration.watchdog import Watchdog
    wd = Watchdog(
        sup,
        heartbeat_sec=cfg.heartbeat_sec,
        max_consecutive_misses=cfg.heartbeat_max_consecutive_misses,
        max_restarts_per_child=cfg.max_restarts_per_child,
        pong_check=lambda role: sup._children.get(role) is not None and sup._children.get(role).process.poll() is None,
        on_miss=on_miss,
        on_unrecoverable=on_unrecoverable,
    )

    agent = cls(cfg, gk, judge_llm, sup, router, run_logger, watchdog=wd)
    agent._ctx = Ctx(round_limit=cfg.rounds)

    return agent
