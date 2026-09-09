from dataclasses import dataclass
from typing import Protocol


@dataclass
class FaceVerificationResult:
    status: str
    provider: str
    identity_verified: bool
    message: str
    similarity: float | None = None
    match_threshold: float | None = None
    review_threshold: float | None = None
    # Alias histórico para match_threshold.
    threshold: float | None = None
    metric: str | None = None
    model: str | None = None
    model_version: str | None = None
    processing_ms: float | None = None
    embedding_document_ms: float | None = None
    embedding_live_ms: float | None = None
    similarity_ms: float | None = None


class FaceVerificationProvider(Protocol):
    """Contrato para um provider biométrico externo/homologado.

    O Face Scanner prepara a captura, valida qualidade e consome o resultado.
    A implementação real do provider permanece desacoplada deste repositório.
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
