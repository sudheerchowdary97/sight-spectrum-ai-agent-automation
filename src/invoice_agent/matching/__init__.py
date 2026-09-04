"""2-way / 3-way invoice matching (Task 6).

Given an extracted invoice, resolve its Purchase Order (via the PO number or RAG
retrieval), pull the Goods Receipt from the ERP, and run a line-level match with
configurable tolerances — classifying the outcome as matched / price-variance /
qty-variance / partial / missing-PO / duplicate.
"""
