"""Duplicate-invoice detection via content hash (Task 4 dedup_hash)."""

from __future__ import annotations


class DedupStore:
    """Remembers which invoice content hashes have been seen.

    In-memory for the prototype; a persistent store would back this in production.
    """

    def __init__(self) -> None:
        self._seen: set[str] = set()

    def seen(self, dedup_hash: str | None) -> bool:
        return bool(dedup_hash) and dedup_hash in self._seen

    def add(self, dedup_hash: str | None) -> None:
        if dedup_hash:
            self._seen.add(dedup_hash)
