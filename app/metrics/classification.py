from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VerificationMetrics:
    true_accept: int
    true_reject: int
    false_accept: int
    false_reject: int

    @property
    def genuine_attempts(self) -> int:
        return self.true_accept + self.false_reject

    @property
    def impostor_attempts(self) -> int:
        return self.true_reject + self.false_accept

    @property
    def far(self) -> float | None:
        """False Acceptance Rate = falsos aceites / tentativas de impostores."""
        total = self.impostor_attempts
        return (self.false_accept / total) if total else None

    @property
    def frr(self) -> float | None:
        """False Rejection Rate = falsas rejeições / tentativas genuínas."""
        total = self.genuine_attempts
        return (self.false_reject / total) if total else None

    def as_dict(self) -> dict:
        return {
            "true_accept": self.true_accept,
            "true_reject": self.true_reject,
            "false_accept": self.false_accept,
            "false_reject": self.false_reject,
            "genuine_attempts": self.genuine_attempts,
            "impostor_attempts": self.impostor_attempts,
            "far": self.far,
            "frr": self.frr,
        }


def from_labeled_decisions(rows: list[tuple[bool, bool]]) -> VerificationMetrics:
    """Calcula métricas a partir de rótulos já definidos externamente.

    Cada tupla é (same_person_ground_truth, accepted_by_engine). Este helper não
    gera embeddings, não escolhe thresholds e não toma decisões biométricas.
    """
    ta = tr = fa = fr = 0
    for same_person, accepted in rows:
        if same_person and accepted:
            ta += 1
        elif same_person and not accepted:
            fr += 1
        elif not same_person and accepted:
            fa += 1
        else:
            tr += 1
    return VerificationMetrics(ta, tr, fa, fr)
