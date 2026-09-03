"""
Adversarial & Fault-Tolerance Test Suite.
Verifies system behavior under:
1. Duplicate event injection (Idempotency)
2. Late/delayed events (Lookahead bias prevention)
3. Out-of-order event streams (Deterministic ordering)
"""

from datetime import datetime, timedelta
import uuid
import pytest
from src.registry.db import SessionLocal
from src.registry.models import FeatureStoreEvent, InferenceAuditLog
from src.feature_store.event_ingestion import EventIngestionEngine
from src.feature_store.point_in_time import PointInTimeFeatureStore
from src.audit.audit_service import AuditService
from src.api.app import load_products


def test_duplicate_events_idempotent_deduplication():
    """
    Scenario 1: Inject exact duplicate events.
    Verifies that duplicates are rejected, no duplicate key errors crash the system,
    and state remains intact.
    """
    db = SessionLocal()
    ingestion = EventIngestionEngine(db)

    uid = f"usr_dedup_{uuid.uuid4().hex[:6]}"
    ts = datetime.utcnow() - timedelta(days=1)
    ev = {
        "entity_id": uid,
        "entity_type": "user",
        "event_type": "purchase",
        "value": 150.0,
        "event_timestamp": ts,
        "item_category": "electronics"
    }

    # First insertion
    ok1, status1 = ingestion.ingest_event(**ev)
    assert ok1 is True
    assert status1 == "inserted"

    # Replayed identical event
    ok2, status2 = ingestion.ingest_event(**ev)
    assert ok2 is False
    assert status2 == "duplicate_skipped"

    # Replayed third time
    ok3, status3 = ingestion.ingest_event(**ev)
    assert ok3 is False
    assert status3 == "duplicate_skipped"

    # Verify only 1 record exists in DB
    cnt = db.query(FeatureStoreEvent).filter_by(entity_id=uid).count()
    assert cnt == 1, f"Expected 1 record, found {cnt}"
    db.close()


def test_late_arriving_events_prevent_lookahead_bias():
    """
    Scenario 2: Inject delayed/late-arriving events.
    Verifies that events timestamped AFTER an inference event DO NOT alter
    the point-in-time features computed for that inference.
    """
    db = SessionLocal()
    feature_store = PointInTimeFeatureStore(db)
    ingestion = EventIngestionEngine(db)

    inference_time = datetime.utcnow() - timedelta(days=5)
    user_id = f"usr_bias_{uuid.uuid4().hex[:6]}"

    # Pre-inference event
    ingestion.ingest_event(
        entity_id=user_id,
        entity_type="user",
        event_type="view",
        value=1.0,
        event_timestamp=inference_time - timedelta(hours=2),
        item_category="electronics"
    )

    # Features as-of inference time
    feats_before = feature_store.get_user_features(user_id, inference_time)
    assert feats_before["view_count"] == 1
    assert feats_before["purchase_count"] == 0

    # Late-arriving event occurring AFTER inference time (e.g., 2 days later)
    ingestion.ingest_event(
        entity_id=user_id,
        entity_type="user",
        event_type="purchase",
        value=300.0,
        event_timestamp=inference_time + timedelta(days=2),
        item_category="electronics"
    )

    # Re-query features as-of original inference time
    feats_after = feature_store.get_user_features(user_id, inference_time)
    # The subsequent purchase must NOT leak into the historical inference snapshot!
    assert feats_after["view_count"] == 1
    assert feats_after["purchase_count"] == 0
    assert feats_after["total_spend"] == 0.0

    db.close()


def test_out_of_order_stream_does_not_corrupt_audit():
    """
    Scenario 3: Out-of-order event stream.
    Validates that existing historical inference audits still pass 100%
    even after out-of-order historical events are backfilled.
    """
    db = SessionLocal()
    products = load_products()
    auditor = AuditService(db, products)
    ingestion = EventIngestionEngine(db)

    # Pick an existing audited inference
    sample_inf = db.query(InferenceAuditLog).first()
    assert sample_inf is not None

    # Before out-of-order injection
    report_before = auditor.reproduce_inference(sample_inf.inference_id)
    assert report_before["is_reproducible"] is True

    # Inject scrambled events for other entities
    now = datetime.utcnow()
    scrambled = [
        {"entity_id": "usr_scramble", "entity_type": "user", "event_type": "click", "value": 1.0, "event_timestamp": now - timedelta(hours=3)},
        {"entity_id": "usr_scramble", "entity_type": "user", "event_type": "click", "value": 1.0, "event_timestamp": now - timedelta(hours=10)},
        {"entity_id": "usr_scramble", "entity_type": "user", "event_type": "click", "value": 1.0, "event_timestamp": now - timedelta(hours=1)},
    ]
    stats = ingestion.ingest_batch(scrambled)
    assert stats["inserted"] == 3

    # Audit historical inference again - must remain 100% reproducible
    report_after = auditor.reproduce_inference(sample_inf.inference_id)
    assert report_after["is_reproducible"] is True
    assert report_after["max_score_delta"] < 1e-4

    db.close()
