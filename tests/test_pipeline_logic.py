"""Pure pipeline logic: cache keying, mode selection, and response caching."""

import time

import pytest

from medical_agent.pipeline import (
    cache_clear,
    cache_get,
    cache_key,
    cache_set,
    should_run_parallel,
)
from medical_agent.utils.intelligent_router import QueryAnalysis


def analysis(**overrides) -> QueryAnalysis:
    base = {
        "is_medical": True,
        "confidence": 0.9,
        "intent": "interaction",
        "complexity": 4,
        "required_agents": ["researcher", "validator"],
        "max_iterations": {"researcher": 3, "validator": 2, "analyst": 1},
        "reasoning": "",
        "suggested_tools": ["graph_db", "cypher"],
        "rejection_message": None,
        "use_chain_of_thought": False,
        "cot_reasoning_steps": None,
    }
    base.update(overrides)
    return QueryAnalysis(**base)


class TestCacheKey:
    def test_word_order_does_not_change_the_key(self):
        """Semantically identical phrasings should hit the same cache entry."""
        assert cache_key("SEQ", "s1", "aspirin warfarin interaction") == cache_key(
            "SEQ", "s1", "interaction warfarin aspirin"
        )

    def test_case_and_spacing_are_normalised(self):
        assert cache_key("SEQ", "s1", "Aspirin   Warfarin") == cache_key(
            "SEQ", "s1", "aspirin warfarin"
        )

    def test_sessions_do_not_share_entries(self):
        """Answers depend on conversation context, so caching across sessions leaks."""
        assert cache_key("SEQ", "s1", "q") != cache_key("SEQ", "s2", "q")

    def test_modes_do_not_share_entries(self):
        assert cache_key("SEQ", "s1", "q") != cache_key("PARALLEL", "s1", "q")

    def test_different_questions_differ(self):
        assert cache_key("SEQ", "s1", "aspirin") != cache_key("SEQ", "s1", "warfarin")


class TestResponseCache:
    def setup_method(self):
        cache_clear()

    def test_round_trips_a_value(self):
        cache_set("k", "answer")
        assert cache_get("k") == "answer"

    def test_missing_key_returns_none(self):
        assert cache_get("absent") is None

    def test_entries_expire(self, monkeypatch):
        """Regression: the TTL constant existed but was never enforced."""
        import medical_agent.pipeline as pipeline_module

        cache_set("k", "answer")
        # Capture the real clock before patching, or the replacement calls itself.
        real_time = time.time
        monkeypatch.setattr(
            pipeline_module.time,
            "time",
            lambda: real_time() + pipeline_module.CACHE_TTL_SECONDS + 1,
        )
        assert cache_get("k") is None

    def test_cache_is_bounded(self):
        import medical_agent.pipeline as pipeline_module

        for index in range(pipeline_module._CACHE_MAX_ENTRIES + 25):
            cache_set(f"k{index}", "v")
        assert len(pipeline_module._RESPONSE_CACHE) <= pipeline_module._CACHE_MAX_ENTRIES


class TestModeSelection:
    def test_complex_interaction_runs_in_parallel(self):
        assert should_run_parallel(analysis()) is True

    @pytest.mark.parametrize(
        "overrides",
        [
            {"complexity": 2},
            {"suggested_tools": ["graph_db"]},
            {"intent": "drug_info"},
        ],
    )
    def test_otherwise_runs_sequentially(self, overrides):
        """Fanning out costs concurrent model calls; only complex, multi-source,
        interaction questions earn that."""
        assert should_run_parallel(analysis(**overrides)) is False
