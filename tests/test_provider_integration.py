import numpy as np

from app.providers.face_verification import InternalFaceVerificationProvider, NotConfiguredFaceVerificationProvider


def test_missing_model_provider_fails_closed():
    result = NotConfiguredFaceVerificationProvider("internal", "model missing").verify(verification_id="x", selfie=b"")
    assert (result.provider, result.status, result.identity_verified) == ("internal", "not_configured", False)


def test_internal_exception_is_review_and_never_identity_verified(caplog):
    class Pipeline:
        embedding_engine = type("Engine", (), {"model_name": "test-model"})()
        def compare(self, *_):
            raise RuntimeError("safe technical failure")
    result = InternalFaceVerificationProvider(Pipeline()).verify(verification_id="x", selfie=b"", document_face=np.zeros(1), live_face=np.zeros(1))
    assert result.status == "review"
    assert result.identity_verified is False
    assert "error_type=RuntimeError" in caplog.text


def test_internal_review_never_verifies_identity():
    class Pipeline:
        def compare(self, *_):
            return type("Result", (), {"status": "review", "identity_verified": True, "similarity": .6, "match_threshold": .8, "review_threshold": .5, "metric": "cosine", "model": "test", "model_version": "1", "total_ms": 1, "embedding_document_ms": 0, "embedding_live_ms": 0, "similarity_ms": 0})()
    result = InternalFaceVerificationProvider(Pipeline()).verify(verification_id="x", selfie=b"", document_face=np.zeros(1), live_face=np.zeros(1))
    assert result.status == "review" and result.identity_verified is False
