"""Tests for observability setup (Task 12).

The real Phoenix export runs in Docker. Here we verify the guard behaviour:
disabled → no-op; enabled-but-libs-absent → graceful no-op (never raises).
"""

from __future__ import annotations

import invoice_agent.observability as obs
from invoice_agent.config import Settings


def test_tracing_disabled_is_noop() -> None:
    settings = Settings(tracing_enabled=False)
    assert obs.configure_tracing(settings) is None


def test_tracing_enabled_is_graceful_without_phoenix(monkeypatch) -> None:
    # On the host the observability libs aren't installed; setup must not raise.
    monkeypatch.setattr(obs, "_configured", False)
    settings = Settings(tracing_enabled=True, phoenix_collector_endpoint="http://phoenix:6006")
    # Returns None (import/collector failure caught) rather than raising.
    assert obs.configure_tracing(settings) is None
