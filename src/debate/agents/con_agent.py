"""Con debater entry — stance constant only (P6.3)."""

from debate.agents.debater_agent import DebaterAgent


class ConAgent(DebaterAgent):
    STANCE = "con"


if __name__ == "__main__":
    ConAgent.bootstrap()
