"""Provider registry / factory."""

from __future__ import annotations

from invoice_agent.config import Settings
from invoice_agent.ingestion.providers.base import (
    EmailProvider,
    FetchedAttachment,
    FetchedEmail,
)
from invoice_agent.ingestion.providers.folder import FolderProvider, parse_eml
from invoice_agent.ingestion.providers.gmail import GmailProvider
from invoice_agent.ingestion.providers.graph import GraphProvider

__all__ = [
    "EmailProvider",
    "FetchedAttachment",
    "FetchedEmail",
    "FolderProvider",
    "GmailProvider",
    "GraphProvider",
    "build_provider",
    "parse_eml",
]


def build_provider(settings: Settings) -> EmailProvider:
    """Return the configured email provider."""
    provider = settings.email_provider.lower()
    if provider == "folder":
        return FolderProvider(settings.email_replay_dir)
    if provider == "graph":
        return GraphProvider(settings)
    if provider == "gmail":
        return GmailProvider(settings)
    raise ValueError(f"Unknown EMAIL_PROVIDER: {settings.email_provider!r}")
