"""Agent implementations — Judge, Pro, Con.

Pro/Con entry modules are **not** imported here so ``python -m debate.agents.pro_agent``
can execute ``if __name__ == '__main__'`` without the runpy double-import bug.
"""

from debate.agents.base_agent import AGENT_ERROR_EXIT, CLEAN_EXIT, BaseAgent
from debate.agents.debater_agent import DebaterAgent, load_debater_system, parse_tool_query

__all__ = [
    "AGENT_ERROR_EXIT",
    "CLEAN_EXIT",
    "BaseAgent",
    "DebaterAgent",
    "load_debater_system",
    "parse_tool_query",
]
