from app.services.temporary_face_store import TemporaryFaceStore


def test_store_is_single_use_and_expires():
    now = [0.0]
    store = TemporaryFaceStore(10, lambda: now[0])
    store.put("a", "face")
    assert store.get("a") == "face"
    assert store.consume("a") == "face"
    assert store.consume("a") is None
    store.put("b", "face")
    now[0] = 11.0
    assert store.get("b") is None
