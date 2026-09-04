"""Synthetic data generation (Task 1).

Produces a fully self-consistent, seeded dataset for the pipeline:

* ERP master records — vendors, customers, Purchase Orders, Goods Receipts,
  open AR items (``master`` module).
* Vendor invoices derived from those POs across a controlled scenario mix,
  each auto-labelled with its expected match outcome (``scenarios`` module).
* Rendered documents — PDF / scanned-PDF / HTML / image (``render`` module).
* ``.eml`` email fixtures for the folder-replay ingestion mode (``email_fixtures``).
* A ``ground_truth.json`` that drives evaluation (``generate`` module).

Everything is deterministic given a seed, so evaluation runs are reproducible.
"""
