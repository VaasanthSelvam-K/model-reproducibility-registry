"""
Statistical Drift & Data Shift Detection Engine (Review 2 Milestone).
Provides:
1. Population Stability Index (PSI) calculation for continuous & categorical features.
2. Two-sample Kolmogorov-Smirnov (KS) Test for cumulative distribution divergence.
3. Wasserstein Distance (Earth Mover's Distance) for metric feature shift quantification.
4. Automated Drift Health Status & Alerting for MLOps Governance.
"""

import numpy as np
from typing import Dict, List, Any, Tuple
from scipy import stats


class StatisticalDriftDetector:
    """
    Evaluates statistical divergence between a reference baseline feature distribution
    and a live/current inference feature distribution.
    """

    def __init__(self, epsilon: float = 1e-6):
        self.epsilon = epsilon

    def calculate_psi(self, baseline: np.ndarray, current: np.ndarray, num_bins: int = 10) -> Dict[str, Any]:
        """
        Computes Population Stability Index (PSI).
        PSI < 0.10: No significant drift (Stable)
        0.10 <= PSI < 0.25: Moderate drift (Warning / Monitor)
        PSI >= 0.25: Significant distribution shift (Action Required / Retrain Alert)
        """
        baseline = np.asarray(baseline, dtype=float)
        current = np.asarray(current, dtype=float)

        if len(baseline) == 0 or len(current) == 0:
            return {"psi": 0.0, "status": "STABLE", "details": "Empty dataset"}

        # Define bin boundaries using baseline quantiles
        quantiles = np.linspace(0, 100, num_bins + 1)
        bin_edges = np.percentile(baseline, quantiles)
        bin_edges[0] -= 1e-5
        bin_edges[-1] += 1e-5

        # Compute histograms
        b_counts, _ = np.histogram(baseline, bins=bin_edges)
        c_counts, _ = np.histogram(current, bins=bin_edges)

        # Convert to proportions with smoothing epsilon
        b_prop = (b_counts + self.epsilon) / (len(baseline) + self.epsilon * num_bins)
        c_prop = (c_counts + self.epsilon) / (len(current) + self.epsilon * num_bins)

        # Calculate PSI sum: (Actual - Expected) * ln(Actual / Expected)
        psi_contributions = (c_prop - b_prop) * np.log(c_prop / b_prop)
        psi_value = float(np.sum(psi_contributions))

        if psi_value < 0.10:
            status = "STABLE"
            severity = "GREEN"
        elif psi_value < 0.25:
            status = "MODERATE_DRIFT"
            severity = "YELLOW"
        else:
            status = "SIGNIFICANT_DRIFT"
            severity = "RED"

        return {
            "psi": round(psi_value, 6),
            "status": status,
            "severity": severity,
            "num_bins": num_bins,
            "sample_sizes": {"baseline": len(baseline), "current": len(current)}
        }

    def calculate_ks_test(self, baseline: np.ndarray, current: np.ndarray) -> Dict[str, Any]:
        """
        Executes two-sample Kolmogorov-Smirnov test.
        """
        baseline = np.asarray(baseline, dtype=float)
        current = np.asarray(current, dtype=float)

        ks_stat, p_value = stats.ks_2samp(baseline, current)
        is_drift_detected = bool(p_value < 0.05)

        return {
            "ks_statistic": round(float(ks_stat), 6),
            "p_value": round(float(p_value), 6),
            "alpha_threshold": 0.05,
            "drift_detected": is_drift_detected,
            "status": "DRIFT_DETECTED" if is_drift_detected else "STABLE"
        }

    def calculate_wasserstein_distance(self, baseline: np.ndarray, current: np.ndarray) -> float:
        """
        Computes Wasserstein Distance (Earth Mover's Distance).
        """
        baseline = np.asarray(baseline, dtype=float)
        current = np.asarray(current, dtype=float)
        return round(float(stats.wasserstein_distance(baseline, current)), 6)

    def analyze_feature_drift(self, baseline: np.ndarray, current: np.ndarray, feature_name: str) -> Dict[str, Any]:
        """
        Runs complete statistical battery across PSI, KS-test, and Wasserstein distance.
        """
        psi_res = self.calculate_psi(baseline, current)
        ks_res = self.calculate_ks_test(baseline, current)
        w_dist = self.calculate_wasserstein_distance(baseline, current)

        overall_status = "ALERT" if psi_res["status"] == "SIGNIFICANT_DRIFT" or ks_res["drift_detected"] else (
            "WARNING" if psi_res["status"] == "MODERATE_DRIFT" else "HEALTHY"
        )

        return {
            "feature_name": feature_name,
            "overall_status": overall_status,
            "psi_analysis": psi_res,
            "ks_test": ks_res,
            "wasserstein_distance": w_dist,
            "baseline_summary": {
                "mean": round(float(np.mean(baseline)), 4),
                "std": round(float(np.std(baseline)), 4),
                "count": len(baseline)
            },
            "current_summary": {
                "mean": round(float(np.mean(current)), 4),
                "std": round(float(np.std(current)), 4),
                "count": len(current)
            }
        }
