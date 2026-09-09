import asyncio

import numpy as np
import pytest
from fastapi import HTTPException

from app import main
from app.providers.face_verification import FaceVerificationResult
from app.services.face_alignment import FaceAlignmentResult
from app.services.face_engine import FaceDetection
from app.services.session_store import SessionStore


class _Detector:
    ready = True

    def __init__(self, acceptable: bool):
        self.acceptable = acceptable
        self.detection = FaceDetection(
            bbox=[20, 20, 80, 100],
            score=.99,
            face_ratio=.3,
            landmarks={
                "eye_left": [40, 50],
                "eye_right": [75, 50],
                "nose": [58, 68],
                "mouth_left": [45, 92],
                "mouth_right": [72, 92],
            },
        )

    def detect(self, image):
        return [self.detection]

    def quality(self, image, detection, *_):
        return {
            "blur_score": 100,
            "brightness": 120,
            "face_ratio": .3,
            "acceptable": self.acceptable,
            "issues": [] if self.acceptable else ["imagem_desfocada"],
        }


class _Preview:
    def align(self, *_):
        return FaceAlignmentResult(False, 224, 224, None, None, "preview unavailable")


class _Provider:
    def __init__(self, status: str):
        self.status = status

    def verify(self, **_):
        return FaceVerificationResult(
            status=self.status,
            provider="synthetic-test",
            identity_verified=self.status == "match",
            message="synthetic",
            similarity=.9,
            match_threshold=.8,
            review_threshold=.5,
            threshold=.8,
            metric="synthetic",
            model="synthetic",
            model_version="test",
        )


def _configure(monkeypatch, *, acceptable: bool, status: str):
    store = SessionStore(ttl_seconds=60)
    detector = _Detector(acceptable)
    session = store.create("RES-TEST", "match")

    async def read_image(*_):
        return np.zeros((160, 160, 3), dtype=np.uint8), b"synthetic"

    monkeypatch.setattr(main, "sessions", store)
    monkeypatch.setattr(main, "face_detector", detector)
    monkeypatch.setattr(main, "face_alignment", _Preview())
    monkeypatch.setattr(main, "face_verification_provider", _Provider(status))
    monkeypatch.setattr(main, "read_image", read_image)
    return store, session.id


def test_quality_review_allows_retry_and_keeps_session(monkeypatch):
    store, verification_id = _configure(monkeypatch, acceptable=False, status="review")
    try:
        result = asyncio.run(main._verify_face_impl(verification_id, object(), main.settings))
        assert result.status == "review"
        assert result.retry_allowed is True
        assert result.identity_verified is False
        assert store.get(verification_id) is not None
    finally:
        store.close()


@pytest.mark.parametrize("status", ["review", "mismatch", "match", "not_configured"])
def test_provider_result_consumes_session_and_disallows_retry(monkeypatch, status):
    store, verification_id = _configure(monkeypatch, acceptable=True, status=status)
    try:
        result = asyncio.run(main._verify_face_impl(verification_id, object(), main.settings))
        assert result.retry_allowed is False
        assert store.get(verification_id) is None
        if status != "match":
            assert result.identity_verified is False
        with pytest.raises(HTTPException) as exc:
            asyncio.run(main._verify_face_impl(verification_id, object(), main.settings))
        assert exc.value.status_code == 404
    finally:
        store.close()
