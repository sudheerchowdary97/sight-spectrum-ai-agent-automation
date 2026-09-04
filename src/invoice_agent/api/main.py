"""FastAPI application factory and entrypoint for the Agent API.

Run with: ``uvicorn invoice_agent.api.main:app``.

Endpoints under ``/api/v1``: health (Task 0), ingest-invoice (Task 3), match-po
(Task 6), exceptions approve/reject (Task 8). Posting (Task 9) and audit-log
(Task 11) follow.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from invoice_agent import __version__
from invoice_agent.api.routers import (
    audit,
    exceptions,
    health,
    ingest,
    match,
    payment,
    remittance,
)
from invoice_agent.ar.service import RemittanceService
from invoice_agent.audit_log import AuditLog
from invoice_agent.config import get_settings
from invoice_agent.erp_client import ErpClient
from invoice_agent.hitl.service import HumanReviewService
from invoice_agent.hitl.store import ExceptionStore
from invoice_agent.ingestion.providers import build_provider
from invoice_agent.ingestion.service import IngestionService
from invoice_agent.logging_config import configure_logging, get_logger
from invoice_agent.matching.service import MatchService, build_match_service
from invoice_agent.posting import ErpPaymentPoster, PostingService

API_PREFIX = "/api/v1"


def create_app(
    ingestion_service: IngestionService | None = None,
    match_service: MatchService | None = None,
    review_service: HumanReviewService | None = None,
    posting_service: PostingService | None = None,
    remittance_service: RemittanceService | None = None,
    audit_log: AuditLog | None = None,
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

        if getattr(app.state, "audit_log", None) is None:
            app.state.audit_log = AuditLog()
        poster = ErpPaymentPoster(ErpClient(settings.erp_base_url))
        if getattr(app.state, "review_service", None) is None:
            app.state.review_service = HumanReviewService(
                ExceptionStore(), poster, app.state.audit_log
            )
        if getattr(app.state, "posting_service", None) is None:
            app.state.posting_service = PostingService(poster, app.state.audit_log)
        if getattr(app.state, "remittance_service", None) is None:
            app.state.remittance_service = RemittanceService(
                ErpClient(settings.erp_base_url), app.state.audit_log
            )
        if getattr(app.state, "ingestion_service", None) is None:
            app.state.ingestion_service = IngestionService(
                provider=build_provider(settings),
                ingested_dir=settings.ingested_dir,
            )
        if getattr(app.state, "match_service", None) is None:
            app.state.match_service = build_match_service(
                settings, reviewer=app.state.review_service
            )
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
    app.state.review_service = review_service
    app.state.posting_service = posting_service
    app.state.remittance_service = remittance_service
    app.state.audit_log = audit_log

    app.include_router(health.router, prefix=API_PREFIX)
    app.include_router(ingest.router, prefix=API_PREFIX)
    app.include_router(match.router, prefix=API_PREFIX)
    app.include_router(exceptions.router, prefix=API_PREFIX)
    app.include_router(payment.router, prefix=API_PREFIX)
    app.include_router(remittance.router, prefix=API_PREFIX)
    app.include_router(audit.router, prefix=API_PREFIX)

    return app


app = create_app()
