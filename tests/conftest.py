"""Test configuration.

CI runs without API keys or a database. Nothing here may make a network call, so
the tests cover pure logic and the request paths that resolve before any model or
graph access happens.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Set before importing anything that reads configuration at import time.
os.environ.setdefault("GROQ_API_KEY", "test-key-not-used")
os.environ.setdefault("GRAPH_ENABLED", "false")
os.environ.setdefault("DAILY_QUERY_LIMIT", "5")

import pytest  # noqa: E402


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from medical_agent.api.server import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def reset_state():
    """Keep per-process singletons from leaking between tests."""
    from medical_agent.utils.memory_manager import MemoryManager
    from medical_agent.utils.rate_limit import get_limiter

    get_limiter().reset()
    MemoryManager.reset()
    yield
    get_limiter().reset()
    MemoryManager.reset()
