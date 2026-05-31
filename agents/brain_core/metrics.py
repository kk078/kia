"""Metrics collection for monitoring and evaluation."""

import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any


@dataclass
class MetricValue:
    """A single metric value with timestamp."""

    value: float
    timestamp: float = field(default_factory=time.time)
    labels: dict[str, str] = field(default_factory=dict)


class MetricsCollector:
    """Collects and stores metrics for the brain system."""

    def __init__(self) -> None:
        """Initialize metrics collector."""
        self.counters: dict[str, list[MetricValue]] = defaultdict(list)
        self.histograms: dict[str, list[MetricValue]] = defaultdict(list)
        self.gauges: dict[str, list[MetricValue]] = defaultdict(list)

    def increment_counter(self, name: str, value: float = 1.0, **labels: str) -> None:
        """Increment a counter metric.

        Args:
            name: Metric name
            value: Increment value
            **labels: Additional labels
        """
        metric = MetricValue(value=value, labels=labels)
        self.counters[name].append(metric)

    def record_histogram(self, name: str, value: float, **labels: str) -> None:
        """Record a histogram metric (e.g., latency).

        Args:
            name: Metric name
            value: Value to record
            **labels: Additional labels
        """
        metric = MetricValue(value=value, labels=labels)
        self.histograms[name].append(metric)

    def set_gauge(self, name: str, value: float, **labels: str) -> None:
        """Set a gauge metric (current value).

        Args:
            name: Metric name
            value: Current value
            **labels: Additional labels
        """
        metric = MetricValue(value=value, labels=labels)
        self.gauges[name].append(metric)

    def get_counter(self, name: str, **labels: str) -> float:
        """Get the total value of a counter.

        Args:
            name: Metric name
            **labels: Filter by labels

        Returns:
            Total counter value
        """
        metrics = self._filter_metrics(self.counters.get(name, []), labels)
        return sum(m.value for m in metrics)

    def get_histogram_stats(self, name: str, **labels: str) -> dict[str, float]:
        """Get histogram statistics.

        Args:
            name: Metric name
            **labels: Filter by labels

        Returns:
            Dict with count, sum, min, max, avg, p50, p95, p99
        """
        metrics = self._filter_metrics(self.histograms.get(name, []), labels)
        if not metrics:
            return {
                "count": 0,
                "sum": 0,
                "min": 0,
                "max": 0,
                "avg": 0,
                "p50": 0,
                "p95": 0,
                "p99": 0,
            }

        values = sorted([m.value for m in metrics])
        count = len(values)

        return {
            "count": count,
            "sum": sum(values),
            "min": min(values),
            "max": max(values),
            "avg": sum(values) / count,
            "p50": values[int(count * 0.5)] if count > 0 else 0,
            "p95": values[int(count * 0.95)] if count > 0 else 0,
            "p99": values[int(count * 0.99)] if count > 0 else 0,
        }

    def get_gauge(self, name: str, **labels: str) -> float:
        """Get the current value of a gauge.

        Args:
            name: Metric name
            **labels: Filter by labels

        Returns:
            Current gauge value (most recent)
        """
        metrics = self._filter_metrics(self.gauges.get(name, []), labels)
        return metrics[-1].value if metrics else 0.0

    def _filter_metrics(
        self, metrics: list[MetricValue], labels: dict[str, str]
    ) -> list[MetricValue]:
        """Filter metrics by labels.

        Args:
            metrics: List of metrics
            labels: Labels to filter by

        Returns:
            Filtered metrics
        """
        if not labels:
            return metrics

        return [m for m in metrics if all(m.labels.get(k) == v for k, v in labels.items())]

    def get_all_metrics(self) -> dict[str, Any]:
        """Get all metrics in a structured format.

        Returns:
            Dict with all metrics organized by type
        """
        result: dict[str, Any] = {
            "counters": {},
            "histograms": {},
            "gauges": {},
        }

        for name in self.counters:
            result["counters"][name] = self.get_counter(name)

        for name in self.histograms:
            result["histograms"][name] = self.get_histogram_stats(name)

        for name in self.gauges:
            result["gauges"][name] = self.get_gauge(name)

        return result

    def clear(self) -> None:
        """Clear all metrics."""
        self.counters.clear()
        self.histograms.clear()
        self.gauges.clear()


# Global metrics collector instance
metrics = MetricsCollector()


class Timer:
    """Context manager for timing operations."""

    def __init__(self, name: str, **labels: str) -> None:
        """Initialize timer.

        Args:
            name: Metric name for the timer
            **labels: Additional labels
        """
        self.name = name
        self.labels = labels
        self.start_time: float | None = None

    def __enter__(self) -> "Timer":
        """Start the timer."""
        self.start_time = time.time()
        return self

    def __exit__(self, *args: Any) -> None:
        """Stop the timer and record the duration."""
        if self.start_time is not None:
            duration = time.time() - self.start_time
            metrics.record_histogram(self.name, duration, **self.labels)


def track_llm_call(
    model: str,
    input_tokens: int,
    output_tokens: int,
    duration: float,
    cost: float | None = None,
) -> None:
    """Track an LLM API call.

    Args:
        model: Model name
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        duration: Call duration in seconds
        cost: Cost in USD (if known)
    """
    metrics.increment_counter("llm_calls_total", model=model)
    metrics.increment_counter("llm_input_tokens_total", input_tokens, model=model)
    metrics.increment_counter("llm_output_tokens_total", output_tokens, model=model)
    metrics.record_histogram("llm_call_duration_seconds", duration, model=model)

    if cost is not None:
        metrics.increment_counter("llm_cost_usd_total", cost, model=model)


def track_agent_invocation(agent_type: str, success: bool = True) -> None:
    """Track an agent invocation.

    Args:
        agent_type: Type of agent (e.g., "orchestrator", "researcher")
        success: Whether the invocation succeeded
    """
    metrics.increment_counter(
        "agent_invocations_total",
        agent_type=agent_type,
        status="success" if success else "error",
    )


def track_memory_operation(operation: str, memory_type: str) -> None:
    """Track a memory operation.

    Args:
        operation: Operation type (e.g., "store", "retrieve")
        memory_type: Memory type (e.g., "episodic", "semantic")
    """
    metrics.increment_counter(
        "memory_operations_total",
        operation=operation,
        memory_type=memory_type,
    )


def track_api_request(endpoint: str, status_code: int, duration: float) -> None:
    """Track an API request.

    Args:
        endpoint: API endpoint
        status_code: HTTP status code
        duration: Request duration in seconds
    """
    metrics.increment_counter(
        "api_requests_total",
        endpoint=endpoint,
        status_code=str(status_code),
    )
    metrics.record_histogram(
        "api_request_duration_seconds",
        duration,
        endpoint=endpoint,
    )


def _esc(v: str) -> str:
    """Escape a Prometheus label value."""
    return v.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")


def render_prometheus() -> str:
    """Render collected metrics in Prometheus text exposition format.

    Aggregates per metric name (single-user scope); histograms are exported as
    summaries with p50/p95/p99 quantiles. Suitable for the configured Prometheus
    scrape of GET /metrics.
    """
    out: list[str] = []
    for name, vals in metrics.counters.items():
        total = sum(v.value for v in vals)
        out.append(f"# TYPE {name} counter")
        out.append(f"{name} {total}")
    for name in metrics.histograms:
        stats = metrics.get_histogram_stats(name)
        out.append(f"# TYPE {name} summary")
        out.append(f"{name}_count {stats['count']}")
        out.append(f"{name}_sum {stats['sum']}")
        for label, key in (("0.5", "p50"), ("0.95", "p95"), ("0.99", "p99")):
            out.append(f'{name}{{quantile="{label}"}} {stats[key]}')
    for name in metrics.gauges:
        out.append(f"# TYPE {name} gauge")
        out.append(f"{name} {metrics.get_gauge(name)}")
    return "\n".join(out) + "\n"
