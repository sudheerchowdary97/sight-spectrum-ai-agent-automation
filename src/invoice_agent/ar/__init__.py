"""Accounts-Receivable mirror track (Task 10).

Mirrors the AP flow for inbound customer remittances: match a remittance against
an open AR item (by referenced invoice number) and apply cash — full, partial,
or overpaid — via the ERP, writing a ``cash_applied`` audit record.
"""
