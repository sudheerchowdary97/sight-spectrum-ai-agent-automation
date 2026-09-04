"""Invoice ingestion endpoint (POST /api/v1/ingest-invoice)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile

from invoice_agent.ingestion.models import IngestResponse
from invoice_agent.ingestion.service import IngestionService

router = APIRouter(tags=["ingestion"])


def get_ingestion_service(request: Request) -> IngestionService:
    """Dependency: the ingestion service held on application state."""
    return request.app.state.ingestion_service


@router.post(
    "/ingest-invoice",
    response_model=IngestResponse,
    summary="Ingest invoice(s) from an upload or the configured mailbox",
)
async def ingest_invoice(
    file: UploadFile | None = File(
        default=None, description="Optional invoice document or .eml to ingest directly"
    ),
    limit: int | None = Query(
        default=None, ge=1, description="Max emails to pull when polling the mailbox"
    ),
    service: IngestionService = Depends(get_ingestion_service),
) -> IngestResponse:
    """Ingest invoices.

    * If a **file** is uploaded, that document (or ``.eml``) is ingested directly.
    * Otherwise the configured provider (folder replay / Graph / Gmail) is polled;
      already-seen emails are skipped.
    """
    if file is not None:
        content = await file.read()
        documents = service.ingest_raw(
            filename=file.filename or "upload.bin",
            content_type=file.content_type,
            content=content,
        )
    else:
        documents = service.ingest_from_provider(limit)

    return IngestResponse(ingested=len(documents), documents=documents)
