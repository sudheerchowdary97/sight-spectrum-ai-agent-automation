"""FastAPI application factory and entrypoint for the Agent API.

Run with: ``uvicorn invoice_agent.api.main:app``.

The minimum-required endpoints from the assignment are mounted under
``/api/v1``. Health is implemented in Task 0; the remaining routers
(ingest-invoice, match-po, post-payment-journal, audit-log) are added in
their respective tasks.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from invoice_agent import __version__
from invoice_agent.api.routers import health
from invoice_agent.config import get_settings
from invoice_agent.logging_config import configure_logging, get_logger

API_PREFIX = "/api/v1"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan: configure logging on start-up."""
    configure_logging()
    log = get_logger("api")
    settings = get_settings()
    log.info("api.startup", environment=settings.environment, version=__version__)
    yield
    log.info("api.shutdown")


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    app = FastAPI(
        title="Agentic Invoice-to-Payment API",
        version=__version__,
        description=(
            "Ingest invoices from email, match against Purchase Orders and Goods "
            "Receipts in the ERP, and post Payment Journal entries with a full "
            "audit trail and human oversight for exceptions."
        ),
        lifespan=lifespan,
    )

    # Implemented in Task 0.
    app.include_router(health.router, prefix=API_PREFIX)

    # Mounted in later tasks:
    #   POST {API_PREFIX}/ingest-invoice        (Task 3)
    #   POST {API_PREFIX}/match-po              (Task 6)
    #   POST {API_PREFIX}/post-payment-journal  (Task 9)
    #   GET  {API_PREFIX}/audit-log             (Task 11)
    return app


app = create_app()
