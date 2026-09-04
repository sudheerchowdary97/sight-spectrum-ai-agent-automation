# Evaluation Report

- Dataset: `data/ground_truth.json`
- Invoices evaluated: **15**

## Extraction accuracy
- Overall field accuracy: **96.0%**
  - invoice_number: 93.3%
  - line_count: 100.0%
  - po_number: 86.7%
  - total_amount: 100.0%
  - vendor_name: 100.0%

## Matching
- Classification accuracy vs ground truth: **80.0%**
- Match rate: **86.7%**
- STP rate (auto-posted): **86.7%**

## Retrieval (RAG candidate PO)
- Evaluated: 15
- hit@1: **100.0%**
- MRR: **1.0**