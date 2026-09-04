"""Docling document parser.

Converts PDF / scanned-PDF / image / HTML into markdown text for the LLM.
Docling is imported lazily (heavy dependency, Python ≤3.12) so this module can
be imported anywhere; only :meth:`to_text` requires it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from invoice_agent.logging_config import get_logger
from invoice_agent.schemas import DocumentType

if TYPE_CHECKING:  # pragma: no cover
    from docling.document_converter import DocumentConverter

log = get_logger("extraction.docling")


class DoclingParser:
    """Parse documents to markdown using Docling (with OCR for scans/images)."""

    def __init__(self) -> None:
        self._converter: DocumentConverter | None = None

    def _get_converter(self) -> DocumentConverter:
        if self._converter is None:
            from docling.document_converter import DocumentConverter

            self._converter = DocumentConverter()
        return self._converter

    def to_text(self, storage_path: str, document_type: DocumentType) -> str:
        """Return the document contents as markdown text."""
        result = self._get_converter().convert(storage_path)
        text = result.document.export_to_markdown()
        log.info("docling.parsed", path=storage_path, type=document_type.value, chars=len(text))
        return text
