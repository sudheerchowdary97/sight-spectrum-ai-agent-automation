"""Email ingestion pipeline (Task 3).

Provider-abstracted ingestion: pull invoice emails from a source (folder replay
of ``.eml`` fixtures, or Microsoft Graph / Gmail), extract and classify their
attachments, and persist them for downstream extraction (Task 4).
"""
