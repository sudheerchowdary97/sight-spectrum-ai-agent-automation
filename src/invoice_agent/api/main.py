"""FastAPI application factory and entrypoint for the Agent API.

Run with: ``uvicorn invoice_agent.api.main:app``.

The minimum-required endpoints from the assignment are mounted under
``/api/v1``. Health (Task 0), ingest-invoice (Task 3), and match-po (Task 6) are
implemented; the remaining routers (post-payment-journal, audit-log) are added
in their respective tasks.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from invoice_agent import __version__
from invoice_agent.api.routers import health, ingest, match
from invoice_agent.config import get_settings
from invoice_agent.ingestion.providers import build_provider
from invoice_agent.ingestion.service import IngestionService
from invoice_agent.logging_config import configure_logging, get_logger
from invoice_agent.matching.service import MatchService, build_match_service

API_PREFIX = "/api/v1"


def create_app(
    ingestion_service: IngestionService | None = None,
    match_service: MatchService | None = None,
) -> FastAPI:
    """Build and configure the FastAPI application.

    Services may be injected (tests); otherwise they are built from settings on
    start-up.
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        configure_logging()
        log = get_logger("api")
        settings = get_settings()
        if getattr(app.state, "ingestion_service", None) is None:
            app.state.ingestion_service = IngestionService(
                provider=build_provider(settings),
                ingested_dir=settings.ingested_dir,
            )
        if getattr(app.state, "match_service", None) is None:
            app.state.match_service = build_match_service(settings)
        log.info("api.startup", environment=settings.environment, version=__version__)
        yield
        log.info("api.shutdown")

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
    # Injected services (tests) are available immediately, without waiting for lifespan.
    app.state.ingestion_service = ingestion_service
    app.state.match_service = match_service

    app.include_router(health.router, prefix=API_PREFIX)
    app.include_router(ingest.router, prefix=API_PREFIX)
    app.include_router(match.router, prefix=API_PREFIX)

    # Mounted in later tasks:
    #   POST {API_PREFIX}/post-payment-journal  (Task 9)
    #   GET  {API_PREFIX}/audit-log             (Task 11)
    return app


app = create_app()
