"""Document processing & field extraction (Task 4).

Pipeline: an ingested document → Docling parses it to text → an Ollama LLM
extracts structured fields → the fields are normalised and validated into the
canonical :class:`~invoice_agent.schemas.invoice.Invoice`, with a duplicate-
detection hash and a reconciliation-based confidence score.

Parser and LLM are behind small protocols (:mod:`.base`) so the orchestration
logic is unit-testable with fakes; the real Docling + Ollama implementations run
in Docker.
"""
