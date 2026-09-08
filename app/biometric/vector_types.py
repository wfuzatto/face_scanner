from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol, Sequence

import numpy as np

VectorInput = Sequence[float] | np.ndarray
DecisionStatus = Literal["mismatch", "review", "match"]
Direction = Literal["higher_is_better", "lower_is_better"]


class VectorSimilarityEngine(Protocol):
    """Contrato genérico: compara dois vetores numéricos e retorna um score."""

    def compare(self, vector_a: VectorInput, vector_b: VectorInput) -> float:
        ...


class VectorDecisionPolicy(Protocol):
    """Contrato genérico: transforma um score em três faixas configuráveis."""

    def decide(self, score: float) -> "VectorDecisionResult":
        ...


@dataclass(frozen=True)
class VectorSimilarityResult:
    metric: str
    score: float
    dimensions: int


@dataclass(frozen=True)
class VectorDecisionResult:
    status: DecisionStatus
    score: float
    review_threshold: float | None
    match_threshold: float | None
    calibrated: bool
    direction: Direction
