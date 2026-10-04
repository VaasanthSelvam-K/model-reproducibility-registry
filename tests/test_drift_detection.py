"""
Statistical Drift Detection Test Suite (Review 2).
Validates Population Stability Index (PSI), Kolmogorov-Smirnov (KS) test,
and Wasserstein Distance calculations across stationary vs drifted distributions.
"""

import numpy as np
import pytest
from src.feature_store.drift_detector import StatisticalDriftDetector


def test_stationary_distribution_yields_stable_status():
    """Validates that stationary baseline and current feature samples trigger STABLE/GREEN status."""
    np.random.seed(42)
    baseline = np.random.normal(loc=0.5, scale=0.15, size=500)
    current = np.random.normal(loc=0.5, scale=0.15, size=500)

    detector = StatisticalDriftDetector()
    report = detector.analyze_feature_drift(baseline, current, feature_name="user_engagement_score")

    assert report["overall_status"] == "HEALTHY"
    assert report["psi_analysis"]["status"] == "STABLE"
    assert report["psi_analysis"]["psi"] < 0.10
    assert report["ks_test"]["drift_detected"] is False


def test_shifted_distribution_triggers_significant_drift_alert():
    """Validates that severe distribution shifts trigger SIGNIFICANT_DRIFT alert and red flag."""
    np.random.seed(42)
    baseline = np.random.normal(loc=0.30, scale=0.10, size=500)
    current = np.random.normal(loc=0.75, scale=0.15, size=500)  # Severe mean shift

    detector = StatisticalDriftDetector()
    report = detector.analyze_feature_drift(baseline, current, feature_name="item_popularity_score")

    assert report["overall_status"] == "ALERT"
    assert report["psi_analysis"]["status"] == "SIGNIFICANT_DRIFT"
    assert report["psi_analysis"]["psi"] > 0.25
    assert report["ks_test"]["drift_detected"] is True
    assert report["wasserstein_distance"] > 0.35
