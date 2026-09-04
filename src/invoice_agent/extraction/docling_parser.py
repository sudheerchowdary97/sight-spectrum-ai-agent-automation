"""Document parser: text-layer extraction (pypdfium2) + Docling OCR.

Strategy by document type:

* **PDF** — try the born-digital text layer first via ``pypdfium2`` (fast,
  lossless). If the PDF is image-only/scanned (no text layer), fall back to
  Docling with OCR.
* **HTML** — Docling (structured text, no OCR).
* **IMAGE** — Docling image pipeline (OCR).

``pypdfium2`` ships as a Docling dependency; Docling is imported lazily (heavy,
Python ≤3.12) so this module stays import-safe.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from invoice_agent.logging_config import get_logger
from invoice_agent.schemas import DocumentType

if TYPE_CHECKING:  # pragma: no cover
    from docling.document_converter import DocumentConverter

log = get_logger("extraction.docling")

_PDF_TYPES = {DocumentType.PDF, DocumentType.SCANNED_PDF}
# Below this many characters we treat the text layer as absent → OCR.
_MIN_CHARS = 20


class DoclingParser:
    """Parse documents to text, using OCR only for image-only PDFs and images."""

    def __init__(self) -> None:
        # Docling PDF converters cached by whether OCR is enabled.
        self._converters: dict[bool, DocumentConverter] = {}

    # ----------------------------------------------------------------- pypdfium2
    @staticmethod
    def _pdf_text_layer(storage_path: str) -> str:
        """Extract the born-digital text layer with pypdfium2 (empty if none)."""
        import pypdfium2 as pdfium

        doc = pdfium.PdfDocument(storage_path)
        try:
            parts: list[str] = []
            for i in range(len(doc)):
                page = doc[i]
                textpage = page.get_textpage()
                parts.append(textpage.get_text_range())
                textpage.close()
                page.close()
            return "\n".join(parts)
        finally:
            doc.close()

    # -------------------------------------------------------------------- docling
    def _get_converter(self, do_ocr: bool) -> DocumentConverter:
        if do_ocr not in self._converters:
            from docling.datamodel.base_models import InputFormat
            from docling.datamodel.pipeline_options import PdfPipelineOptions
            from docling.document_converter import DocumentConverter, PdfFormatOption

            pdf_options = PdfPipelineOptions()
            pdf_options.do_ocr = do_ocr
            self._converters[do_ocr] = DocumentConverter(
                format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pdf_options)}
            )
        return self._converters[do_ocr]

    def _docling_text(self, storage_path: str, do_ocr: bool) -> str:
        document = self._get_converter(do_ocr).convert(storage_path).document
        text = document.export_to_markdown()
        if len(text.strip()) < _MIN_CHARS and hasattr(document, "export_to_text"):
            alt = document.export_to_text()
            if len(alt.strip()) > len(text.strip()):
                text = alt
        return text

    # ------------------------------------------------------------------------ api
    def to_text(self, storage_path: str, document_type: DocumentType) -> str:
        """Return the document contents as text, using OCR only when needed."""
        if document_type in _PDF_TYPES:
            try:
                text = self._pdf_text_layer(storage_path)
            except Exception as exc:  # pragma: no cover - defensive
                log.info("pdf.text_layer.error", path=storage_path, error=str(exc))
                text = ""
            if len(text.strip()) >= _MIN_CHARS:
                log.info("pdf.text_layer", path=storage_path, chars=len(text))
                return text
            # No text layer → image-only/scanned PDF → OCR via Docling.
            log.info("pdf.ocr_fallback", path=storage_path)
            text = self._docling_text(storage_path, do_ocr=True)
            log.info("docling.parsed", path=storage_path, ocr=True, chars=len(text))
            return text

        # HTML (text) or IMAGE (Docling image pipeline OCRs by default).
        text = self._docling_text(storage_path, do_ocr=False)
        log.info("docling.parsed", path=storage_path, type=document_type.value, chars=len(text))
        return text
