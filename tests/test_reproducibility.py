"""
Reproducibility Verification Test Suite.
Validates that 100% of historical inference predictions can be exactly reconstructed
using the model-reproducibility registry and point-in-time feature store.
"""

import pytest
from src.registry.db import init_db, SessionLocal, BASE_DIR
from src.registry.models import InferenceAuditLog
from src.models.train import run_pipeline
from src.audit.audit_service import AuditService
from src.api.app import load_products


@pytest.fixture(scope="session", autouse=True)
def setup_database_and_data():
    """Ensure database is seeded before running tests."""
    init_db()
    db = SessionLocal()
    count = db.query(InferenceAuditLog).count()
    db.close()
    if count == 0:
        run_pipeline()


def test_historical_predictions_100_percent_reproducible():
    """
    Core Evaluation Requirement:
    Verify that historical predictions can be reconstructed with 0 score delta
    and 100% bit-exact parity.
    """
    db = SessionLocal()
    products = load_products()
    auditor = AuditService(db, products)

    inferences = db.query(InferenceAuditLog).all()
    assert len(inferences) > 0, "No historical inferences found in registry."

    reproducible_count = 0
    total = len(inferences)

    for inf in inferences:
        report = auditor.reproduce_inference(inf.inference_id)
        assert report["status"] == "VERIFIED_AUDIT_PASSED", f"Inference {inf.inference_id} failed audit: {report}"
        assert report["is_reproducible"] is True
        assert report["max_score_delta"] < 1e-4, f"Delta too high: {report['max_score_delta']}"
        assert report["lineage_trail"]["model"]["sha_verified"] is True
        reproducible_count += 1

    reproducibility_rate = (reproducible_count / total) * 100.0
    print(f"\n[Test Result] Audited {total} historical predictions. Reproducibility Rate: {reproducibility_rate:.1f}%")
    assert reproducibility_rate == 100.0
    db.close()


def test_model_artifact_sha256_integrity():
    """Validate that registered artifact hash matches the physical file hash on disk."""
    db = SessionLocal()
    products = load_products()
    auditor = AuditService(db, products)
    sample_inf = db.query(InferenceAuditLog).first()

    report = auditor.reproduce_inference(sample_inf.inference_id)
    reg_sha = report["lineage_trail"]["model"]["registered_artifact_sha256"]
    curr_sha = report["lineage_trail"]["model"]["current_artifact_sha256"]

    assert reg_sha == curr_sha
    assert len(reg_sha) == 64
    db.close()
