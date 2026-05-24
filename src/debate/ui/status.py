"""Live debate status panel (rich) — structured summary only (P8.2)."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from rich.panel import Panel
from rich.table import Table
from rich.text import Text


@dataclass
class DebateStatus:
    motion: str = ""
    speaker: str = "—"
    round_num: int = 0
    round_limit: int = 1
    llm_mode: str = "live"
    pro_snippet: str = ""
    con_snippet: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    usd_spent: float = 0.0
    max_usd: float = 0.0
    started_at: float = field(default_factory=time.monotonic)

    def elapsed_sec(self) -> float:
        return time.monotonic() - self.started_at


def truncate(text: str, limit: int = 120) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= limit:
        return cleaned or "—"
    return cleaned[: limit - 1] + "…"


def status_from_agent(agent: Any, *, speaker: str) -> DebateStatus:
    snap = agent.gk.ledger.snapshot()
    t0 = getattr(agent, "_ui_started_at", None)
    if t0 is None:
        t0 = time.monotonic()
    mode = str(getattr(agent, "_debate_llm_mode", "live"))
    return DebateStatus(
        motion=agent._motion,
        speaker=speaker,
        round_num=agent._ctx.round,
        round_limit=agent._ctx.round_limit,
        llm_mode=mode,
        pro_snippet=truncate(agent._last_pro),
        con_snippet=truncate(agent._last_con),
        tokens_in=int(snap.get("tokens_in", 0)),
        tokens_out=int(snap.get("tokens_out", 0)),
        usd_spent=float(snap.get("usd_spent", 0)),
        max_usd=float(agent.cfg.max_usd_per_debate),
        started_at=float(t0),
    )


def render_panel(status: DebateStatus) -> Panel:
    round_line = f"Round {status.round_num} / {status.round_limit}"
    table = Table.grid(padding=(0, 1))
    table.add_row("Motion", status.motion[:72] + ("…" if len(status.motion) > 72 else ""))
    table.add_row("Speaker", status.speaker.upper())
    if status.llm_mode == "stub":
        table.add_row("LLM", Text("STUB (pass --stub only for tests)", style="yellow"))
    table.add_row("Round", Text(round_line, style="bold cyan"))
    table.add_row(
        "Budget",
        f"${status.usd_spent:.4f} / ${status.max_usd:.2f}  |  "
        f"tokens {status.tokens_in} in / {status.tokens_out} out",
    )
    table.add_row("Elapsed", f"{status.elapsed_sec():.1f}s")
    sides = Table.grid(expand=True)
    sides.add_column("Pro", ratio=1)
    sides.add_column("Con", ratio=1)
    sides.add_row(
        Text(status.pro_snippet, style="green"),
        Text(status.con_snippet, style="cyan"),
    )
    table.add_row("Last replies", sides)
    return Panel(
        table,
        title="HW2 Debate",
        title_align="left",
        subtitle=round_line,
        subtitle_align="left",
        border_style="blue",
    )
