"""Gmail API email provider (interface stub).

Mirrors a real implementation: authenticate with OAuth credentials, list
messages with attachments, map to :class:`FetchedEmail`. Live calls are not
enabled in this prototype; use ``EMAIL_PROVIDER=folder`` to run.
"""

from __future__ import annotations

from invoice_agent.config import Settings
from invoice_agent.ingestion.providers.base import FetchedEmail


class GmailProvider:
    """Fetch invoice emails from a Gmail mailbox via the Gmail API."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def fetch(self, limit: int | None = None) -> list[FetchedEmail]:
        raise NotImplementedError(
            "GmailProvider is a stub in this prototype. Set EMAIL_PROVIDER=folder "
            "for local runs, or implement Gmail auth using GMAIL_CREDENTIALS_PATH / "
            "GMAIL_TOKEN_PATH."
        )
