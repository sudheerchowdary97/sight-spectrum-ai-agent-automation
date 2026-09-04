"""Retrieval-Augmented Generation layer (Task 5).

Indexes Purchase Orders into PostgreSQL + PGVector (via LlamaIndex, with Ollama
embeddings) and retrieves the most semantically similar candidate POs for an
invoice. This is what lets matching (Task 6) find the right PO even when the
vendor name is fuzzy or the PO number is missing/garbled.

The index is behind a small :class:`~invoice_agent.rag.base.POIndex` protocol so
the retrieval logic is unit-testable with a dependency-free in-memory index; the
real LlamaIndex + PGVector implementation runs in Docker.
"""
