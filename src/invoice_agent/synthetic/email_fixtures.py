"""Build ``.eml`` email fixtures for the folder-replay ingestion mode (Task 3).

Uses only the Python standard library so it has no third-party dependency.
"""

from __future__ import annotations

import mimetypes
from email.message import EmailMessage
from pathlib import Path

MAILBOX = "ap@ourcompany.example"


def build_email(
    *,
    email_id: str,
    sender_name: str,
    sender_email: str,
    subject: str,
    body: str,
    attachments: list[Path],
    out_dir: Path,
) -> Path:
    """Create an ``.eml`` with the given attachments and write it to ``out_dir``.

    Returns the path to the written ``.eml`` file.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    msg = EmailMessage()
    msg["Message-ID"] = f"<{email_id}@synthetic.local>"
    msg["From"] = f"{sender_name} <{sender_email}>"
    msg["To"] = MAILBOX
    msg["Subject"] = subject
    msg.set_content(body)

    for attachment in attachments:
        ctype, _ = mimetypes.guess_type(attachment.name)
        maintype, subtype = ctype.split("/", 1) if ctype else ("application", "octet-stream")
        msg.add_attachment(
            attachment.read_bytes(),
            maintype=maintype,
            subtype=subtype,
            filename=attachment.name,
        )

    path = out_dir / f"{email_id}.eml"
    path.write_bytes(bytes(msg))
    return path
