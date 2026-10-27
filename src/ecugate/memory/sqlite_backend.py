"""SQLite backend for structured agent memory."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, List, Optional

from ecugate.memory.models import MemoryRecord, RecordType
from ecugate.memory.storage import MemoryBackend


class SQLiteMemoryBackend(MemoryBackend):
    def __init__(self, path: str | Path = ":memory:") -> None:
        self.path = str(path)
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS memory_records (
                record_id TEXT PRIMARY KEY,
                record_type TEXT NOT NULL,
                subject TEXT NOT NULL,
                content_json TEXT NOT NULL,
                provenance_json TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                schema_version TEXT NOT NULL,
                related_ids_json TEXT NOT NULL,
                superseded_by TEXT,
                tags_json TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_mem_subject ON memory_records(subject);
            CREATE INDEX IF NOT EXISTS idx_mem_type ON memory_records(record_type);
            CREATE INDEX IF NOT EXISTS idx_mem_ts ON memory_records(timestamp);
            """
        )
        self._conn.commit()

    def append(self, record: MemoryRecord) -> None:
        try:
            self._conn.execute(
                """
                INSERT INTO memory_records (
                    record_id, record_type, subject, content_json, provenance_json,
                    timestamp, schema_version, related_ids_json, superseded_by, tags_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.record_id,
                    record.record_type.value,
                    record.subject,
                    json.dumps(record.content, sort_keys=True),
                    json.dumps(record.provenance.to_dict(), sort_keys=True),
                    record.timestamp,
                    record.schema_version,
                    json.dumps(record.related_ids),
                    record.superseded_by,
                    json.dumps(record.tags),
                ),
            )
            self._conn.commit()
        except sqlite3.IntegrityError as e:
            raise ValueError(f"record_id already exists: {record.record_id}") from e

    def get(self, record_id: str) -> Optional[MemoryRecord]:
        row = self._conn.execute(
            "SELECT * FROM memory_records WHERE record_id = ?", (record_id,)
        ).fetchone()
        if row is None:
            return None
        return self._row_to_record(row)

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
        clauses: List[str] = []
        params: List[Any] = []
        if subject is not None:
            clauses.append("subject = ?")
            params.append(subject)
        if record_type is not None:
            clauses.append("record_type = ?")
            params.append(record_type.value)
        if active_only:
            clauses.append("superseded_by IS NULL")
        if since is not None:
            clauses.append("timestamp >= ?")
            params.append(since)
        if until is not None:
            clauses.append("timestamp <= ?")
            params.append(until)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        sql = f"SELECT * FROM memory_records{where} ORDER BY timestamp ASC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        rows = self._conn.execute(sql, params).fetchall()
        records = [self._row_to_record(r) for r in rows]
        if related_to is not None:
            records = [r for r in records if related_to in r.related_ids or r.record_id == related_to]
        if tags:
            tag_set = set(tags)
            records = [r for r in records if tag_set.intersection(r.tags)]
        return records

    def supersede(self, record_id: str, successor_id: str) -> bool:
        cur = self._conn.execute(
            "UPDATE memory_records SET superseded_by = ? WHERE record_id = ? AND superseded_by IS NULL",
            (successor_id, record_id),
        )
        self._conn.commit()
        return cur.rowcount > 0

    def count(self, subject: Optional[str] = None) -> int:
        if subject is None:
            row = self._conn.execute("SELECT COUNT(*) FROM memory_records").fetchone()
        else:
            row = self._conn.execute(
                "SELECT COUNT(*) FROM memory_records WHERE subject = ?", (subject,)
            ).fetchone()
        return int(row[0]) if row else 0

    def close(self) -> None:
        self._conn.close()

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> MemoryRecord:
        d = {
            "record_id": row["record_id"],
            "record_type": row["record_type"],
            "subject": row["subject"],
            "content": json.loads(row["content_json"]),
            "provenance": json.loads(row["provenance_json"]),
            "timestamp": row["timestamp"],
            "schema_version": row["schema_version"],
            "related_ids": json.loads(row["related_ids_json"]),
            "superseded_by": row["superseded_by"],
            "tags": json.loads(row["tags_json"]),
        }
        return MemoryRecord.from_dict(d)
