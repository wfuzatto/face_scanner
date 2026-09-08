from dataclasses import dataclass
from typing import Protocol

@dataclass
class FaceVerificationResult:
    status: str
    provider: str
    message: str

class FaceVerificationProvider(Protocol):
    def verify(self, *, verification_id: str, selfie: bytes) -> FaceVerificationResult:
        ...

class DisabledFaceVerificationProvider:
    """Provider padrão: o matching biométrico não é implementado neste repositório."""
    def verify(self, *, verification_id: str, selfie: bytes) -> FaceVerificationResult:
        return FaceVerificationResult(status="not_configured", provider="disabled", message="Provider de verificação biométrica não configurado.")
