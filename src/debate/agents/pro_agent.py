"""Pro debater entry — stance constant only (P6.3)."""

from debate.agents.debater_agent import DebaterAgent


class ProAgent(DebaterAgent):
    STANCE = "pro"


if __name__ == "__main__":
    ProAgent.bootstrap()
