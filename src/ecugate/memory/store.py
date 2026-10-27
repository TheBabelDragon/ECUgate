"""High-level memory store API. Recalled memory is never authorization."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ecugate.memory.models import MemoryRecord, Provenance, RecordType, make_record
from ecugate.memory.storage import MemoryBackend
from ecugate.memory.sqlite_backend import SQLiteMemoryBackend


class MemoryStore:
    def __init__(self, backend: Optional[MemoryBackend] = None) -> None:
        self._backend = backend or SQLiteMemoryBackend(":memory:")

    @property
    def backend(self) -> MemoryBackend:
        return self._backend

    def append(self, record: MemoryRecord) -> MemoryRecord:
        self._backend.append(record)
        return record

    def record(
        self,
        record_type: RecordType,
        subject: str,
        content: Dict[str, Any],
        provenance: Provenance,
        *,
        related_ids: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
    ) -> MemoryRecord:
        rec = make_record(
            record_type, subject, content, provenance, related_ids=related_ids, tags=tags
        )
        return self.append(rec)

    def get(self, record_id: str) -> Optional[MemoryRecord]:
        return self._backend.get(record_id)

    def retrieve(
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
    ) -> List[MemoryRecord]:
        return self._backend.filter(
            subject=subject,
            record_type=record_type,
            related_to=related_to,
            tags=tags,
            active_only=active_only,
            since=since,
            until=until,
            limit=limit,
        )

    def supersede(self, record_id: str, successor: MemoryRecord) -> MemoryRecord:
        self.append(successor)
        self._backend.supersede(record_id, successor.record_id)
        return successor

    def close(self) -> None:
        self._backend.close()
