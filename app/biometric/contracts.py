from __future__ import annotations

from typing import Protocol

import numpy as np


@dataclass(frozen=True)
class EmbeddingOutput:
    vector: np.ndarray
    model: str
    model_version: str


class EmbeddingEngine(Protocol):
    """Ponto de extensão para o motor de representação facial.

    A implementação real deve ser fornecida separadamente. O Face Scanner não
    inclui um modelo que reconheça/identifique pessoas.
    """

    def embed(self, aligned_face: np.ndarray) -> EmbeddingOutput:
        ...


class SimilarityEngine(Protocol):
    """Compara somente vetores numéricos e retorna o score."""

    def compare(self, vector_a: np.ndarray, vector_b: np.ndarray) -> float:
        ...


class DecisionPolicy(Protocol):
    """Transforma um score em faixas calibradas externamente."""

    def decide(self, score: float):
        ...


class BiometricEngineNotConfigured(RuntimeError):
    pass
