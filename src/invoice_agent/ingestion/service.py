"""Ingestion service: fetch emails, extract/classify/persist invoice attachments.

Extraction of invoice *fields* happens later (Task 4, Docling). This stage only
identifies invoice-like attachments, stores their raw bytes, and records
provenance + a content hash for downstream duplicate detection.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from invoice_agent.ingestion.models import IngestedDocument
from invoice_agent.ingestion.providers.base import EmailProvider, FetchedEmail
from invoice_agent.ingestion.providers.folder import parse_eml
from invoice_agent.logging_config import get_logger
from invoice_agent.schemas import DocumentType

log = get_logger("ingestion")

# Attachment content-types / extensions we treat as invoice documents.
_CONTENT_TYPE_MAP: dict[str, DocumentType] = {
    "application/pdf": DocumentType.PDF,
    "image/png": DocumentType.IMAGE,
    "image/jpeg": DocumentType.IMAGE,
    "text/html": DocumentType.HTML,
}
_EXTENSION_MAP: dict[str, DocumentType] = {
    ".pdf": DocumentType.PDF,
    ".png": DocumentType.IMAGE,
    ".jpg": DocumentType.IMAGE,
    ".jpeg": DocumentType.IMAGE,
    ".html": DocumentType.HTML,
    ".htm": DocumentType.HTML,
}


def classify_document(content_type: str | None, filename: str) -> DocumentType | None:
    """Map an attachment to a document type, or ``None`` if not an invoice doc."""
    ctype = (content_type or "").split(";")[0].strip().lower()
    if ctype in _CONTENT_TYPE_MAP:
        return _CONTENT_TYPE_MAP[ctype]
    return _EXTENSION_MAP.get(Path(filename).suffix.lower())


class IngestionService:
    """Turn raw emails into stored, classified :class:`IngestedDocument` records."""

    def __init__(self, provider: EmailProvider, ingested_dir: str | Path) -> None:
        self._provider = provider
        self._dir = Path(ingested_dir)
        self._processed: set[str] = set()

    def ingest_from_provider(self, limit: int | None = None) -> list[IngestedDocument]:
        """Pull emails from the provider and ingest any new ones."""
        documents: list[IngestedDocument] = []
        for email in self._provider.fetch(limit):
            if email.email_id in self._processed:
                continue  # replay idempotency: skip already-seen emails
            documents.extend(self._ingest_email(email))
            self._processed.add(email.email_id)
        log.info("ingest.provider", new_documents=len(documents))
        return documents

    def ingest_raw(
        self,
        *,
        filename: str,
        content_type: str | None,
        content: bytes,
    ) -> list[IngestedDocument]:
        """Ingest a single uploaded file (an invoice document or an ``.eml``)."""
        if filename.lower().endswith(".eml") or content_type == "message/rfc822":
            email = parse_eml(content, email_id=f"upload-{_short_hash(content)}")
            return self._ingest_email(email)

        email = FetchedEmail(email_id=f"upload-{_short_hash(content)}")
        return self._ingest_attachment(email, filename, content_type, content)

    # ------------------------------------------------------------------ internals
    def _ingest_email(self, email: FetchedEmail) -> list[IngestedDocument]:
        documents: list[IngestedDocument] = []
        for attachment in email.attachments:
            documents.extend(
                self._ingest_attachment(
                    email, attachment.filename, attachment.content_type, attachment.content
                )
            )
        return documents

    def _ingest_attachment(
        self,
        email: FetchedEmail,
        filename: str,
        content_type: str | None,
        content: bytes,
    ) -> list[IngestedDocument]:
        document_type = classify_document(content_type, filename)
        if document_type is None:
            log.info("ingest.skip", filename=filename, content_type=content_type)
            return []

        storage_path = self._persist(email.email_id, filename, content)
        sha = hashlib.sha256(content).hexdigest()
        document = IngestedDocument(
            document_id=f"{email.email_id}:{filename}",
            email_id=email.email_id,
            sender=email.sender,
            subject=email.subject,
            attachment_filename=filename,
            content_type=(content_type or "application/octet-stream"),
            document_type=document_type,
            storage_path=str(storage_path),
            size_bytes=len(content),
            content_sha256=sha,
        )
        log.info("ingest.document", document_id=document.document_id, type=document_type.value)
        return [document]

    def _persist(self, email_id: str, filename: str, content: bytes) -> Path:
        safe_email = email_id.replace("/", "_")
        target_dir = self._dir / safe_email
        target_dir.mkdir(parents=True, exist_ok=True)
        path = target_dir / filename
        path.write_bytes(content)
        return path


def _short_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()[:12]
