from __future__ import annotations

from research_agent.tools.cost import SEARCH_PRICING, CostTracker


class TestLLMCallCost:
    def test_opus47_input_cost(self) -> None:
        tracker = CostTracker()
        # 1 000 input tokens at $5/1M = $0.005
        cost = tracker.record_llm_call("claude-opus-4-7-20260416", 1_000, 0)
        assert abs(cost - 0.005) < 1e-9

    def test_opus47_output_cost(self) -> None:
        tracker = CostTracker()
        # 1 000 output tokens at $25/1M = $0.025
        cost = tracker.record_llm_call("claude-opus-4-7-20260416", 0, 1_000)
        assert abs(cost - 0.025) < 1e-9

    def test_opus47_combined_cost(self) -> None:
        tracker = CostTracker()
        # 1 000 in + 500 out → 0.005 + 0.0125 = 0.0175
        cost = tracker.record_llm_call("claude-opus-4-7-20260416", 1_000, 500)
        assert abs(cost - 0.0175) < 1e-9

    def test_gpt54_mini_cost(self) -> None:
        tracker = CostTracker()
        # $0.75/1M in, $4.50/1M out
        # 2 000 in + 1 000 out → 0.0015 + 0.0045 = 0.006
        cost = tracker.record_llm_call("gpt-5.4-mini", 2_000, 1_000)
        assert abs(cost - 0.006) < 1e-9

    def test_gemini_flash_cost(self) -> None:
        tracker = CostTracker()
        # $0.50/1M in, $3.0/1M out
        cost = tracker.record_llm_call("gemini-3-flash-preview", 1_000_000, 1_000_000)
        assert abs(cost - (0.50 + 3.0)) < 1e-9

    def test_tokens_accumulated(self) -> None:
        tracker = CostTracker()
        tracker.record_llm_call("gpt-5.4-mini", 100, 50)
        tracker.record_llm_call("gpt-5.4-mini", 200, 100)
        assert tracker.total_tokens_in == 300
        assert tracker.total_tokens_out == 150

    def test_dollars_accumulated(self) -> None:
        tracker = CostTracker()
        c1 = tracker.record_llm_call("gpt-5.4-mini", 1_000, 0)
        c2 = tracker.record_llm_call("gpt-5.4-mini", 1_000, 0)
        assert abs(tracker.total_dollars - (c1 + c2)) < 1e-9

    def test_unknown_model_returns_zero_cost(self) -> None:
        tracker = CostTracker()
        cost = tracker.record_llm_call("unknown-model-xyz", 1_000, 500)
        assert cost == 0.0

    def test_unknown_model_tokens_still_accumulated(self) -> None:
        tracker = CostTracker()
        tracker.record_llm_call("unknown-model-xyz", 100, 50)
        assert tracker.total_tokens_in == 100
        assert tracker.total_tokens_out == 50

    def test_dollars_by_provider_grouped(self) -> None:
        tracker = CostTracker()
        tracker.record_llm_call("claude-opus-4-7-20260416", 1_000, 0)
        tracker.record_llm_call("gpt-5.4-mini", 1_000, 0)
        assert "anthropic" in tracker.dollars_by_provider
        assert "openai" in tracker.dollars_by_provider


class TestSearchCallCost:
    def test_brave_cost(self) -> None:
        tracker = CostTracker()
        cost = tracker.record_search_call("brave")
        assert abs(cost - SEARCH_PRICING["brave"]) < 1e-9

    def test_exa_cost(self) -> None:
        tracker = CostTracker()
        cost = tracker.record_search_call("exa")
        assert abs(cost - SEARCH_PRICING["exa"]) < 1e-9

    def test_search_calls_accumulate(self) -> None:
        tracker = CostTracker()
        tracker.record_search_call("brave")
        tracker.record_search_call("exa")
        tracker.record_search_call("brave")
        assert tracker.total_search_calls == 3

    def test_calls_by_provider_tracked(self) -> None:
        tracker = CostTracker()
        tracker.record_search_call("brave")
        tracker.record_search_call("brave")
        tracker.record_search_call("exa")
        assert tracker.calls_by_provider["brave"] == 2
        assert tracker.calls_by_provider["exa"] == 1

    def test_dollars_include_search_costs(self) -> None:
        tracker = CostTracker()
        tracker.record_search_call("brave")
        tracker.record_search_call("exa")
        expected = SEARCH_PRICING["brave"] + SEARCH_PRICING["exa"]
        assert abs(tracker.total_dollars - expected) < 1e-9

    def test_unknown_search_provider_returns_zero(self) -> None:
        tracker = CostTracker()
        cost = tracker.record_search_call("unknown_provider")
        assert cost == 0.0


class TestSummary:
    def test_summary_keys_present(self) -> None:
        tracker = CostTracker()
        summary = tracker.summary()
        required_keys = {
            "total_tokens_in",
            "total_tokens_out",
            "total_tokens",
            "total_dollars",
            "total_search_calls",
            "calls_by_provider",
            "dollars_by_provider",
        }
        assert required_keys.issubset(summary.keys())

    def test_summary_total_tokens_is_sum(self) -> None:
        tracker = CostTracker()
        tracker.record_llm_call("gpt-5.4-mini", 300, 100)
        summary = tracker.summary()
        assert summary["total_tokens"] == 400

    def test_summary_empty_tracker(self) -> None:
        tracker = CostTracker()
        summary = tracker.summary()
        assert summary["total_tokens_in"] == 0
        assert summary["total_tokens_out"] == 0
        assert summary["total_dollars"] == 0.0
        assert summary["total_search_calls"] == 0
        assert summary["calls_by_provider"] == {}
        assert summary["dollars_by_provider"] == {}

    def test_summary_reflects_mixed_calls(self) -> None:
        tracker = CostTracker()
        tracker.record_llm_call("claude-opus-4-7-20260416", 1_000, 500)
        tracker.record_search_call("brave")
        summary = tracker.summary()
        assert summary["total_search_calls"] == 1
        assert summary["total_tokens_in"] == 1_000
        assert summary["total_tokens_out"] == 500
