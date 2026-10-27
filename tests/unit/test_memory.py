import os
import tempfile

from ecugate.memory import MemoryStore, RecordType, Provenance
from ecugate.memory.models import make_record
from ecugate.memory.sqlite_backend import SQLiteMemoryBackend


def test_append_retrieve_persist():
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "m.db")
        store = MemoryStore(SQLiteMemoryBackend(path))
        rec = store.record(
            RecordType.FACT,
            "vehicle:1",
            {"spark": 15},
            Provenance(source="test", is_observed=True, confidence=1.0),
            tags=["ecu"],
        )
        got = store.get(rec.record_id)
        assert got is not None
        assert got.content["spark"] == 15
        store.close()

        store2 = MemoryStore(SQLiteMemoryBackend(path))
        again = store2.get(rec.record_id)
        assert again is not None
        assert again.content["spark"] == 15
        listed = store2.retrieve(subject="vehicle:1", record_type=RecordType.FACT)
        assert len(listed) == 1
        store2.close()


def test_supersede_preserves_history():
    store = MemoryStore()
    r1 = store.record(
        RecordType.FACT,
        "e",
        {"v": 1},
        Provenance(source="t", is_observed=True),
    )
    r2 = make_record(
        RecordType.FACT,
        "e",
        {"v": 2},
        Provenance(source="t", is_observed=True),
        related_ids=[r1.record_id],
    )
    store.supersede(r1.record_id, r2)
    active = store.retrieve(subject="e", active_only=True)
    assert len(active) == 1
    assert active[0].content["v"] == 2
    all_recs = store.retrieve(subject="e", active_only=False)
    assert len(all_recs) == 2
    old = store.get(r1.record_id)
    assert old is not None
    assert old.superseded_by == r2.record_id


def test_failure_record():
    store = MemoryStore()
    store.record(
        RecordType.FAILURE,
        "e",
        {"error": "boom"},
        Provenance(source="tool:x", is_observed=True),
    )
    fails = store.retrieve(record_type=RecordType.FAILURE)
    assert len(fails) == 1
