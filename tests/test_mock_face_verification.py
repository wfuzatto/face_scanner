import pytest

from app.providers.face_verification import MockFaceVerificationProvider


@pytest.mark.parametrize(
    "status,expected_identity,expected_score",
    [
        ("match", True, 0.95),
        ("review", False, 0.65),
        ("mismatch", False, 0.20),
        ("not_configured", False, None),
    ],
)
def test_mock_provider_exercises_ui_states_without_processing_images(status, expected_identity, expected_score):
    provider = MockFaceVerificationProvider(status)
    result = provider.verify(verification_id="verification-test", selfie=b"ignored-by-mock")

    assert result.status == status
    assert result.provider == "mock_homologation"
    assert result.identity_verified is expected_identity
    assert result.similarity == expected_score
    assert result.metric == "synthetic_fixed_score"
    assert result.model == "mock-state-machine"
    assert "SIMULAÇÃO DE HOMOLOGAÇÃO" in result.message


def test_mock_provider_rejects_unknown_state():
    with pytest.raises(ValueError):
        MockFaceVerificationProvider("unknown")
