"""PO index implementations.

* :class:`InMemoryPOIndex` — dependency-free lexical index (token overlap). Used
  by unit tests and as a fallback; deterministic, no embeddings.
* :class:`LlamaIndexPOIndex` — the real index: LlamaIndex ``VectorStoreIndex``
  backed by PostgreSQL + PGVector, with Ollama embeddings. Heavy libraries are
  imported lazily so this module stays import-safe.
"""

from __future__ import annotations

import re
from decimal import Decimal

from invoice_agent.config import Settings
from invoice_agent.logging_config import get_logger
from invoice_agent.rag.documents import po_metadata, po_to_text
from invoice_agent.rag.models import RetrievedPO
from invoice_agent.schemas import PurchaseOrder

log = get_logger("rag.index")

_TOKEN = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> set[str]:
    return set(_TOKEN.findall(text.lower()))


class InMemoryPOIndex:
    """Lexical (token-overlap) index — deterministic, no external dependencies."""

    def __init__(self) -> None:
        self._entries: list[tuple[PurchaseOrder, set[str]]] = []

    def index_purchase_orders(self, purchase_orders: list[PurchaseOrder]) -> None:
        self._entries = [(po, _tokens(po_to_text(po))) for po in purchase_orders]
        log.info("rag.index.memory", purchase_orders=len(self._entries))

    def retrieve(self, query: str, top_k: int = 5) -> list[RetrievedPO]:
        q = _tokens(query)
        scored: list[tuple[float, PurchaseOrder]] = []
        for po, toks in self._entries:
            union = q | toks
            score = len(q & toks) / len(union) if union else 0.0
            scored.append((score, po))
        scored.sort(key=lambda s: (s[0], s[1].po_number), reverse=True)
        return [
            RetrievedPO(
                po_number=po.po_number,
                vendor_name=po.vendor_name,
                total_amount=po.total_amount,
                score=round(score, 4),
            )
            for score, po in scored[:top_k]
        ]


class LlamaIndexPOIndex:
    """Real index: LlamaIndex + PGVector + Ollama embeddings."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._index = None  # type: ignore[var-annotated]

    # --- lazily-built LlamaIndex components ---
    def _configure_embeddings(self) -> None:
        from llama_index.core import Settings as LISettings
        from llama_index.embeddings.ollama import OllamaEmbedding

        LISettings.embed_model = OllamaEmbedding(
            model_name=self._settings.ollama_embedding_model,
            base_url=self._settings.ollama_base_url,
        )

    def _vector_store(self):  # type: ignore[no-untyped-def]
        from llama_index.vector_stores.postgres import PGVectorStore

        s = self._settings
        return PGVectorStore.from_params(
            host=s.postgres_host,
            port=str(s.postgres_port),
            database=s.postgres_db,
            user=s.postgres_user,
            password=s.postgres_password,
            table_name=s.pgvector_table,
            embed_dim=s.embed_dim,
        )

    def index_purchase_orders(self, purchase_orders: list[PurchaseOrder]) -> None:
        from llama_index.core import Document, StorageContext, VectorStoreIndex

        self._configure_embeddings()
        documents = [
            Document(text=po_to_text(po), metadata=po_metadata(po), doc_id=po.po_number)
            for po in purchase_orders
        ]
        storage_context = StorageContext.from_defaults(vector_store=self._vector_store())
        self._index = VectorStoreIndex.from_documents(documents, storage_context=storage_context)
        log.info("rag.index.pgvector", purchase_orders=len(documents))

    def retrieve(self, query: str, top_k: int = 5) -> list[RetrievedPO]:
        from llama_index.core import VectorStoreIndex

        if self._index is None:
            # Connect to the existing PGVector table (e.g. indexed in a prior run).
            self._configure_embeddings()
            self._index = VectorStoreIndex.from_vector_store(self._vector_store())

        nodes = self._index.as_retriever(similarity_top_k=top_k).retrieve(query)
        results: list[RetrievedPO] = []
        for node in nodes:
            meta = node.metadata or {}
            total = meta.get("total_amount")
            results.append(
                RetrievedPO(
                    po_number=meta.get("po_number", ""),
                    vendor_name=meta.get("vendor_name", ""),
                    total_amount=Decimal(total) if total is not None else None,
                    score=float(node.score or 0.0),
                )
            )
        return results
