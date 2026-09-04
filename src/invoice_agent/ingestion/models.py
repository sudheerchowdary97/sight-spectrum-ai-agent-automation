"""Ingestion models: the API-facing record for an ingested document."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from invoice_agent.schemas import DocumentType, utcnow


class IngestedDocument(BaseModel):
    """One invoice attachment that has been extracted from an email and stored.

    This is the hand-off to extraction (Task 4): it locates the raw bytes and
    carries the provenance needed for the audit trail.
    """

    document_id: str
    email_id: str
    sender: str = ""
    subject: str = ""
    attachment_filename: str
    content_type: str
    document_type: DocumentType
    storage_path: str
    size_bytes: int
    content_sha256: str
    ingested_at: datetime = Field(default_factory=utcnow)


class IngestResponse(BaseModel):
    """Response for POST /ingest-invoice."""

    ingested: int
    documents: list[IngestedDocument]
