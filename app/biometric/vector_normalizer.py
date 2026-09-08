from __future__ import annotations

import numpy as np

from .vector_types import VectorInput


class VectorNormalizer:
    """Valida e, opcionalmente, normaliza um vetor numérico pela norma L2."""

    def __init__(self, *, unit_norm: bool = True) -> None:
        self.unit_norm = unit_norm

    def normalize(self, vector: VectorInput) -> np.ndarray:
        try:
            result = np.asarray(vector, dtype=np.float32)
        except (TypeError, ValueError) as exc:
            raise ValueError("vector must contain numeric values") from exc

        if result.ndim != 1:
            raise ValueError("vector must be one-dimensional")
        if result.size == 0:
            raise ValueError("vector must not be empty")
        if not np.all(np.isfinite(result)):
            raise ValueError("vector must not contain NaN or infinity")

        norm = float(np.linalg.norm(result.astype(np.float64)))
        if norm == 0.0:
            raise ValueError("vector must have a non-zero L2 norm")

        if self.unit_norm:
            result = (result / np.float32(norm)).astype(np.float32, copy=False)
        return result.copy()
