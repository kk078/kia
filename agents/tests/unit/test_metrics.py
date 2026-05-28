"""Tests for metrics collection."""

import pytest

from brain_core.metrics import (
    MetricsCollector,
    Timer,
    track_agent_invocation,
    track_api_request,
    track_llm_call,
    track_memory_operation,
)


class TestMetricsCollector:
    """Test MetricsCollector functionality."""

    @pytest.fixture
    def collector(self) -> MetricsCollector:
        """Create metrics collector instance."""
        return MetricsCollector()

    def test_increment_counter(self, collector: MetricsCollector) -> None:
        """Test counter increment."""
        collector.increment_counter("test_counter", 1.0)
        collector.increment_counter("test_counter", 2.0)

        total = collector.get_counter("test_counter")
        assert total == 3.0

    def test_counter_with_labels(self, collector: MetricsCollector) -> None:
        """Test counter with labels."""
        collector.increment_counter("requests", 1.0, endpoint="/api/v1/test")
        collector.increment_counter("requests", 1.0, endpoint="/api/v1/test")
        collector.increment_counter("requests", 1.0, endpoint="/api/v1/other")

        total = collector.get_counter("requests")
        assert total == 3.0

        filtered = collector.get_counter("requests", endpoint="/api/v1/test")
        assert filtered == 2.0

    def test_record_histogram(self, collector: MetricsCollector) -> None:
        """Test histogram recording."""
        collector.record_histogram("latency", 0.1)
        collector.record_histogram("latency", 0.2)
        collector.record_histogram("latency", 0.3)

        stats = collector.get_histogram_stats("latency")
        assert stats["count"] == 3
        assert abs(stats["sum"] - 0.6) < 0.001
        assert stats["min"] == 0.1
        assert stats["max"] == 0.3
        assert abs(stats["avg"] - 0.2) < 0.001

    def test_histogram_percentiles(self, collector: MetricsCollector) -> None:
        """Test histogram percentile calculations."""
        for i in range(100):
            collector.record_histogram("values", float(i))

        stats = collector.get_histogram_stats("values")
        assert stats["p50"] == 50.0
        assert stats["p95"] == 95.0
        assert stats["p99"] == 99.0

    def test_set_gauge(self, collector: MetricsCollector) -> None:
        """Test gauge setting."""
        collector.set_gauge("temperature", 20.0)
        assert collector.get_gauge("temperature") == 20.0

        collector.set_gauge("temperature", 25.0)
        assert collector.get_gauge("temperature") == 25.0

    def test_get_all_metrics(self, collector: MetricsCollector) -> None:
        """Test getting all metrics."""
        collector.increment_counter("counter1", 1.0)
        collector.record_histogram("histogram1", 0.5)
        collector.set_gauge("gauge1", 10.0)

        all_metrics = collector.get_all_metrics()
        assert "counters" in all_metrics
        assert "histograms" in all_metrics
        assert "gauges" in all_metrics
        assert all_metrics["counters"]["counter1"] == 1.0
        assert all_metrics["gauges"]["gauge1"] == 10.0

    def test_clear_metrics(self, collector: MetricsCollector) -> None:
        """Test clearing metrics."""
        collector.increment_counter("test", 1.0)
        collector.clear()

        assert collector.get_counter("test") == 0.0


class TestTimer:
    """Test Timer context manager."""

    def test_timer_records_duration(self) -> None:
        """Test that timer records duration."""
        import time

        from brain_core.metrics import metrics

        metrics.clear()

        with Timer("test_operation"):
            time.sleep(0.1)

        stats = metrics.get_histogram_stats("test_operation")
        assert stats["count"] == 1
        assert stats["avg"] >= 0.1


class TestTrackingFunctions:
    """Test tracking helper functions."""

    def test_track_llm_call(self) -> None:
        """Test LLM call tracking."""
        from brain_core.metrics import metrics

        metrics.clear()
        track_llm_call(
            model="test-model",
            input_tokens=100,
            output_tokens=50,
            duration=1.5,
            cost=0.01,
        )

        assert metrics.get_counter("llm_calls_total", model="test-model") == 1.0
        assert metrics.get_counter("llm_input_tokens_total", model="test-model") == 100.0
        assert metrics.get_counter("llm_output_tokens_total", model="test-model") == 50.0
        assert metrics.get_counter("llm_cost_usd_total", model="test-model") == 0.01

    def test_track_agent_invocation(self) -> None:
        """Test agent invocation tracking."""
        from brain_core.metrics import metrics

        metrics.clear()
        track_agent_invocation("orchestrator", success=True)
        track_agent_invocation("orchestrator", success=False)

        success_count = metrics.get_counter(
            "agent_invocations_total", agent_type="orchestrator", status="success"
        )
        error_count = metrics.get_counter(
            "agent_invocations_total", agent_type="orchestrator", status="error"
        )
        assert success_count == 1.0
        assert error_count == 1.0

    def test_track_memory_operation(self) -> None:
        """Test memory operation tracking."""
        from brain_core.metrics import metrics

        metrics.clear()
        track_memory_operation("store", "episodic")
        track_memory_operation("retrieve", "episodic")

        store_count = metrics.get_counter(
            "memory_operations_total", operation="store", memory_type="episodic"
        )
        retrieve_count = metrics.get_counter(
            "memory_operations_total", operation="retrieve", memory_type="episodic"
        )
        assert store_count == 1.0
        assert retrieve_count == 1.0

    def test_track_api_request(self) -> None:
        """Test API request tracking."""
        from brain_core.metrics import metrics

        metrics.clear()
        track_api_request("/api/v1/test", 200, 0.5)
        track_api_request("/api/v1/test", 200, 0.3)
        track_api_request("/api/v1/test", 500, 0.1)

        success_count = metrics.get_counter(
            "api_requests_total", endpoint="/api/v1/test", status_code="200"
        )
        error_count = metrics.get_counter(
            "api_requests_total", endpoint="/api/v1/test", status_code="500"
        )
        assert success_count == 2.0
        assert error_count == 1.0
