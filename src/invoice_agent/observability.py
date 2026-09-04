"""Observability: OpenTelemetry tracing to Arize Phoenix (Task 12).

``configure_tracing`` registers a Phoenix/OTLP tracer provider and instruments
LlamaIndex (which covers RAG retrieval and LlamaIndex-mediated LLM calls). It is
**best-effort**: a no-op when tracing is disabled, and it never raises if the
observability libraries or the Phoenix collector are unavailable — so the
pipeline runs identically with or without Phoenix.
"""

from __future__ import annotations

from invoice_agent.config import Settings
from invoice_agent.logging_config import get_logger

log = get_logger("observability")

_configured = False


def configure_tracing(settings: Settings) -> object | None:
    """Set up Phoenix tracing + LlamaIndex instrumentation. Returns the provider or None."""
    global _configured
    if not settings.tracing_enabled:
        log.info("tracing.disabled_by_config")
        return None
    if _configured:
        return None

    try:
        from openinference.instrumentation.llama_index import LlamaIndexInstrumentor
        from phoenix.otel import register

        endpoint = f"{settings.phoenix_collector_endpoint.rstrip('/')}/v1/traces"
        tracer_provider = register(project_name=settings.app_name, endpoint=endpoint)
        LlamaIndexInstrumentor().instrument(tracer_provider=tracer_provider)
        _configured = True
        log.info("tracing.enabled", endpoint=endpoint, project=settings.app_name)
        return tracer_provider
    except Exception as exc:  # pragma: no cover - best-effort; deps/collector optional
        log.warning("tracing.setup_failed", error=str(exc))
        return None
