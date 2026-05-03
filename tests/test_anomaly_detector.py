"""Anomaly detector tests — z-score based ML detection."""

from __future__ import annotations

import pytest

from core.anomaly_detector import AnomalyDetector, StepBaseline


def test_step_baseline_empty():
    b = StepBaseline(window_size=10)
    assert b.count == 0
    assert b.mean == 0.0
    assert b.std == 0.0
    assert b.z_score(5.0) == 0.0


def test_step_baseline_stats():
    b = StepBaseline(window_size=100)
    for v in [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0]:
        b.push(v)
    assert b.count == 8
    assert abs(b.mean - 5.0) < 0.01
    assert b.std > 0


def test_step_baseline_rolling_window():
    b = StepBaseline(window_size=3)
    for v in [1.0, 2.0, 3.0, 100.0]:
        b.push(v)
    assert b.count == 3  # window capped
    # Window is [2.0, 3.0, 100.0]
    assert abs(b.mean - 35.0) < 0.01


def test_detector_no_anomaly_before_min_samples():
    det = AnomalyDetector("m1", min_samples=5, window_size=10)
    # Feed 4 samples — not enough for detection
    for i in range(4):
        result = det.evaluate(0, "Step 1", 3.0)
        assert result.is_anomaly is False
        assert result.z_score == 0.0


def test_detector_flags_anomaly_on_spike():
    det = AnomalyDetector("m1", z_threshold=2.0, min_samples=10, window_size=20)
    # Build stable baseline with slight natural variance
    import random
    random.seed(42)
    for _ in range(20):
        det.evaluate(0, "Step 1", 3.0 + random.uniform(-0.3, 0.3))

    # Spike — should be flagged
    result = det.evaluate(0, "Step 1", 30.0)
    assert result.is_anomaly is True
    assert result.z_score > 2.0


def test_detector_no_false_positive_on_normal():
    det = AnomalyDetector("m1", z_threshold=2.5, min_samples=10, window_size=20)
    import random
    random.seed(99)
    for _ in range(20):
        det.evaluate(0, "Step 1", 3.0 + random.uniform(-0.3, 0.3))

    # Normal value within 1σ — should NOT be flagged
    result = det.evaluate(0, "Step 1", 3.1)
    assert result.is_anomaly is False


def test_evaluate_all():
    """evaluate_all processes multiple steps."""
    from core.data_model import CycleStats

    det = AnomalyDetector("m1", min_samples=5, window_size=10)
    # Build baseline
    for _ in range(10):
        det.evaluate(0, "Step 1", 3.0)
        det.evaluate(1, "Step 2", 5.0)

    stats = [
        CycleStats(machine_id="m1", step_index=0, step_name="Step 1", cv_pct=3.0),
        CycleStats(machine_id="m1", step_index=1, step_name="Step 2", cv_pct=5.0),
    ]
    results = det.evaluate_all(stats)
    assert len(results) == 2
    assert all(not r.is_anomaly for r in results)


def test_detector_reset():
    det = AnomalyDetector("m1")
    for _ in range(10):
        det.evaluate(0, "Step 1", 3.0)
    assert len(det.baselines) == 1
    det.reset()
    assert len(det.baselines) == 0
