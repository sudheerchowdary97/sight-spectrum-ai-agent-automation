# Agentic Invoice-to-Payment Automation

An **Agentic AI prototype** that reads vendor invoices from a shared mailbox,
extracts the data, performs a **2-way / 3-way match** against Purchase Orders and
Goods Receipts in the ERP, and **posts a Payment Journal** for approved invoices —
with a full audit trail and human oversight for exceptions. The same pattern is
mirrored for inbound **AR remittances**.

> Status: **Tasks 0–11 complete** — the full pipeline plus all five mandatory
> API endpoints (ingest, match, post-journal, audit-log, health), human-in-the-loop
> review, and the AR mirror. Remaining: observability (Phoenix), evaluation
> (RAGAs + metrics), packaging, and the deck. See
> [docs/architecture.md](docs/architecture.md).

## Technology stack

| Component            | Technology                             |
|----------------------|----------------------------------------|
| Email ingestion      | Microsoft Graph API / Gmail API        |
| Document processing  | Docling                                |
| Vector database      | PostgreSQL + PGVector                  |
| RAG framework        | LlamaIndex                             |
| Agent orchestration  | LangGraph / CrewAI                     |
| LLM provider         | Ollama                                 |
| ERP integration      | Mock ERP API (SAP/Oracle/NetSuite-shaped) |
| Observability        | Arize Phoenix                          |
| Evaluation           | RAGAs + extraction-accuracy metrics    |
| Deployment           | Docker & Docker Compose                |

## Quick start

```bash
# 1. Configure
cp .env.example .env            # adjust as needed

# 2. Bring up the full stack (Postgres, Ollama, Phoenix, mock-erp, api)
make up

# 3. Pull the LLM + embedding models into the Ollama container
make ollama-pull

# 4. Verify
curl http://localhost:8000/api/v1/health      # Agent API
curl http://localhost:8001/api/v1/health      # Mock ERP
open http://localhost:8000/docs               # Swagger / OpenAPI
open http://localhost:6006                     # Phoenix UI
```

### Local development (host Python)

The mandatory ML libraries target **Python 3.11–3.12**; use that for a host venv
(Docker uses 3.12 regardless).

```bash
python3.12 -m venv .venv && source .venv/bin/activate
make install        # editable install + dev/data extras
make lint test      # ruff + pytest
```

> **After changing server code, restart the API:** `docker compose restart api`.
> On colima, file-change events don't cross the VM mount, so uvicorn `--reload`
> may not fire. (CLI scripts run fresh each time and need no restart.)

## API endpoints

| Method | Path                            | Task | Description                         |
|--------|---------------------------------|------|-------------------------------------|
| GET    | `/api/v1/health`                | 0    | Liveness probe                      |
| POST   | `/api/v1/ingest-invoice`        | 3    | Ingest & parse an invoice email     |
| POST   | `/api/v1/match-po`              | 6    | 2-way / 3-way match against PO/GR   |
| POST   | `/api/v1/post-payment-journal`  | 9    | Post an AP journal entry            |
| GET    | `/api/v1/audit-log`             | 11   | Retrieve the decision audit trail   |

### Human-in-the-loop endpoints (Task 8)

Matches that need oversight (variance / missing-PO / duplicate) are queued as
exceptions. A human lists them and approves (→ posts the Payment Journal) or
rejects — every decision is audited.

| Method | Path                                          | Description                     |
|--------|-----------------------------------------------|---------------------------------|
| GET    | `/api/v1/exceptions[?status=pending]`         | List queued exceptions          |
| GET    | `/api/v1/exceptions/{id}`                      | Fetch one exception             |
| POST   | `/api/v1/exceptions/{id}/approve`             | Approve → post the journal      |
| POST   | `/api/v1/exceptions/{id}/reject`              | Reject → close the invoice      |

### Mock ERP endpoints (`:8001`, Task 2)

Seeded from the Task 1 master data; a real SAP/Oracle/NetSuite connector can
replace it behind the same interface.

| Method | Path                                   | Description                        |
|--------|----------------------------------------|------------------------------------|
| GET    | `/api/v1/purchase-orders/{po_number}`  | Fetch a Purchase Order             |
| GET    | `/api/v1/goods-receipts?po_number=`    | List Goods Receipts for a PO       |
| GET    | `/api/v1/ar-items[?status=open]`       | List open AR items                 |
| POST   | `/api/v1/payment-journals`             | Post AP journal (409 on duplicate) |
| POST   | `/api/v1/cash-applications`            | Apply a remittance to an AR item   |

## Project layout

```
sight-spectrum/
├── docker-compose.yml          # full local stack
├── docker/                     # api & mock-erp Dockerfiles
├── config/tolerances.yaml      # matching tolerance thresholds
├── src/invoice_agent/
│   ├── config.py               # pydantic-settings configuration
│   ├── logging_config.py       # structlog setup
│   ├── schemas/                # shared domain contract (Pydantic)
│   ├── api/                    # Agent API (FastAPI)
│   └── mock_erp/               # mock ERP service (FastAPI)
├── scripts/                    # synthetic data generation (Task 1)
├── tests/                      # pytest suite
└── docs/                       # architecture & design docs
```

## Data

No real invoices are used. A **seeded, reproducible** generator produces
synthetic Purchase Orders, Goods Receipts, AR items, and matching invoices
rendered as PDF / scanned-PDF / HTML / image, plus a `ground_truth.json` that
drives evaluation (extraction accuracy, match rate, STP rate).

```bash
make data                                             # defaults: seed 42, 60 POs
python scripts/generate_synthetic_data.py --seed 42 --num-pos 60 --out data
```

Outputs (under `data/`, git-ignored):

```
master/            vendors, customers, purchase_orders, goods_receipts,
                   ar_items, remittances  (JSON — seed for mock ERP + PGVector)
generated/invoices/  rendered invoice documents (pdf/scanned-pdf/html/png)
inbox/             .eml fixtures (invoices + remittances) for folder-replay ingestion
ground_truth.json  labelled expectation per invoice (scenario, expected match, fields)
summary.json       dataset statistics (counts, scenario mix, expected STP rate)
```

Scenario mix (auto-labelled): clean match, price variance, qty variance,
partial, missing-PO, duplicate — plus fuzzy vendor-name variants to exercise
semantic retrieval.

> **After regenerating data, restart the ERP so it re-seeds:**
> `docker compose restart mock-erp` (it loads master data at start-up).

## Running extraction (Docling + Ollama)

Field extraction (Task 4) runs **Docling** (document → text, with OCR for scans)
and a local **Ollama** LLM (text → structured invoice JSON). These require
**Python ≤3.12** and a running Ollama, so run them via Docker:

```bash
# 1) Start the stack and pull the model
make up
make ollama-pull                       # llama3.1:8b + nomic-embed-text

# 2) Generate data (if not already done)
docker compose exec api python scripts/generate_synthetic_data.py --out data

# 3) Extract a single invoice end-to-end (ingest → Docling → Ollama → Invoice)
docker compose exec api python scripts/extract_invoice.py \
    data/generated/invoices/INV-00002.pdf
```

The CLI prints the validated `Invoice` JSON with a confidence score (based on
whether line items reconcile to the total) and any warnings. Swap the file for a
`.png` (scanned) or `.html` to exercise the other document types.

## RAG retrieval (PGVector + LlamaIndex + Ollama)

Task 5 indexes Purchase Orders into PostgreSQL + PGVector (LlamaIndex, Ollama
embeddings) and retrieves candidate POs for an invoice — robust to fuzzy vendor
names and missing PO numbers.

```bash
# Index master POs into PGVector, then test retrieval with fuzzed vendor names
docker compose exec api python scripts/rag_index_retrieve.py --sample 10
```

It reports `hit@1` — how often the correct PO is retrieved first despite a
perturbed vendor name — demonstrating the semantic-retrieval value that feeds
the matching engine (Task 6).

## Running the full agent (LangGraph)

Task 7 wires everything into one agentic state machine — `ingest → extract →
match → (post | escalate) → audit`:

```bash
docker compose exec api python scripts/run_agent.py --limit 5
```

For each invoice it prints the match status, the decision (`posted` /
`escalated` / `duplicate`), the posted journal id, and the audit trail. Clean
matches auto-post a Payment Journal to the ERP; exceptions route to escalation.

## License

[MIT](LICENSE)
