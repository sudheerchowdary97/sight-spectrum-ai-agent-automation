"""Tests for the email ingestion pipeline (Task 3)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from invoice_agent.api.main import create_app
from invoice_agent.ingestion.providers.folder import FolderProvider
from invoice_agent.ingestion.service import IngestionService, classify_document
from invoice_agent.schemas import DocumentType
from invoice_agent.synthetic.email_fixtures import build_email


def _make_inbox(tmp_path: Path) -> Path:
    """Create an inbox with two invoice emails (a PDF and an HTML attachment)."""
    docs = tmp_path / "docs"
    docs.mkdir()
    pdf = docs / "INV-1.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake pdf bytes")
    html = docs / "INV-2.html"
    html.write_text("<html><body>Invoice 2</body></html>", encoding="utf-8")

    inbox = tmp_path / "inbox"
    build_email(
        email_id="email-INV-1",
        sender_name="Acme Corp",
        sender_email="ap@acme.example",
        subject="Invoice INV-1",
        body="See attached.",
        attachments=[pdf],
        out_dir=inbox,
    )
    build_email(
        email_id="email-INV-2",
        sender_name="Beta LLC",
        sender_email="ap@beta.example",
        subject="Invoice INV-2",
        body="See attached.",
        attachments=[html],
        out_dir=inbox,
    )
    return inbox


def test_classify_document() -> None:
    assert classify_document("application/pdf", "x.pdf") is DocumentType.PDF
    assert classify_document("text/html; charset=utf-8", "x.html") is DocumentType.HTML
    assert classify_document(None, "scan.PNG") is DocumentType.IMAGE
    assert classify_document(None, "notes.txt") is None


def test_folder_provider_and_dedup(tmp_path: Path) -> None:
    inbox = _make_inbox(tmp_path)
    service = IngestionService(FolderProvider(inbox), ingested_dir=tmp_path / "ingested")

    docs = service.ingest_from_provider()
    assert len(docs) == 2
    types = {d.document_type for d in docs}
    assert types == {DocumentType.PDF, DocumentType.HTML}
    for d in docs:
        assert Path(d.storage_path).exists()
        assert d.content_sha256 and d.size_bytes > 0

    # Replaying the same inbox ingests nothing new (idempotency).
    assert service.ingest_from_provider() == []


@pytest.fixture
def upload_client(tmp_path: Path) -> TestClient:
    service = IngestionService(FolderProvider(tmp_path / "empty"), ingested_dir=tmp_path / "ing")
    return TestClient(create_app(ingestion_service=service))


def test_ingest_endpoint_upload(upload_client: TestClient) -> None:
    resp = upload_client.post(
        "/api/v1/ingest-invoice",
        files={"file": ("invoice.pdf", b"%PDF-1.4 fake", "application/pdf")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ingested"] == 1
    assert body["documents"][0]["document_type"] == "pdf"


def test_ingest_endpoint_poll(tmp_path: Path) -> None:
    inbox = _make_inbox(tmp_path)
    service = IngestionService(FolderProvider(inbox), ingested_dir=tmp_path / "ing")
    client = TestClient(create_app(ingestion_service=service))

    resp = client.post("/api/v1/ingest-invoice")
    assert resp.status_code == 200
    assert resp.json()["ingested"] == 2
