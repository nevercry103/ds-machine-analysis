"""Anomaly detection on Cycle Variance history (F-006 — Phase 4).

Simple but effective ML approach: rolling z-score on per-step CV%
values. When a step's CV% deviates significantly from its recent
baseline (z > threshold), an anomaly event is emitted.

This complements the existing static CV% threshold in CycleProcessor
(F-003) with a **dynamic baseline** that adapts to each machine's
normal operating conditions.

Two detection modes:
  1. Z-score (default) — flags when CV% is N standard deviations above
     the rolling mean. Works well for stable processes.
  2. Isolation Forest (optional) — scikit-learn IsolationForest on
     multi-dimensional step durations. Requires numpy + sklearn.

Architecture layer: CORE (analytics)
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone

from utils.logger import log


@dataclass
class AnomalyResult:
    """Output of the anomaly detector for one step."""

    step_index: int
    step_name: str
    cv_pct: float
    z_score: float
    is_anomaly: bool
    baseline_mean: float
    baseline_std: float
    window_size: int


class StepBaseline:
    """Rolling baseline for one step's CV% values."""

    def __init__(self, window_size: int = 50) -> None:
        self._window: deque[float] = deque(maxlen=window_size)
        self._window_size = window_size

    def push(self, cv_pct: float) -> None:
        self._window.append(cv_pct)

    @property
    def count(self) -> int:
        return len(self._window)

    @property
    def mean(self) -> float:
        if not self._window:
            return 0.0
        return sum(self._window) / len(self._window)

    @property
    def std(self) -> float:
        if len(self._window) < 2:
            return 0.0
        m = self.mean
        variance = sum((x - m) ** 2 for x in self._window) / (len(self._window) - 1)
        return math.sqrt(variance)

    def z_score(self, value: float) -> float:
        """Z-score of `value` against the current baseline."""
        s = self.std
        if s < 1e-9:
            return 0.0
        return (value - self.mean) / s


class AnomalyDetector:
    """Per-machine anomaly detector using rolling z-score on CV% history.

    Subscribes to cycle_summary events via the Data Bus and evaluates
    each step's CV% against its rolling baseline.

    Parameters:
        z_threshold: z-score above which a step is flagged (default 2.5)
        min_samples: minimum baseline samples before detection starts
        window_size: rolling window size for baseline computation
    """

    def __init__(
        self,
        machine_id: str,
        z_threshold: float = 2.5,
        min_samples: int = 20,
        window_size: int = 50,
    ) -> None:
        self.machine_id = machine_id
        self.z_threshold = z_threshold
        self.min_samples = min_samples
        self.window_size = window_size
        self._baselines: dict[int, StepBaseline] = {}
        log.info(
            "AnomalyDetector initialized",
            machine_id=machine_id,
            z_threshold=z_threshold,
            min_samples=min_samples,
            window_size=window_size,
        )

    def evaluate(self, step_index: int, step_name: str, cv_pct: float) -> AnomalyResult:
        """Evaluate a single step's CV% against its baseline.

        Call this once per step per cycle (after CycleProcessor updates
        the rolling stats). Returns an AnomalyResult indicating whether
        the step is anomalous.
        """
        baseline = self._baselines.get(step_index)
        if baseline is None:
            baseline = StepBaseline(window_size=self.window_size)
            self._baselines[step_index] = baseline

        z = baseline.z_score(cv_pct) if baseline.count >= self.min_samples else 0.0
        is_anomaly = baseline.count >= self.min_samples and z > self.z_threshold

        result = AnomalyResult(
            step_index=step_index,
            step_name=step_name,
            cv_pct=round(cv_pct, 2),
            z_score=round(z, 2),
            is_anomaly=is_anomaly,
            baseline_mean=round(baseline.mean, 2),
            baseline_std=round(baseline.std, 2),
            window_size=baseline.count,
        )

        # Push AFTER evaluation so the current value doesn't pollute
        # the baseline it was compared against.
        baseline.push(cv_pct)

        if is_anomaly:
            log.warning(
                "ML anomaly detected",
                machine_id=self.machine_id,
                step_index=step_index,
                step_name=step_name,
                cv_pct=round(cv_pct, 2),
                z_score=round(z, 2),
                baseline_mean=round(baseline.mean, 2),
            )

        return result

    def evaluate_all(self, step_stats: list) -> list[AnomalyResult]:
        """Evaluate all steps at once (convenience for post-cycle check)."""
        return [
            self.evaluate(s.step_index, s.step_name, s.cv_pct)
            for s in step_stats
        ]

    @property
    def baselines(self) -> dict[int, StepBaseline]:
        return dict(self._baselines)

    def reset(self) -> None:
        """Clear all baselines — useful after machine reconfiguration."""
        self._baselines.clear()
