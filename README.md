# Agentic Invoice-to-Payment Automation

An **Agentic AI prototype** that reads vendor invoices from a shared mailbox,
extracts the data, performs a **2-way / 3-way match** against Purchase Orders and
Goods Receipts in the ERP, and **posts a Payment Journal** for approved invoices —
with a full audit trail and human oversight for exceptions. The same pattern is
mirrored for inbound **AR remittances**.

> Status: **Task 0 — foundation & scaffolding** complete. Subsequent tasks build
> the pipeline on top of this contract. See [docs/architecture.md](docs/architecture.md).

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

## API endpoints

| Method | Path                            | Task | Description                         |
|--------|---------------------------------|------|-------------------------------------|
| GET    | `/api/v1/health`                | 0    | Liveness probe                      |
| POST   | `/api/v1/ingest-invoice`        | 3    | Ingest & parse an invoice email     |
| POST   | `/api/v1/match-po`              | 6    | 2-way / 3-way match against PO/GR   |
| POST   | `/api/v1/post-payment-journal`  | 9    | Post an AP journal entry            |
| GET    | `/api/v1/audit-log`             | 11   | Retrieve the decision audit trail   |

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

## License

[MIT](LICENSE)
