from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np


@dataclass(frozen=True)
class EmbeddingOutput:
    vector: np.ndarray
    model: str
    model_version: str


@dataclass(frozen=True)
class SimilarityOutput:
    score: float
    metric: str


@dataclass(frozen=True)
class DecisionOutput:
    status: str
    identity_verified: bool
    threshold: float | None = None
    review_threshold: float | None = None


class EmbeddingEngine(Protocol):
    """Ponto de extensão para o motor de representação facial.

    A implementação real deve ser fornecida separadamente. O Face Scanner não
    inclui um modelo que reconheça/identifique pessoas.
    """

    def embed(self, aligned_face: np.ndarray) -> EmbeddingOutput:
        ...


class SimilarityEngine(Protocol):
    """Ponto de extensão para a métrica escolhida pelo motor biométrico."""

    def compare(self, document: EmbeddingOutput, live: EmbeddingOutput) -> SimilarityOutput:
        ...


class DecisionPolicy(Protocol):
    """Ponto de extensão para a política match/review/mismatch calibrada externamente."""

    def decide(self, similarity: SimilarityOutput) -> DecisionOutput:
        ...


class BiometricEngineNotConfigured(RuntimeError):
    pass
