"""Shared fixtures for integration tests."""

from __future__ import annotations

import pytest

from debate.shared.config import load_config


@pytest.fixture
def cfg():
    return load_config()
