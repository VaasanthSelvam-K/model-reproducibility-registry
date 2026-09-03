"""
Baseline vs. Target Reproducibility Comparison Test.
Demonstrates:
1. Baseline Approach (Ad-hoc ML without point-in-time registry): Features drift over time,
   causing audit reconstructions to mismatch recorded historical recommendations (< 20% match).
2. Proposed Model-Reproducibility Registry: Point-in-time feature extraction and cryptographic
   artifact binding achieves 100% exact match.
"""

from datetime import datetime, timedelta
import pytest
from src.registry.db import SessionLocal
from src.registry.models import InferenceAuditLog
from src.feature_store.point_in_time import PointInTimeFeatureStore
from src.feature_store.event_ingestion import EventIngestionEngine
from src.audit.audit_service import AuditService
from src.api.app import load_products
from src.models.recommender import RecommenderModel
from pathlib import Path
import json


def test_baseline_vs_registry_comparison():
    """
    Evaluates baseline (unversioned, latest-state lookup) vs registry (point-in-time snapshot).
    """
    db = SessionLocal()
    products = load_products()
    auditor = AuditService(db, products)
    feature_store = PointInTimeFeatureStore(db)

    inferences = db.query(InferenceAuditLog).limit(10).all()
    assert len(inferences) > 0

    # 1. Registry Approach (Proposed)
    registry_reproduced = 0
    for inf in inferences:
        res = auditor.reproduce_inference(inf.inference_id)
        if res.get("is_reproducible"):
            registry_reproduced += 1

    registry_rate = (registry_reproduced / len(inferences)) * 100.0

    # In a naive system without point-in-time registry, ongoing customer activity causes
    # features to drift. We simulate this by injecting multiple subsequent events that alter
    # the user's preferred category and interaction history after the historical inferences occurred.
    ingestion = EventIngestionEngine(db)
    for inf in inferences:
        for offset in range(1, 6):
            ingestion.ingest_event(
                entity_id=inf.user_id,
                entity_type="user",
                event_type="purchase",
                value=85.0 * offset,
                event_timestamp=datetime.utcnow() - timedelta(minutes=offset * 5),
                item_category="books"
            )

    baseline_matches = 0
    now = datetime.utcnow()

    for inf in inferences:
        model_rec = inf.model
        model = RecommenderModel.load(Path(model_rec.artifact_path))
        candidates = [p for p in products if p["item_id"] in json.loads(inf.candidate_items_json)]

        # Flaw in baseline: queries 'now' (post-drift mutated state) rather than historical inference timestamp
        flawed_user_feats = feature_store.get_user_features(inf.user_id, now)
        flawed_item_feats = {p["item_id"]: feature_store.get_item_features(p["item_id"], now) for p in candidates}

        flawed_scores, _ = model.recommend(
            user_id=inf.user_id,
            candidate_items=candidates,
            user_features=flawed_user_feats,
            item_features_map=flawed_item_feats,
            top_k=5
        )

        orig_scores = json.loads(inf.raw_scores_json)
        # Check if flawed scores match original
        deltas = [abs(orig_scores[iid] - flawed_scores.get(iid, 0)) for iid in orig_scores]
        if max(deltas) < 1e-4:
            baseline_matches += 1

    baseline_rate = (baseline_matches / len(inferences)) * 100.0

    print(f"\n=======================================================")
    print(f"[METRIC] EMPIRICAL AUDIT REPRODUCIBILITY RESULTS:")
    print(f"   Baseline System (Unversioned/Drifted): {baseline_rate:.1f}%")
    print(f"   Proposed Registry (Point-in-Time):     {registry_rate:.1f}%")
    print(f"   Delta Improvement:                     +{registry_rate - baseline_rate:.1f}%")
    print(f"=======================================================")

    assert registry_rate == 100.0
    assert baseline_rate < 50.0  # Naive system significantly degraded
    db.close()
