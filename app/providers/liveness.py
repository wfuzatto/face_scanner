from dataclasses import dataclass
from typing import Protocol


@dataclass
class LivenessProviderResult:
    status: str
    method: str
    message: str


class LivenessProvider(Protocol):
    """Contrato para PAD/liveness independente da verificação de identidade."""

    def check(self, *, verification_id: str, capture: bytes) -> LivenessProviderResult:
        ...


class DisabledLivenessProvider:
    """Fail-closed: nenhuma prova de vivacidade é presumida sem provider configurado."""

    def check(self, *, verification_id: str, capture: bytes) -> LivenessProviderResult:
        return LivenessProviderResult(
            status="not_checked",
            method="none",
            message="Liveness/PAD não configurado.",
        )
