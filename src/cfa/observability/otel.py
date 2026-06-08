# NOTE: This module is internal to CFA — not part of the public API. Use at your own risk.
"""
CFA OpenTelemetry Integration
==============================
Optional OTel instrumentation for CFA pipeline phases.

Each pipeline phase becomes a span with attributes:
- cfa.phase, cfa.decision, cfa.signature_hash, cfa.faults, cfa.replan_count

Usage:
    from cfa.observability.otel import enable_otel
    enable_otel(service_name="cfa-governance", exporter="console")
    # All subsequent KernelOrchestrator.process() calls are traced

Requires: pip install opentelemetry-api opentelemetry-sdk
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any


def _get_tracer():
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider

        provider = trace.get_tracer_provider()
        if not isinstance(provider, TracerProvider):
            resource = Resource.create({"service.name": "cfa-governance"})
            provider = TracerProvider(resource=resource)
            trace.set_tracer_provider(provider)
        return trace.get_tracer("cfa")
    except ImportError:
        return None


def enable_otel(
    service_name: str = "cfa-governance",
    exporter: str = "console",
    otlp_endpoint: str | None = None,
) -> bool:
    """Enable OpenTelemetry tracing for CFA.

    Returns True if OTel was successfully enabled.
    """
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    except ImportError:
        return False

    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)

    if exporter == "otlp" and otlp_endpoint:
        otlp = OTLPSpanExporter(endpoint=otlp_endpoint)
        provider.add_span_processor(BatchSpanProcessor(otlp))
    else:
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

    trace.set_tracer_provider(provider)
    return True


@contextmanager
def cfa_span(name: str, **attrs: Any):
    """Context manager for a CFA span. Falls back to no-op if OTel unavailable."""
    tracer = _get_tracer()
    if tracer is None:
        yield
        return
    with tracer.start_as_current_span(name, attributes=attrs) as span:
        span.set_attribute("cfa.phase", attrs.get("phase", name))
        for k, v in attrs.items():
            span.set_attribute(f"cfa.{k}", str(v))
        yield
