from app.services.verification_gate import evaluate_checkin_gate


def test_gate_requires_all_three_checks():
    blocked = evaluate_checkin_gate(
        document_name_status="match",
        identity_verified=True,
        liveness_status="not_checked",
    )
    assert blocked.allowed is False
    assert "liveness_not_passed" in blocked.reasons

    allowed = evaluate_checkin_gate(
        document_name_status="match",
        identity_verified=True,
        liveness_status="passed",
    )
    assert allowed.allowed is True
    assert allowed.reasons == []
