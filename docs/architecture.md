# Architecture

> Living document. Diagrams and detail are expanded as tasks land; Task 15
> produces the final architecture diagram and slide deck.

## System context

```
                         ┌──────────────────────────────────────────────┐
   Vendor emails  ─────▶ │  Agent API (FastAPI, :8000)                    │
   (PDF/scan/HTML)       │  ingest → extract → retrieve → match → post    │
                         │  orchestrated by LangGraph, reasoned by Ollama │
                         └───┬───────────┬───────────┬───────────┬────────┘
                             │           │           │           │
                     Docling │   PGVector│    Ollama │   Mock ERP │
                  (extract)  │   +Llama- │   (LLM +  │   (:8001)  │
                             │   Index   │   embed)  │  PO/GR/AP  │
                             ▼           ▼           ▼           ▼
                        parsed doc   retrieval    decisions   journal post
                             └───────────┴─── Arize Phoenix traces ───┘
                                         (all steps → audit trail in Postgres)
```

## Services (docker-compose)

| Service    | Image / build              | Port  | Role                                  |
|------------|----------------------------|-------|---------------------------------------|
| `api`      | `docker/api.Dockerfile`    | 8000  | Agent API + orchestration             |
| `mock-erp` | `docker/mock_erp.Dockerfile` | 8001 | PO/GR reads, journal posting          |
| `postgres` | `pgvector/pgvector:pg16`   | 5432  | Vector store + ERP/audit persistence  |
| `ollama`   | `ollama/ollama`            | 11434 | LLM + embeddings                      |
| `phoenix`  | `arizephoenix/phoenix`     | 6006  | Tracing / observability               |

## Runtime notes

- **Canonical runtime:** Python 3.12 (in Docker). The mandatory ML stack does not
  yet support Python 3.14, so container builds are the source of truth.
- **Schema-first:** `invoice_agent.schemas` is the shared contract used by every
  stage (extraction, matching, posting, audit).
- **Provenance:** every `AuditRecord` carries a `correlation_id` and
  `source_email_id`, satisfying the end-to-end auditability requirement.
```
