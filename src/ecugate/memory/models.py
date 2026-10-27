"""Structured memory record types and provenance."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4


class RecordType(str, enum.Enum):
    FACT = "fact"
    EVENT = "event"
    DECISION = "decision"
    OUTCOME = "outcome"
    PROCEDURE = "procedure"
    FAILURE = "failure"
    OBSERVATION = "observation"
    OPERATION = "operation"


@dataclass
class Provenance:
    source: str
    operation_id: Optional[str] = None
    confidence: Optional[float] = None
    is_observed: bool = True
    agent_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "operation_id": self.operation_id,
            "confidence": self.confidence,
            "is_observed": self.is_observed,
            "agent_id": self.agent_id,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Provenance":
        return cls(
            source=d["source"],
            operation_id=d.get("operation_id"),
            confidence=d.get("confidence"),
            is_observed=d.get("is_observed", True),
            agent_id=d.get("agent_id"),
        )


SCHEMA_VERSION = "1.0"


@dataclass
class MemoryRecord:
    record_id: str
    record_type: RecordType
    subject: str
    content: Dict[str, Any]
    provenance: Provenance
    timestamp: str
    schema_version: str = SCHEMA_VERSION
    related_ids: List[str] = field(default_factory=list)
    superseded_by: Optional[str] = None
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "record_type": self.record_type.value,
            "subject": self.subject,
            "content": self.content,
            "provenance": self.provenance.to_dict(),
            "timestamp": self.timestamp,
            "schema_version": self.schema_version,
            "related_ids": list(self.related_ids),
            "superseded_by": self.superseded_by,
            "tags": list(self.tags),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "MemoryRecord":
        return cls(
            record_id=d["record_id"],
            record_type=RecordType(d["record_type"]),
            subject=d["subject"],
            content=d["content"],
            provenance=Provenance.from_dict(d["provenance"]),
            timestamp=d["timestamp"],
            schema_version=d.get("schema_version", SCHEMA_VERSION),
            related_ids=list(d.get("related_ids") or []),
            superseded_by=d.get("superseded_by"),
            tags=list(d.get("tags") or []),
        )

    def is_active(self) -> bool:
        return self.superseded_by is None


def new_record_id() -> str:
    return str(uuid4())


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_record(
    record_type: RecordType,
    subject: str,
    content: Dict[str, Any],
    provenance: Provenance,
    *,
    related_ids: Optional[List[str]] = None,
    tags: Optional[List[str]] = None,
    record_id: Optional[str] = None,
    timestamp: Optional[str] = None,
) -> MemoryRecord:
    return MemoryRecord(
        record_id=record_id or new_record_id(),
        record_type=record_type,
        subject=subject,
        content=content,
        provenance=provenance,
        timestamp=timestamp or utc_now_iso(),
        related_ids=list(related_ids or []),
        tags=list(tags or []),
    )
