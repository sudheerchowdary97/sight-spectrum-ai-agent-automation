"""Extraction service: orchestrate parse → LLM extract → normalise → validate."""

from __future__ import annotations

import re

from invoice_agent.config import Settings
from invoice_agent.extraction.base import DocumentParser, LLMClient
from invoice_agent.extraction.models import ExtractionResult
from invoice_agent.extraction.normalizer import to_extraction_result
from invoice_agent.ingestion.models import IngestedDocument
from invoice_agent.logging_config import get_logger

log = get_logger("extraction")

# Deterministic backstop for the PO number (LLMs sometimes miss this field even
# when it is clearly present as a "PO-#####" token in the text).
_PO_PATTERN = re.compile(r"\bPO-\d{3,}\b")


class ExtractionService:
    """Turn an ingested document into a validated, scored invoice."""

    def __init__(self, parser: DocumentParser, llm: LLMClient) -> None:
        self._parser = parser
        self._llm = llm

    def extract(self, ingested: IngestedDocument) -> ExtractionResult:
        text = self._parser.to_text(ingested.storage_path, ingested.document_type)
        extracted = self._llm.extract_invoice(text)

        # Backstop: recover a PO number the LLM dropped but that is in the text.
        if not extracted.po_number:
            match = _PO_PATTERN.search(text)
            if match:
                extracted = extracted.model_copy(update={"po_number": match.group(0)})
                log.info("extract.po_backstop", document_id=ingested.document_id, po=match.group(0))

        result = to_extraction_result(extracted, ingested)
        log.info(
            "extract.done",
            document_id=ingested.document_id,
            invoice_number=result.invoice.invoice_number,
            confidence=result.confidence,
            warnings=len(result.warnings),
        )
        return result


def build_extraction_service(settings: Settings) -> ExtractionService:
    """Build the real Docling + Ollama extraction service from settings."""
    from invoice_agent.extraction.docling_parser import DoclingParser
    from invoice_agent.extraction.llm import OllamaLLMClient

    return ExtractionService(
        parser=DoclingParser(),
        llm=OllamaLLMClient(settings.ollama_base_url, settings.ollama_llm_model),
    )
