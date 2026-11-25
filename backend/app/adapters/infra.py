"""Adaptateurs d'infrastructure simples pour le POC (remplaçables par S3 / Redis plus tard)."""
from __future__ import annotations

import threading
from datetime import date
from pathlib import Path


class LocalFileStorage:
    def __init__(self, root: str):
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        p = (self._root / key).resolve()
        if self._root.resolve() not in p.parents:
            raise ValueError("clé invalide")
        return p

    def put(self, key: str, data: bytes) -> None:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)

    def get(self, key: str) -> bytes | None:
        try:
            p = self._path(key)
        except ValueError:
            return None
        return p.read_bytes() if p.is_file() else None


class InMemoryDailyLimiter:
    """Quota par jour et par sujet (IP pour un invité, id pour un inscrit)."""

    def __init__(self):
        self._lock = threading.Lock()
        self._day = date.today()
        self._counts: dict[str, int] = {}

    def _roll(self) -> None:
        if date.today() != self._day:
            self._day, self._counts = date.today(), {}

    def check_and_consume(self, subject: str, limit: int) -> bool:
        with self._lock:
            self._roll()
            used = self._counts.get(subject, 0)
            if used >= limit:
                return False
            self._counts[subject] = used + 1
            return True

    def remaining(self, subject: str, limit: int) -> int:
        with self._lock:
            self._roll()
            return max(0, limit - self._counts.get(subject, 0))
