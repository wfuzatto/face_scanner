from dataclasses import dataclass
from typing import Protocol


@dataclass
class FaceVerificationResult:
    status: str
    provider: str
    identity_verified: bool
    message: str
    similarity: float | None = None
    threshold: float | None = None
    review_threshold: float | None = None


class FaceVerificationProvider(Protocol):
    """Contrato para um provider biométrico externo/homologado.

    O provider é responsável pela verificação de identidade. Este repositório
    apenas prepara a captura, valida qualidade e consome o resultado devolvido.
    """

    def verify(self, *, verification_id: str, selfie: bytes) -> FaceVerificationResult:
        ...


class DisabledFaceVerificationProvider:
    """Provider padrão: nenhuma identidade é confirmada sem integração externa."""

    def verify(self, *, verification_id: str, selfie: bytes) -> FaceVerificationResult:
        return FaceVerificationResult(
            status="not_configured",
            provider="disabled",
            identity_verified=False,
            message="Identidade não verificada: provider biométrico não configurado.",
        )
