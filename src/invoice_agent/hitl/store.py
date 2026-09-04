"""In-memory store for queued exceptions."""

from __future__ import annotations

import itertools

from invoice_agent.hitl.models import ExceptionItem, ExceptionStatus
from invoice_agent.schemas import Invoice, MatchResult


class ExceptionStore:
    """Holds queued exceptions (in-memory for the prototype)."""

    def __init__(self) -> None:
        self._items: dict[str, ExceptionItem] = {}
        self._seq = itertools.count(1)

    def add(
        self, invoice: Invoice, match: MatchResult, correlation_id: str | None = None
    ) -> ExceptionItem:
        exception_id = f"EXC-{next(self._seq):06d}"
        item = ExceptionItem(
            exception_id=exception_id,
            correlation_id=correlation_id,
            invoice=invoice,
            match=match,
            reason=match.notes or match.status.value,
        )
        self._items[exception_id] = item
        return item

    def get(self, exception_id: str) -> ExceptionItem | None:
        return self._items.get(exception_id)

    def list(self, status: ExceptionStatus | None = None) -> list[ExceptionItem]:
        items = list(self._items.values())
        if status is not None:
            items = [i for i in items if i.status is status]
        return items

    def save(self, item: ExceptionItem) -> None:
        self._items[item.exception_id] = item
