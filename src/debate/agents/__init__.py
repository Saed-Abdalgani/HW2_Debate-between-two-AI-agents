"""Agent implementations — Judge, Pro, Con.

Pro/Con entry modules are **not** imported here so ``python -m debate.agents.pro_agent``
can execute ``if __name__ == '__main__'`` without the runpy double-import bug.
"""

from debate.agents.base_agent import AGENT_ERROR_EXIT, CLEAN_EXIT, BaseAgent
from debate.agents.debater_agent import DebaterAgent
from debate.agents.debater_prompt import load_debater_system, parse_tool_query
from debate.agents.judge_agent import JudgeAgent
from debate.agents.judge_tie_break import tie_break
from debate.agents.judge_verdict import validate_verdict_stages

__all__ = [
    "AGENT_ERROR_EXIT",
    "CLEAN_EXIT",
    "BaseAgent",
    "DebaterAgent",
    "JudgeAgent",
    "load_debater_system",
    "parse_tool_query",
    "tie_break",
    "validate_verdict_stages",
]
