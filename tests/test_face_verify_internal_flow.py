import asyncio

import numpy as np
import pytest
from fastapi import HTTPException

from app import main
from app.providers.face_verification import FaceVerificationResult
from app.services.face_engine import FaceDetection
from app.services.session_store import SessionStore
from app.services.temporary_face_store import TemporaryFaceStore


class Detector:
    ready = True
    detection = FaceDetection(
        [20, 20, 80, 100],
        .99,
        .3,
        {
            "eye_left": [40, 50],
            "eye_right": [75, 50],
            "nose": [58, 68],
            "mouth_left": [45, 92],
            "mouth_right": [72, 92],
        },
        np.array(
            [20, 20, 80, 100, 40, 50, 75, 50, 58, 68, 45, 92, 72, 92, .99],
            dtype=np.float32,
        ),
    )

    def __init__(self, acceptable):
        self.acceptable = acceptable

    def detect(self, _):
        return [self.detection]

    def quality(self, *_):
        return {
            "blur_score": 100,
            "brightness": 120,
            "face_ratio": .3,
            "acceptable": self.acceptable,
            "issues": [] if self.acceptable else ["imagem_desfocada"],
        }


class Provider:
    requires_aligned_faces = True
    provider = "internal"

    def __init__(self, status):
        self.status = status

    def prepare_face(self, *_):
        return np.ones((112, 112, 3), dtype=np.uint8)

    def verify(self, **_):
        return FaceVerificationResult(
            self.status,
            "internal",
            self.status == "match",
            "synthetic",
        )


def configured(monkeypatch, acceptable, status):
    store, faces = SessionStore(60), TemporaryFaceStore(60)
    session = store.create("RES", "match")
    faces.put(session.id, np.ones((112, 112, 3), dtype=np.uint8))

    async def read_image(*_):
        return np.zeros((160, 160, 3), dtype=np.uint8), b"safe"

    monkeypatch.setattr(main, "sessions", store)
    monkeypatch.setattr(main, "document_faces", faces)
    monkeypatch.setattr(main, "face_detector", Detector(acceptable))
    monkeypatch.setattr(main, "face_verification_provider", Provider(status))
    monkeypatch.setattr(main, "read_image", read_image)
    return store, faces, session.id


def test_quality_review_keeps_session(monkeypatch):
    store, faces, ident = configured(monkeypatch, False, "review")
    try:
        result = asyncio.run(main._verify_face_impl(ident, object(), main.settings))
        assert result.status == "review"
        assert result.retry_allowed is True
        assert result.attempts_used == 0
        assert store.get(ident) is not None
        assert faces.get(ident) is not None
    finally:
        store.close()


@pytest.mark.parametrize("status", ["review", "mismatch"])
def test_provider_review_or_mismatch_retries_twice_then_closes(monkeypatch, status):
    store, faces, ident = configured(monkeypatch, True, status)
    try:
        for attempt in range(1, 4):
            result = asyncio.run(main._verify_face_impl(ident, object(), main.settings))
            assert result.status == status
            assert result.attempts_used == attempt
            assert result.attempts_remaining == 3 - attempt
            assert result.retry_allowed is (attempt < 3)
            if attempt < 3:
                assert store.get(ident) is not None
                assert faces.get(ident) is not None
            else:
                assert store.get(ident) is None
                assert faces.get(ident) is None
                assert "recepção" in result.message

        with pytest.raises(HTTPException):
            asyncio.run(main._verify_face_impl(ident, object(), main.settings))
    finally:
        store.close()


def test_match_consumes_session_and_face_immediately(monkeypatch):
    store, faces, ident = configured(monkeypatch, True, "match")
    try:
        result = asyncio.run(main._verify_face_impl(ident, object(), main.settings))
        assert result.status == "match"
        assert result.identity_verified is True
        assert result.retry_allowed is False
        assert result.attempts_used == 1
        assert store.get(ident) is None
        assert faces.get(ident) is None

        with pytest.raises(HTTPException):
            asyncio.run(main._verify_face_impl(ident, object(), main.settings))
    finally:
        store.close()
