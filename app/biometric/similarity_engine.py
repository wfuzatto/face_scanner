from __future__ import annotations

import math

import numpy as np

from .vector_normalizer import VectorNormalizer
from .vector_types import VectorInput, VectorSimilarityResult


class CosineSimilarityEngine:
    """Similaridade cosseno genérica. Não aplica thresholds nem conhece o domínio dos vetores."""

    metric = "cosine_similarity"

    def __init__(self, normalizer: VectorNormalizer | None = None) -> None:
        self.normalizer = normalizer or VectorNormalizer(unit_norm=True)

    def compare(self, vector_a: VectorInput, vector_b: VectorInput) -> float:
        a = self.normalizer.normalize(vector_a)
        b = self.normalizer.normalize(vector_b)
        if a.shape != b.shape:
            raise ValueError("vectors must have exactly the same dimensions")

        score = float(np.dot(a.astype(np.float64), b.astype(np.float64)))
        if not math.isfinite(score):
            raise ValueError("similarity result is not finite")
        return float(np.clip(score, -1.0, 1.0))

    def evaluate(self, vector_a: VectorInput, vector_b: VectorInput) -> VectorSimilarityResult:
        a = self.normalizer.normalize(vector_a)
        b = self.normalizer.normalize(vector_b)
        if a.shape != b.shape:
            raise ValueError("vectors must have exactly the same dimensions")
        score = float(np.dot(a.astype(np.float64), b.astype(np.float64)))
        if not math.isfinite(score):
            raise ValueError("similarity result is not finite")
        score = float(np.clip(score, -1.0, 1.0))
        return VectorSimilarityResult(metric=self.metric, score=score, dimensions=int(a.size))


class EuclideanDistanceEngine:
    """Distância euclidiana genérica. Menor valor significa vetores mais próximos."""

    metric = "euclidean_distance"

    def __init__(self, normalizer: VectorNormalizer | None = None) -> None:
        self.normalizer = normalizer or VectorNormalizer(unit_norm=False)

    def compare(self, vector_a: VectorInput, vector_b: VectorInput) -> float:
        a = self.normalizer.normalize(vector_a)
        b = self.normalizer.normalize(vector_b)
        if a.shape != b.shape:
            raise ValueError("vectors must have exactly the same dimensions")

        distance = float(np.linalg.norm(a.astype(np.float64) - b.astype(np.float64)))
        if not math.isfinite(distance):
            raise ValueError("distance result is not finite")
        return distance

    def evaluate(self, vector_a: VectorInput, vector_b: VectorInput) -> VectorSimilarityResult:
        a = self.normalizer.normalize(vector_a)
        b = self.normalizer.normalize(vector_b)
        if a.shape != b.shape:
            raise ValueError("vectors must have exactly the same dimensions")
        distance = float(np.linalg.norm(a.astype(np.float64) - b.astype(np.float64)))
        if not math.isfinite(distance):
            raise ValueError("distance result is not finite")
        return VectorSimilarityResult(metric=self.metric, score=distance, dimensions=int(a.size))
