import logging
from dataclasses import dataclass
from typing import Protocol

import numpy as np

from app.biometric.pipeline import BiometricPipeline
from app.services.face_engine import FaceDetection

logger = logging.getLogger("face_scanner.biometric")


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

    def verify(
        self,
        *,
        verification_id: str,
        selfie: bytes,
        document_face: np.ndarray | None = None,
        live_face: np.ndarray | None = None,
    ) -> FaceVerificationResult:
        ...


class DisabledFaceVerificationProvider:
    """Provider padrão: nenhuma identidade é confirmada sem integração externa."""

    requires_aligned_faces = False

    def verify(self, *, verification_id: str, selfie: bytes, document_face=None, live_face=None) -> FaceVerificationResult:
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

    requires_aligned_faces = False

    def verify(self, *, verification_id: str, selfie: bytes, document_face=None, live_face=None) -> FaceVerificationResult:
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


class NotConfiguredFaceVerificationProvider:
    """Represents a requested but unusable provider without claiming verification."""

    requires_aligned_faces = False

    def __init__(self, provider: str, message: str) -> None:
        self.provider = provider
        self.message = message

    def verify(self, *, verification_id: str, selfie: bytes, document_face=None, live_face=None) -> FaceVerificationResult:
        return FaceVerificationResult("not_configured", self.provider, False, self.message)


class InternalFaceVerificationProvider:
    """Adapter around the supplied internal SFace pipeline."""

    provider = "internal"
    requires_aligned_faces = True

    def __init__(self, pipeline: BiometricPipeline) -> None:
        self.pipeline = pipeline

    def prepare_face(self, image: np.ndarray, detection: FaceDetection) -> np.ndarray:
        if detection.face_box is None:
            raise ValueError("SFace requires the complete FaceDetectorYN face_box")
        return self.pipeline.embedding_engine.align_crop(image, detection.face_box)

    def verify(self, *, verification_id: str, selfie: bytes, document_face: np.ndarray | None = None, live_face: np.ndarray | None = None) -> FaceVerificationResult:
        if document_face is None or live_face is None:
            return FaceVerificationResult("not_configured", self.provider, False, "Faces temporárias indisponíveis para o provider interno.")
        try:
            result = self.pipeline.compare(document_face, live_face)
        except Exception as exc:
            engine = getattr(self.pipeline, "embedding_engine", None)
            model = str(getattr(engine, "model_name", "unknown"))[:120]
            detail = " ".join(str(exc).split())[:240]
            logger.warning(
                "biometric pipeline failed provider=%s model=%s error_type=%s error=%s",
                self.provider, model, type(exc).__name__, detail or "no technical message",
            )
            return FaceVerificationResult("review", self.provider, False, "Falha no motor biométrico; identidade não verificada.")
        status = result.status if result.status in {"match", "review", "mismatch", "not_configured"} else "review"
        message = (
            "Comparação facial técnica concluída; score real calculado, "
            "mas a decisão biométrica está desativada sem thresholds homologados."
            if status == "not_configured"
            else "Comparação facial concluída."
        )
        return FaceVerificationResult(
            status=status,
            provider=self.provider,
            identity_verified=status == "match" and bool(result.identity_verified),
            message=message,
            similarity=result.similarity,
            match_threshold=result.match_threshold,
            review_threshold=result.review_threshold,
            threshold=result.match_threshold,
            metric=result.metric,
            model=result.model,
            model_version=result.model_version,
            processing_ms=result.total_ms,
            embedding_document_ms=result.embedding_document_ms,
            embedding_live_ms=result.embedding_live_ms,
            similarity_ms=result.similarity_ms,
        )
