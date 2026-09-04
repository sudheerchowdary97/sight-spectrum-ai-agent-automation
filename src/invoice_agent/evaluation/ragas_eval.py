"""Best-effort RAGAs evaluation of retrieval quality (Task 13/14).

Optional and fully guarded: if RAGAs / langchain-ollama are unavailable or the
Ollama judge errors, it returns ``{"available": False, ...}`` and never breaks
the deterministic evaluation. Uses the local Ollama model as the judge LLM.
"""

from __future__ import annotations

from typing import Any

from invoice_agent.config import Settings
from invoice_agent.logging_config import get_logger

log = get_logger("evaluation.ragas")


def evaluate_with_ragas(samples: list[dict[str, Any]], settings: Settings) -> dict[str, Any]:
    """Compute RAGAs context precision/recall over retrieval samples.

    Each sample: ``{query: str, contexts: list[str], reference: str}``.
    """
    if not samples:
        return {"available": False, "reason": "no samples with a known reference PO"}
    try:
        from datasets import Dataset
        from langchain_ollama import ChatOllama, OllamaEmbeddings
        from ragas import evaluate
        from ragas.metrics import context_precision, context_recall
    except Exception as exc:  # pragma: no cover - optional dependency
        return {"available": False, "reason": f"ragas/langchain-ollama not installed: {exc}"}

    try:
        dataset = Dataset.from_dict(
            {
                "question": [s["query"] for s in samples],
                "contexts": [s["contexts"] for s in samples],
                "reference": [s["reference"] for s in samples],
            }
        )
        judge = ChatOllama(
            model=settings.ollama_llm_model, base_url=settings.ollama_base_url, temperature=0
        )
        embeddings = OllamaEmbeddings(
            model=settings.ollama_embedding_model, base_url=settings.ollama_base_url
        )
        result = evaluate(
            dataset,
            metrics=[context_precision, context_recall],
            llm=judge,
            embeddings=embeddings,
        )
        scores = {k: round(float(v), 4) for k, v in dict(result).items()}
        log.info("ragas.done", samples=len(samples), scores=scores)
        return {"available": True, "samples": len(samples), "scores": scores}
    except Exception as exc:  # pragma: no cover - judge/runtime issues
        log.warning("ragas.failed", error=str(exc))
        return {"available": False, "reason": str(exc)}
