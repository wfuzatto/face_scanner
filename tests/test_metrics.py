from app.metrics.classification import VerificationMetrics, from_labeled_decisions


def test_far_and_frr_from_counts():
    metrics = VerificationMetrics(
        true_accept=90,
        true_reject=95,
        false_accept=5,
        false_reject=10,
    )
    assert metrics.far == 0.05
    assert metrics.frr == 0.10


def test_labeled_decisions_are_counted_without_threshold_logic():
    metrics = from_labeled_decisions(
        [
            (True, True),
            (True, False),
            (False, False),
            (False, True),
        ]
    )
    assert metrics.as_dict()["true_accept"] == 1
    assert metrics.as_dict()["false_reject"] == 1
    assert metrics.as_dict()["true_reject"] == 1
    assert metrics.as_dict()["false_accept"] == 1
