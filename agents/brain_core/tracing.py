"""OpenTelemetry tracing and Langfuse integration."""

import asyncio
import functools
import os
from collections.abc import Callable
from typing import Any, TypeVar, cast

from langfuse import Langfuse
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from brain_core.config import settings

_F = TypeVar("_F", bound=Callable[..., Any])


class TracingManager:
    """Manages OpenTelemetry and Langfuse tracing."""

    def __init__(self, service_name: str = "secondary-brain") -> None:
        """Initialize tracing manager.

        Args:
            service_name: Name of the service for tracing
        """
        self.service_name = service_name
        self.tracer: trace.Tracer | None = None
        self.langfuse: Langfuse | None = None
        self._initialized = False

    def initialize(self) -> None:
        """Initialize OpenTelemetry and Langfuse."""
        if self._initialized:
            return

        # Initialize OpenTelemetry
        resource = Resource.create(
            {
                "service.name": self.service_name,
                "service.version": "0.1.0",
                "deployment.environment": settings.environment,
            }
        )

        provider = TracerProvider(resource=resource)

        # Add OTLP exporter if endpoint is configured
        otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
        if otlp_endpoint:
            exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
            provider.add_span_processor(BatchSpanProcessor(exporter))

        trace.set_tracer_provider(provider)
        self.tracer = trace.get_tracer(self.service_name)

        # Initialize Langfuse if credentials are available
        if settings.langfuse_public_key and settings.langfuse_secret_key:
            self.langfuse = Langfuse(
                public_key=settings.langfuse_public_key,
                secret_key=settings.langfuse_secret_key,
                host=settings.langfuse_url,
            )

        self._initialized = True

    def get_tracer(self) -> trace.Tracer:
        """Get the OpenTelemetry tracer.

        Returns:
            OpenTelemetry tracer instance
        """
        if not self._initialized:
            self.initialize()
        return self.tracer  # type: ignore

    def get_langfuse(self) -> Langfuse | None:
        """Get the Langfuse client.

        Returns:
            Langfuse client or None if not configured
        """
        if not self._initialized:
            self.initialize()
        return self.langfuse

    def shutdown(self) -> None:
        """Shutdown tracing providers."""
        if self.langfuse:
            self.langfuse.flush()

        # Shutdown OpenTelemetry
        provider = trace.get_tracer_provider()
        if hasattr(provider, "shutdown"):
            provider.shutdown()

        self._initialized = False


# Global tracing manager instance
tracing_manager = TracingManager()


def traced(name: str | None = None) -> Callable[[_F], _F]:
    """Decorator for tracing function calls with OpenTelemetry.

    Args:
        name: Optional span name (defaults to function name)

    Returns:
        Decorated function
    """

    def decorator(func: _F) -> _F:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            tracer = tracing_manager.get_tracer()
            span_name = name or func.__name__

            with tracer.start_as_current_span(span_name) as span:
                span.set_attribute("function.name", func.__name__)
                span.set_attribute("function.module", func.__module__)

                try:
                    result = await func(*args, **kwargs)
                    span.set_status(trace.Status(trace.StatusCode.OK))
                    return result
                except Exception as e:
                    span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                    span.record_exception(e)
                    raise

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            tracer = tracing_manager.get_tracer()
            span_name = name or func.__name__

            with tracer.start_as_current_span(span_name) as span:
                span.set_attribute("function.name", func.__name__)
                span.set_attribute("function.module", func.__module__)

                try:
                    result = func(*args, **kwargs)
                    span.set_status(trace.Status(trace.StatusCode.OK))
                    return result
                except Exception as e:
                    span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                    span.record_exception(e)
                    raise

        # Choose wrapper based on whether function is async
        if asyncio.iscoroutinefunction(func):
            return cast(_F, async_wrapper)
        return cast(_F, sync_wrapper)

    return decorator


def create_trace(name: str, **metadata: Any) -> Any:
    """Create a new Langfuse trace.

    Args:
        name: Trace name
        **metadata: Additional metadata

    Returns:
        Langfuse trace object or None if Langfuse not configured
    """
    langfuse = tracing_manager.get_langfuse()
    if not langfuse:
        return None

    return langfuse.trace(name=name, metadata=metadata)  # type: ignore[attr-defined]


def create_span(trace: Any, name: str, **metadata: Any) -> Any:
    """Create a span within a trace.

    Args:
        trace: Parent trace object
        name: Span name
        **metadata: Additional metadata

    Returns:
        Langfuse span object or None
    """
    if not trace:
        return None

    return trace.span(name=name, metadata=metadata)


def create_generation(span: Any, name: str, model: str, input_data: Any, **metadata: Any) -> Any:
    """Create an LLM generation within a span.

    Args:
        span: Parent span object
        name: Generation name
        model: Model name
        input_data: Input to the model
        **metadata: Additional metadata

    Returns:
        Langfuse generation object or None
    """
    if not span:
        return None

    return span.generation(
        name=name,
        model=model,
        input=input_data,
        metadata=metadata,
    )


def end_generation(generation: Any, output: Any, **metadata: Any) -> None:
    """End an LLM generation with output.

    Args:
        generation: Generation object
        output: Model output
        **metadata: Additional metadata (e.g., usage, cost)
    """
    if not generation:
        return

    generation.end(output=output, metadata=metadata)


def llm_traced(name: str | None = None) -> Callable[[_F], _F]:
    """Decorator for tracing LLM function calls with OpenTelemetry and Langfuse.

    Args:
        name: Optional span name (defaults to function name)

    Returns:
        Decorated function
    """

    def decorator(func: _F) -> _F:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            tracer = tracing_manager.get_tracer()
            span_name = name or func.__name__

            with tracer.start_as_current_span(span_name) as span:
                span.set_attribute("function.name", func.__name__)
                span.set_attribute("function.module", func.__module__)
                span.set_attribute("llm.operation", "true")

                # Extract model from kwargs if present
                if "model" in kwargs:
                    span.set_attribute("llm.model", kwargs["model"])

                try:
                    result = await func(*args, **kwargs)
                    span.set_status(trace.Status(trace.StatusCode.OK))
                    return result
                except Exception as e:
                    span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                    span.record_exception(e)
                    raise

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            tracer = tracing_manager.get_tracer()
            span_name = name or func.__name__

            with tracer.start_as_current_span(span_name) as span:
                span.set_attribute("function.name", func.__name__)
                span.set_attribute("function.module", func.__module__)
                span.set_attribute("llm.operation", "true")

                if "model" in kwargs:
                    span.set_attribute("llm.model", kwargs["model"])

                try:
                    result = func(*args, **kwargs)
                    span.set_status(trace.Status(trace.StatusCode.OK))
                    return result
                except Exception as e:
                    span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                    span.record_exception(e)
                    raise

        if asyncio.iscoroutinefunction(func):
            return cast(_F, async_wrapper)
        return cast(_F, sync_wrapper)

    return decorator
