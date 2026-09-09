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


class MockFaceVerificationProvider:
    """Provider sintético de homologação.

    Não processa a imagem, não compara pessoas, não gera embeddings e não deve ser
    usado como prova de identidade. Serve apenas para exercitar os estados da UI e
    a integração Totem -> Face Scanner de forma determinística.
    """

    _ALLOWED = {"match", "review", "mismatch", "not_configured"}
    _SCORES = {
        "match": 0.95,
        "review": 0.65,
        "mismatch": 0.20,
        "not_configured": None,
    }

    def __init__(self, status: str = "review") -> None:
        normalized = str(status).strip().lower()
        if normalized not in self._ALLOWED:
            raise ValueError(f"FACE_MOCK_STATUS inválido: {status}")
        self.status = normalized

    def verify(self, *, verification_id: str, selfie: bytes) -> FaceVerificationResult:
        score = self._SCORES[self.status]
        identity_verified = self.status == "match"
        return FaceVerificationResult(
            status=self.status,
            provider="mock_homologation",
            identity_verified=identity_verified,
            message=(
                "SIMULAÇÃO DE HOMOLOGAÇÃO: resultado sintético; nenhuma identidade foi comparada."
            ),
            similarity=score,
            review_threshold=0.50 if score is not None else None,
            match_threshold=0.80 if score is not None else None,
            threshold=0.80 if score is not None else None,
            metric="synthetic_fixed_score",
            model="mock-state-machine",
            model_version="1",
            processing_ms=0.0,
            embedding_document_ms=0.0,
            embedding_live_ms=0.0,
            similarity_ms=0.0,
        )
