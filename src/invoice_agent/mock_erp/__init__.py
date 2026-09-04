"""Mock ERP service (SAP/Oracle/NetSuite stand-in).

Task 0 provides only the health endpoint; the PO / Goods-Receipt read endpoints
and the journal-posting endpoint are implemented in Task 2. Designed so a real
ERP sandbox can be swapped in behind the same interface later.
"""
