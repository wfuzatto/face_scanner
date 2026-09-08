from dataclasses import dataclass


@dataclass(frozen=True)
class VerificationGateResult:
    allowed: bool
    reasons: list[str]


def evaluate_checkin_gate(
    *,
    document_name_status: str,
    identity_verified: bool,
    liveness_status: str,
) -> VerificationGateResult:
    """Regra fail-closed para futura automação de check-in.

    Esta função apenas combina resultados já produzidos pelas etapas do fluxo;
    não executa reconhecimento facial nem liveness.
    """
    reasons: list[str] = []
    if document_name_status != "match":
        reasons.append("document_name_not_confirmed")
    if identity_verified is not True:
        reasons.append("identity_not_verified")
    if liveness_status != "passed":
        reasons.append("liveness_not_passed")
    return VerificationGateResult(allowed=not reasons, reasons=reasons)
