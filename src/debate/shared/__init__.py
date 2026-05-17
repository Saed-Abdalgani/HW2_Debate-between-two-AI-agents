"""Shared infrastructure — config, gatekeeper, logger, router."""

from debate.shared.budget import BudgetExceeded, Ledger, TransientProviderError, Usage
from debate.shared.config import Config, ConfigError, load_config
from debate.shared.gatekeeper import Gatekeeper
from debate.shared.logger import Logger, LoggerError
from debate.shared.router import SkillRouter
from debate.shared.secrets import MissingSecretError, get_key, redact
from debate.shared.skills import (
    ChatResult,
    LLMClientProto,
    SearchClientProto,
    make_score_skill,
    make_search_skill,
    make_summarise_skill,
)

__all__ = [
    "BudgetExceeded",
    "ChatResult",
    "Config",
    "ConfigError",
    "Gatekeeper",
    "LLMClientProto",
    "Ledger",
    "Logger",
    "LoggerError",
    "MissingSecretError",
    "SearchClientProto",
    "SkillRouter",
    "TransientProviderError",
    "Usage",
    "get_key",
    "load_config",
    "make_score_skill",
    "make_search_skill",
    "make_summarise_skill",
    "redact",
]
