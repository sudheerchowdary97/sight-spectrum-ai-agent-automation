"""Docling document parser.

Converts PDF / scanned-PDF / image / HTML into markdown text for the LLM.

OCR is only enabled where it is needed — scanned PDFs and images. Digital PDFs
(which carry a real text layer) and HTML are parsed without OCR, which is faster
and avoids loading the OCR engine entirely. Docling is imported lazily (heavy
dependency, Python ≤3.12) so this module is import-safe anywhere.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from invoice_agent.logging_config import get_logger
from invoice_agent.schemas import DocumentType

if TYPE_CHECKING:  # pragma: no cover
    from docling.document_converter import DocumentConverter

log = get_logger("extraction.docling")

# PDF document types that are image-only and therefore require OCR.
_OCR_PDF_TYPES = {DocumentType.SCANNED_PDF}


class DoclingParser:
    """Parse documents to markdown using Docling, with OCR only when required."""

    def __init__(self) -> None:
        # Two PDF converters cached by whether OCR is enabled.
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

    def to_text(self, storage_path: str, document_type: DocumentType) -> str:
        """Return the document contents as markdown text."""
        # Images always go through Docling's image pipeline (OCR). For PDFs we
        # enable OCR only for scanned (image-only) PDFs. HTML needs no OCR.
        do_ocr = document_type in _OCR_PDF_TYPES
        result = self._get_converter(do_ocr).convert(storage_path)
        text = result.document.export_to_markdown()
        log.info(
            "docling.parsed",
            path=storage_path,
            type=document_type.value,
            ocr=do_ocr,
            chars=len(text),
        )
        return text
