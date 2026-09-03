# Viva & Project Defense Guide: Model-Reproducibility Registry

Use this guide to prepare for your viva, review panel, and professor questions.

---

### 1. 30-Second Elevator Pitch
> *"In e-commerce companies running hundreds of recommendation experiments, auditing an old prediction is virtually impossible because features drift, datasets change, and models get overwritten. Our project introduces a Model-Reproducibility Registry linked to a Point-in-Time Feature Store. We prove with cryptographic SHA-256 hashing and time-travel querying that 100% of historical predictions can be reproduced bit-for-bit, even when data streams suffer from delayed, duplicated, or out-of-order events."*

---

### 2. Frequently Asked Questions by Professors

#### Q1: "Why can't traditional ML systems reproduce past predictions?"
* **Answer**: In traditional systems, model weights are saved without immutable commit hashes, and feature tables are continually updated. When an auditor re-runs a model 3 weeks later, they query *today's* user features instead of the user's features at the exact millisecond of the recommendation. This causes **lookahead bias** and score divergence (our tests show baseline systems fail up to 80% of the time).

#### Q2: "What is Point-in-Time Feature Extraction?"
* **Answer**: It is a time-travel querying mechanism. When auditing an inference from `2026-08-20 14:30:15`, the feature store executes queries strictly where `event_timestamp <= 2026-08-20 14:30:15`. Any purchases, clicks, or profile changes that occurred after that timestamp are excluded, ensuring zero data leakage.

#### Q3: "How does your system handle duplicate and delayed events (Adversarial test)?"
* **Answer**:
  * **Duplicates**: The ingestion engine generates an idempotent SHA-256 fingerprint from `(entity_id, event_type, value, timestamp)`. If a duplicate network packet arrives, it is safely intercepted without throwing errors or corrupting aggregate features.
  * **Delayed / Out-of-Order**: Events carry their original occurrence timestamp. Even if an event arrives days late, the feature store places it in its correct historical chronological position.

#### Q4: "How is governance and approval tracked?"
* **Answer**: The registry contains explicit `approval_records` and `deployment_records`. A model cannot serve live traffic or be considered production-ready without a recorded sign-off from an authorized auditor (e.g., Head of AI / Compliance).

#### Q5: "What are your measured experimental results?"
* **Answer**:
  * Baseline (Unversioned/Drifted system): **20.0%** audit reproducibility.
  * Our Registry System: **100.0%** bit-exact reproducibility ($0.00000000$ max score delta).
  * Adversarial stream corruption: **0.0%**.

---

### 3. Step-by-Step Live Demo Plan for Professors (2 Minutes)

1. **Step 1: Start the Application**:
   * Double click `run.bat` (or run `python -m uvicorn src.api.app:app --host 0.0.0.0 --port 8000`).
   * The dashboard opens at `http://localhost:8000`.

2. **Step 2: Show Live Recommendation & Audit Logging**:
   * On Tab 1 ("Live E-Commerce Store"), select a customer (e.g. `usr_102`).
   * Point out the **Point-in-Time Features** (Engagement score, preferred category, past purchases).
   * Click **"Generate Personalized Recommendations"**.
   * Show that an immutable `inference_id` was created, capturing the exact active model artifact SHA-256.

3. **Step 3: Demonstrate 1-Click Audit & Lineage**:
   * Click **"Audit & Verify This Prediction Now"** (or switch to Tab 2).
   * Click **"Reproduce & Audit"**.
   * Show the panel:
     * Green badge: **"AUDIT PASSED: 100.0% Bit-Exact Reproducibility"**.
     * **Lineage Trail**: Shows Dataset Version (SHA-256), Git Commit SHA, Model Artifact SHA-256, and Formal Approval.
     * **Scoring Table**: Original vs Reconstructed scores side-by-side with Delta = `0.0`.
     * Click **"Export Audit Certificate"** to download the JSON report.

4. **Step 4: Demonstrate Adversarial Stream Resilience**:
   * Switch to Tab 3 ("Adversarial Chaos Engine").
   * Select **"Mixed Adversarial Assault"** and click **"Inject Adversarial Events"**.
   * Show the resilience metrics: Duplicates safely intercepted, state corruption rate = **0.0%**.

5. **Step 5: Show Automated Test Suite**:
   * Open the terminal and run:
     ```bash
     python -m pytest tests/ -v -s
     ```
   * Show that all 6 tests pass with 100% success.
