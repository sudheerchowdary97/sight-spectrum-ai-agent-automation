"""Ollama LLM client for invoice field extraction.

Asks a local Ollama model to return JSON conforming to :class:`ExtractedInvoice`
(using Ollama's structured-output ``format`` = JSON schema), then validates it.
The ``ollama`` package is imported lazily so this module is import-safe without it.
"""

from __future__ import annotations

from invoice_agent.extraction.models import ExtractedInvoice
from invoice_agent.logging_config import get_logger

log = get_logger("extraction.ollama")

SYSTEM_PROMPT = (
    "You are an accounts-payable data-extraction engine. Extract invoice fields "
    "from the document text and return ONLY JSON matching the provided schema.\n"
    "Field labels in the text: 'Invoice #:' -> invoice_number; 'PO #:' -> po_number "
    "(set null ONLY if it is absent or 'N/A' — do NOT omit a PO that is present); "
    "'Date:' -> invoice_date; 'Due:' -> due_date; 'Vendor:' -> vendor_name; "
    "'Total:' -> total_amount.\n"
    "The line-item table has columns: #, SKU, Description, Qty, Unit, Amount. Extract "
    "EVERY row; map the SKU column value (e.g. 'SKU-1001') to sku, Qty to quantity, "
    "Unit to unit_price, Amount to amount.\n"
    "Rules: ISO dates (YYYY-MM-DD); amounts as plain numbers without currency symbols "
    "or thousands separators. Do not invent values."
)


class OllamaLLMClient:
    """Extract structured invoice fields via a local Ollama model."""

    def __init__(self, base_url: str, model: str, *, temperature: float = 0.0) -> None:
        self._base_url = base_url
        self._model = model
        self._temperature = temperature
        self._client = None

    def _get_client(self):  # type: ignore[no-untyped-def]
        if self._client is None:
            from ollama import Client

            self._client = Client(host=self._base_url)
        return self._client

    def extract_invoice(self, text: str) -> ExtractedInvoice:
        schema = ExtractedInvoice.model_json_schema()
        response = self._get_client().chat(
            model=self._model,
            format=schema,
            options={"temperature": self._temperature},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Document text:\n\n{text}"},
            ],
        )
        content = response["message"]["content"]
        log.info("ollama.extracted", model=self._model, chars=len(text))
        return ExtractedInvoice.model_validate_json(content)
