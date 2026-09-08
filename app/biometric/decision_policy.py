from __future__ import annotations

import math
import os

from .vector_types import Direction, VectorDecisionResult


class ThreeWayDecisionPolicy:
    """Política genérica de três faixas para scores numéricos configuráveis.

    Para ``higher_is_better``:
      score < review_threshold -> mismatch
      review_threshold <= score < match_threshold -> review
      score >= match_threshold -> match

    Para ``lower_is_better``:
      score <= match_threshold -> match
      match_threshold < score <= review_threshold -> review
      score > review_threshold -> mismatch

    A classe não conhece a origem dos scores e não escolhe thresholds.
    """

    def __init__(
        self,
        review_threshold: float | None = None,
        match_threshold: float | None = None,
        *,
        direction: Direction = "higher_is_better",
    ) -> None:
        if direction not in ("higher_is_better", "lower_is_better"):
            raise ValueError("direction must be higher_is_better or lower_is_better")
        self.review_threshold = review_threshold
        self.match_threshold = match_threshold
        self.direction = direction
        self._validate_thresholds()

    @property
    def calibrated(self) -> bool:
        return self.review_threshold is not None and self.match_threshold is not None

    def _validate_thresholds(self) -> None:
        if not self.calibrated:
            return
        review = float(self.review_threshold)
        match = float(self.match_threshold)
        if not math.isfinite(review) or not math.isfinite(match):
            raise ValueError("thresholds must be finite")
        if self.direction == "higher_is_better" and not review < match:
            raise ValueError("higher_is_better requires review_threshold < match_threshold")
        if self.direction == "lower_is_better" and not match < review:
            raise ValueError("lower_is_better requires match_threshold < review_threshold")

    @classmethod
    def from_environment(
        cls,
        *,
        prefix: str = "VECTOR",
        direction: Direction = "higher_is_better",
    ) -> "ThreeWayDecisionPolicy":
        def read(name: str) -> float | None:
            value = os.getenv(name)
            if value is None or not value.strip():
                return None
            try:
                result = float(value)
            except ValueError as exc:
                raise ValueError(f"{name} must be numeric") from exc
            if not math.isfinite(result):
                raise ValueError(f"{name} must be finite")
            return result

        return cls(
            review_threshold=read(f"{prefix}_REVIEW_THRESHOLD"),
            match_threshold=read(f"{prefix}_MATCH_THRESHOLD"),
            direction=direction,
        )

    def decide(self, score: float) -> VectorDecisionResult:
        score = float(score)
        if not math.isfinite(score):
            raise ValueError("score must be finite")
        if not self.calibrated:
            raise RuntimeError("decision policy is not calibrated: thresholds are not configured")

        review = float(self.review_threshold)
        match = float(self.match_threshold)

        if self.direction == "higher_is_better":
            if score < review:
                status = "mismatch"
            elif score < match:
                status = "review"
            else:
                status = "match"
        else:
            if score <= match:
                status = "match"
            elif score <= review:
                status = "review"
            else:
                status = "mismatch"

        return VectorDecisionResult(
            status=status,
            score=score,
            review_threshold=review,
            match_threshold=match,
            calibrated=True,
            direction=self.direction,
        )
