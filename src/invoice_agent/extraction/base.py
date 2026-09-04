"""Extraction interfaces (protocols).

Kept dependency-free so the orchestration logic can be tested with fakes; the
real Docling/Ollama implementations import their heavy libraries lazily.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from invoice_agent.extraction.models import ExtractedInvoice
from invoice_agent.schemas import DocumentType


@runtime_checkable
class DocumentParser(Protocol):
    """Parse a stored document into plain text / markdown."""

    def to_text(self, storage_path: str, document_type: DocumentType) -> str: ...


@runtime_checkable
class LLMClient(Protocol):
    """Extract structured invoice fields from parsed document text."""

    def extract_invoice(self, text: str) -> ExtractedInvoice: ...
