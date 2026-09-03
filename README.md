# Model-Reproducibility Registry for E-Commerce Recommendations

> **A production-grade model-reproducibility registry and point-in-time feature store linking datasets, features, code commits, model weights, approvals, and inference audit logs.**

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-1.0+-009688.svg)](https://fastapi.tiangolo.com/)
[![Tests](https://img.shields.io/badge/Tests-6%20Passed%20(100%25)-success.svg)]()
[![Reproducibility](https://img.shields.io/badge/Audit%20Reproducibility-100%25-brightgreen.svg)]()

---

## 📌 Project Overview
E-commerce enterprises run hundreds of concurrent recommendation experiments. When an anomalous prediction requires auditing, traditional MLOps systems cannot reconstruct the prediction because features have drifted and models have been overwritten.

This repository provides an end-to-end solution:
1. **Cryptographic Lineage**: Binds Dataset Snapshots (SHA-256), Git Commit SHAs, Model Weights (SHA-256), and Approval Sign-offs.
2. **Point-in-Time Feature Store**: Eliminates lookahead bias by retrieving features strictly as of historical inference timestamps.
3. **1-Click Audit Reconstruction**: Verifies bit-exact prediction reproducibility ($0.00000000$ delta) and exports audit certificates.
4. **Adversarial Stream Resilience**: Prevents state corruption under delayed, duplicate, and out-of-order event streams.

---

## 🚀 Quick Start (Windows)

### Option 1: One-Click Launch
Double-click `run.bat` in the project root folder.  
It will automatically launch the web dashboard at `http://localhost:8000`.

### Option 2: Command Line
```powershell
# 1. Initialize data & train initial model (if not already run)
python -m src.models.train

# 2. Start web application
python -m uvicorn src.api.app:app --host 0.0.0.0 --port 8000
```
Open **[http://localhost:8000](http://localhost:8000)** in your web browser.

---

## 🧪 Running Automated Tests
To run the complete test suite verifying reproducibility, adversarial fault-tolerance, and baseline comparisons:

```powershell
python -m pytest tests/ -v -s
```

### Expected Output:
```
tests/test_adversarial.py::test_duplicate_events_idempotent_deduplication PASSED
tests/test_adversarial.py::test_late_arriving_events_prevent_lookahead_bias PASSED
tests/test_adversarial.py::test_out_of_order_stream_does_not_corrupt_audit PASSED
tests/test_baseline_comparison.py::test_baseline_vs_registry_comparison PASSED
tests/test_reproducibility.py::test_historical_predictions_100_percent_reproducible PASSED
tests/test_reproducibility.py::test_model_artifact_sha256_integrity PASSED

============================== 6 passed in 1.16s ==============================
```

---

## 📊 Measured Benchmark Results

| Metric | Baseline (Ad-Hoc System) | Proposed Registry | Delta Gain |
| :--- | :---: | :---: | :---: |
| **Historical Prediction Reproducibility** | 20.0% | **100.0%** | **+80.0%** |
| **Maximum Score Delta** | $> 0.185$ | **0.00000000** | Bit-Exact |
| **Artifact SHA-256 Integrity** | Unverified | **100% Verified** | Tamper-proof |
| **State Corruption Under Stream Attacks** | Elevated | **0.0%** | Zero Poisoning |

---

## 📁 Repository Structure
```
├── data/                      # Local SQLite DB, datasets, and serialized model artifacts
│   ├── registry.db            # Relational SQLite metadata store
│   ├── products.json          # E-commerce candidate catalog
│   ├── datasets/              # Versioned training snapshots (CSV)
│   └── artifacts/             # Serialized model weights (.pkl)
├── src/
│   ├── registry/              # Database models, connection, and registry service
│   │   ├── models.py
│   │   ├── db.py
│   │   └── registry_service.py
│   ├── feature_store/         # Point-in-time time-travel engine & event ingestion
│   │   ├── point_in_time.py
│   │   └── event_ingestion.py
│   ├── models/                # Recommendation model architecture & training pipeline
│   │   ├── recommender.py
│   │   └── train.py
│   ├── audit/                 # 1-Click audit reconstruction service & certificate generator
│   │   └── audit_service.py
│   ├── api/                   # FastAPI server & REST API
│   │   └── app.py
│   └── ui/                    # Dark-mode glassmorphic web dashboard
│       ├── index.html
│       ├── styles.css
│       └── app.js
├── tests/                     # Verification test suite
│   ├── test_reproducibility.py
│   ├── test_adversarial.py
│   └── test_baseline_comparison.py
├── Review_1_Report.md         # Formatted 35% milestone submission report for Qbee
├── Viva_Preparation_Guide.md  # Comprehensive viva and defense questions & answers
├── run.bat                    # Windows 1-click batch launcher
└── run.ps1                    # PowerShell launcher
```

---

## 🎓 College Submission & Review 1
* The ready-to-submit milestone report is in [Review_1_Report.md](file:///e:/cse%20project/New%20folder%20(3)/Review_1_Report.md).
* For faculty defense and demo guidance, refer to [Viva_Preparation_Guide.md](file:///e:/cse%20project/New%20folder%20(3)/Viva_Preparation_Guide.md).
