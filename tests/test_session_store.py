from app.services.session_store import SessionStore

def test_session_is_one_time():
    store = SessionStore(ttl_seconds=60)
    created = store.create("RES-1", "match")
    assert store.consume(created.id) is not None
    assert store.consume(created.id) is None
