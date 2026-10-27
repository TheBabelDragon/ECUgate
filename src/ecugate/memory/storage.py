"""Storage backend interface for structured agent memory."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, List, Optional

from ecugate.memory.models import MemoryRecord, RecordType


class MemoryBackend(ABC):
    @abstractmethod
    def append(self, record: MemoryRecord) -> None:
        ...

    @abstractmethod
    def get(self, record_id: str) -> Optional[MemoryRecord]:
        ...

    @abstractmethod
    def filter(
        self,
        *,
        subject: Optional[str] = None,
        record_type: Optional[RecordType] = None,
        related_to: Optional[str] = None,
        tags: Optional[List[str]] = None,
        active_only: bool = True,
        since: Optional[str] = None,
        until: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[MemoryRecord]:
        ...

    @abstractmethod
    def supersede(self, record_id: str, successor_id: str) -> bool:
        ...

    @abstractmethod
    def count(self, subject: Optional[str] = None) -> int:
        ...

    @abstractmethod
    def close(self) -> None:
        ...
