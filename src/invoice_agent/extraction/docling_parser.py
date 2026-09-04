"""Docling document parser.

Converts PDF / scanned-PDF / image / HTML into markdown text for the LLM.

OCR is enabled only where needed (scanned PDFs, images); digital PDFs and HTML
are parsed via their text layer first. If a no-OCR parse yields (near-)empty
text — e.g. a PDF whose text layer Docling can't read — we transparently retry
with OCR. Docling is imported lazily (heavy dependency, Python ≤3.12).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from invoice_agent.logging_config import get_logger
from invoice_agent.schemas import DocumentType

if TYPE_CHECKING:  # pragma: no cover
    from docling.document_converter import DocumentConverter

log = get_logger("extraction.docling")

# PDF document types that are image-only and therefore require OCR up front.
_OCR_PDF_TYPES = {DocumentType.SCANNED_PDF}
# Below this many characters we consider the parse empty and fall back to OCR.
_MIN_CHARS = 20


class DoclingParser:
    """Parse documents to markdown using Docling, with OCR when required."""

    def __init__(self) -> None:
        # PDF converters cached by whether OCR is enabled.
        self._converters: dict[bool, DocumentConverter] = {}

    def _get_converter(self, do_ocr: bool) -> DocumentConverter:
        if do_ocr not in self._converters:
            from docling.datamodel.base_models import InputFormat
            from docling.datamodel.pipeline_options import PdfPipelineOptions
            from docling.document_converter import DocumentConverter, PdfFormatOption

            pdf_options = PdfPipelineOptions()
            pdf_options.do_ocr = do_ocr
            self._converters[do_ocr] = DocumentConverter(
                format_options={
                    InputFormat.PDF: PdfFormatOption(pipeline_options=pdf_options),
                }
            )
        return self._converters[do_ocr]

    def _convert(self, storage_path: str, do_ocr: bool) -> str:
        document = self._get_converter(do_ocr).convert(storage_path).document
        text = document.export_to_markdown()
        # Markdown can come back empty even when text exists; try plain-text export
        # (guarded — the method name varies across Docling versions).
        if len(text.strip()) < _MIN_CHARS and hasattr(document, "export_to_text"):
            alt = document.export_to_text()
            if len(alt.strip()) > len(text.strip()):
                text = alt
        return text

    def to_text(self, storage_path: str, document_type: DocumentType) -> str:
        """Return the document contents as markdown text, using OCR as needed."""
        do_ocr = document_type in _OCR_PDF_TYPES
        text = self._convert(storage_path, do_ocr)

        # Fallback: a digital PDF whose text layer didn't extract → retry with OCR.
        if len(text.strip()) < _MIN_CHARS and not do_ocr:
            log.info("docling.fallback_ocr", path=storage_path, type=document_type.value)
            text = self._convert(storage_path, True)

        log.info(
            "docling.parsed",
            path=storage_path,
            type=document_type.value,
            ocr=do_ocr,
            chars=len(text),
        )
        return text
