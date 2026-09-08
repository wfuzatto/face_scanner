import math

import numpy as np
import pytest

from app.biometric import (
    CosineSimilarityEngine,
    EuclideanDistanceEngine,
    ThreeWayDecisionPolicy,
    VectorNormalizer,
)


def test_vector_normalizer_accepts_list_and_numpy_and_does_not_mutate():
    source = np.array([3.0, 4.0], dtype=np.float64)
    before = source.copy()
    result = VectorNormalizer(unit_norm=True).normalize(source)
    assert result.dtype == np.float32
    assert np.allclose(result, [0.6, 0.8], atol=1e-6)
    assert np.array_equal(source, before)


@pytest.mark.parametrize(
    "value",
    [[], [0.0, 0.0], [1.0, np.nan], [1.0, np.inf], [[1.0, 2.0]]],
)
def test_vector_normalizer_rejects_invalid_vectors(value):
    with pytest.raises(ValueError):
        VectorNormalizer().normalize(value)


def test_cosine_similarity_known_cases():
    engine = CosineSimilarityEngine()
    assert engine.compare([1, 0], [1, 0]) == pytest.approx(1.0, abs=1e-6)
    assert engine.compare([1, 0], [0, 1]) == pytest.approx(0.0, abs=1e-6)
    assert engine.compare([1, 0], [-1, 0]) == pytest.approx(-1.0, abs=1e-6)


def test_cosine_similarity_returns_metadata():
    result = CosineSimilarityEngine().evaluate([1, 2, 3], [1, 2, 3])
    assert result.metric == "cosine_similarity"
    assert result.dimensions == 3
    assert result.score == pytest.approx(1.0, abs=1e-6)


def test_similarity_engines_reject_dimension_mismatch():
    with pytest.raises(ValueError):
        CosineSimilarityEngine().compare([1, 2], [1, 2, 3])
    with pytest.raises(ValueError):
        EuclideanDistanceEngine().compare([1, 2], [1, 2, 3])


def test_euclidean_distance_known_case():
    engine = EuclideanDistanceEngine()
    assert engine.compare([1, 2], [4, 6]) == pytest.approx(5.0)
    result = engine.evaluate([1, 2], [4, 6])
    assert result.metric == "euclidean_distance"
    assert result.dimensions == 2
    assert result.score == pytest.approx(5.0)


def test_higher_is_better_boundaries():
    policy = ThreeWayDecisionPolicy(0.4, 0.8, direction="higher_is_better")
    assert policy.decide(0.39).status == "mismatch"
    assert policy.decide(0.4).status == "review"
    assert policy.decide(0.79).status == "review"
    assert policy.decide(0.8).status == "match"


def test_lower_is_better_boundaries():
    policy = ThreeWayDecisionPolicy(0.8, 0.4, direction="lower_is_better")
    assert policy.decide(0.4).status == "match"
    assert policy.decide(0.41).status == "review"
    assert policy.decide(0.8).status == "review"
    assert policy.decide(0.81).status == "mismatch"


def test_threshold_configuration_validation():
    with pytest.raises(ValueError):
        ThreeWayDecisionPolicy(0.8, 0.4, direction="higher_is_better")
    with pytest.raises(ValueError):
        ThreeWayDecisionPolicy(0.4, 0.8, direction="lower_is_better")
    with pytest.raises(ValueError):
        ThreeWayDecisionPolicy(math.nan, 0.8)


def test_unconfigured_policy_fails_closed():
    policy = ThreeWayDecisionPolicy()
    assert policy.calibrated is False
    with pytest.raises(RuntimeError):
        policy.decide(0.9)


def test_non_finite_score_rejected():
    policy = ThreeWayDecisionPolicy(0.4, 0.8)
    with pytest.raises(ValueError):
        policy.decide(float("nan"))
    with pytest.raises(ValueError):
        policy.decide(float("inf"))
