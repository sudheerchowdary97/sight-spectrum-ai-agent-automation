"""Folder-replay email provider.

Parses ``.eml`` files from a directory (the Task 1 fixtures). This lets the whole
pipeline run and be demoed without any live mailbox OAuth.
"""

from __future__ import annotations

from email.parser import BytesParser
from email.policy import default
from pathlib import Path

from invoice_agent.ingestion.providers.base import FetchedAttachment, FetchedEmail


def parse_eml(content: bytes, *, email_id: str) -> FetchedEmail:
    """Parse raw ``.eml`` bytes into a :class:`FetchedEmail`."""
    msg = BytesParser(policy=default).parsebytes(content)
    attachments: list[FetchedAttachment] = []
    for part in msg.iter_attachments():
        filename = part.get_filename()
        if not filename:
            continue
        payload = part.get_payload(decode=True) or b""
        attachments.append(
            FetchedAttachment(
                filename=filename,
                content_type=part.get_content_type(),
                content=payload,
            )
        )
    return FetchedEmail(
        email_id=email_id,
        sender=str(msg["From"] or ""),
        subject=str(msg["Subject"] or ""),
        attachments=attachments,
    )


class FolderProvider:
    """Read emails from a directory of ``.eml`` files (sorted, deterministic)."""

    def __init__(self, inbox_dir: str | Path) -> None:
        self._dir = Path(inbox_dir)

    def fetch(self, limit: int | None = None) -> list[FetchedEmail]:
        if not self._dir.exists():
            return []
        files = sorted(self._dir.glob("*.eml"))
        if limit is not None:
            files = files[:limit]
        return [parse_eml(f.read_bytes(), email_id=f.stem) for f in files]
