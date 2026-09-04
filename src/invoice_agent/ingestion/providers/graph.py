"""Microsoft Graph email provider (interface stub).

The structure mirrors a real implementation: authenticate with client
credentials, list messages in the target mailbox with attachments, and map them
to :class:`FetchedEmail`. Live calls are intentionally not enabled in this
prototype (no OAuth in the sandbox); use ``EMAIL_PROVIDER=folder`` to run.
"""

from __future__ import annotations

from invoice_agent.config import Settings
from invoice_agent.ingestion.providers.base import FetchedEmail


class GraphProvider:
    """Fetch invoice emails from a shared mailbox via Microsoft Graph."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def fetch(self, limit: int | None = None) -> list[FetchedEmail]:
        raise NotImplementedError(
            "GraphProvider is a stub in this prototype. Set EMAIL_PROVIDER=folder "
            "for local runs, or implement Graph auth using GRAPH_TENANT_ID / "
            "GRAPH_CLIENT_ID / GRAPH_CLIENT_SECRET / GRAPH_MAILBOX."
        )
