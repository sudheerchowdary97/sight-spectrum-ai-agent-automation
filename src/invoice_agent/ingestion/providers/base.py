"""Email-provider abstraction.

A provider knows how to fetch raw emails (with attachments as bytes) from some
source. The ingestion service is provider-agnostic; swapping folder-replay for
Microsoft Graph or Gmail is a one-line change in :func:`build_provider`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass
class FetchedAttachment:
    """A raw attachment pulled from an email."""

    filename: str
    content_type: str
    content: bytes


@dataclass
class FetchedEmail:
    """A raw email with its attachments."""

    email_id: str
    sender: str = ""
    subject: str = ""
    attachments: list[FetchedAttachment] = field(default_factory=list)


@runtime_checkable
class EmailProvider(Protocol):
    """Fetch emails from a mailbox/source."""

    def fetch(self, limit: int | None = None) -> list[FetchedEmail]:
        """Return up to ``limit`` emails (all if ``limit`` is ``None``)."""
        ...
