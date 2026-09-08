import time

from app.services.session_store import SessionStore


def test_session_is_one_time():
    store = SessionStore(ttl_seconds=60)
    created = store.create("RES-1", "match")
    assert store.get(created.id) is not None
    assert store.get(created.id) is not None
    assert store.consume(created.id) is not None
    assert store.get(created.id) is None
    assert store.consume(created.id) is None
    store.close()


def test_session_survives_store_restart(tmp_path):
    db = tmp_path / "sessions.sqlite3"
    first = SessionStore(ttl_seconds=60, db_path=db)
    created = first.create("RES-2", "match")
    first.close()

    second = SessionStore(ttl_seconds=60, db_path=db)
    restored = second.get(created.id)
    assert restored is not None
    assert restored.reservation_id == "RES-2"
    assert second.consume(created.id) is not None
    assert second.consume(created.id) is None
    second.close()


def test_expired_session_is_removed(tmp_path):
    db = tmp_path / "sessions.sqlite3"
    store = SessionStore(ttl_seconds=0, db_path=db)
    created = store.create("RES-3", "review")
    time.sleep(0.01)
    assert store.get(created.id) is None
    assert store.consume(created.id) is None
    assert store.count() == 0
    store.close()
