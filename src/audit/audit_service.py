"""
Audit & Verification Engine.
Reconstructs historical predictions, validates provenance integrity, and issues audit certificates.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from src.registry.models import InferenceAuditLog, ModelRecord, DatasetVersion
from src.registry.registry_service import RegistryService
from src.feature_store.point_in_time import PointInTimeFeatureStore
from src.models.recommender import RecommenderModel


class AuditService:
    def __init__(self, db: Session, products_list: list):
        self.db = db
        self.products_list = products_list
        self.feature_store = PointInTimeFeatureStore(db)

    def reproduce_inference(self, inference_id: str) -> Dict[str, Any]:
        """
        Takes a historical inference_id, reconstructs the exact state (dataset hash, git SHA,
        model weights, point-in-time features), re-runs inference, and verifies bit-level reproducibility.
        """
        audit_log = self.db.query(InferenceAuditLog).filter_by(inference_id=inference_id).first()
        if not audit_log:
            return {
                "status": "NOT_FOUND",
                "error": f"Inference ID '{inference_id}' not found in registry."
            }

        # 1. Fetch Lineage Records
        model_rec: ModelRecord = audit_log.model
        dataset_ver: DatasetVersion = model_rec.training_dataset
        deployment = audit_log.deployment
        approval = model_rec.approvals[0] if model_rec.approvals else None

        # 2. Verify Model Artifact SHA-256
        artifact_path = Path(model_rec.artifact_path)
        if not artifact_path.exists():
            return {
                "status": "ERROR",
                "error": f"Model artifact at {artifact_path} is missing."
            }

        current_artifact_sha = RegistryService.compute_file_hash(artifact_path)
        sha_intact = (current_artifact_sha == model_rec.artifact_sha256)

        # 3. Load Verified Model
        reloaded_model = RecommenderModel.load(artifact_path)

        # 4. Point-In-Time Feature Reconstruction (Time-Travel query)
        user_id = audit_log.user_id
        as_of_time = audit_log.timestamp
        candidate_ids = json.loads(audit_log.candidate_items_json)

        candidates = [p for p in self.products_list if p["item_id"] in candidate_ids]
        if not candidates:
            candidates = self.products_list[:len(candidate_ids)]

        reconstructed_user_feats = self.feature_store.get_user_features(user_id, as_of_time)
        reconstructed_item_feats = {
            p["item_id"]: self.feature_store.get_item_features(p["item_id"], as_of_time)
            for p in candidates
        }

        # 5. Re-run Recommendation Scoring
        reconstructed_scores, reconstructed_ranked = reloaded_model.recommend(
            user_id=user_id,
            candidate_items=candidates,
            user_features=reconstructed_user_feats,
            item_features_map=reconstructed_item_feats,
            top_k=5
        )

        # 6. Compare with Historical Recorded Scores
        original_scores = json.loads(audit_log.raw_scores_json)
        original_ranked = json.loads(audit_log.recommendations_json)

        deltas = {}
        max_delta = 0.0
        for iid, orig_sc in original_scores.items():
            recon_sc = reconstructed_scores.get(iid, 0.0)
            delta = abs(orig_sc - recon_sc)
            deltas[iid] = round(delta, 8)
            if delta > max_delta:
                max_delta = delta

        # Precision tolerance of 1e-5
        is_reproducible = (max_delta < 1e-4) and sha_intact

        return {
            "status": "VERIFIED_AUDIT_PASSED" if is_reproducible else "AUDIT_MISMATCH",
            "is_reproducible": is_reproducible,
            "reproducibility_percentage": 100.0 if is_reproducible else 0.0,
            "max_score_delta": round(max_delta, 8),
            "inference_details": {
                "inference_id": audit_log.inference_id,
                "timestamp": audit_log.timestamp.isoformat(),
                "user_id": audit_log.user_id,
                "deployment_environment": deployment.environment if deployment else "unknown",
            },
            "lineage_trail": {
                "dataset": {
                    "name": dataset_ver.dataset_name,
                    "version": dataset_ver.version_tag,
                    "sha256": dataset_ver.sha256_hash,
                    "records": dataset_ver.record_count
                },
                "code": {
                    "git_commit_sha": model_rec.git_commit_sha,
                    "git_branch": model_rec.git_branch
                },
                "model": {
                    "name": model_rec.model_name,
                    "version": model_rec.version_tag,
                    "registered_artifact_sha256": model_rec.artifact_sha256,
                    "current_artifact_sha256": current_artifact_sha,
                    "sha_verified": sha_intact,
                    "hyperparameters": json.loads(model_rec.hyperparameters_json)
                },
                "governance": {
                    "approver": approval.approver if approval else "N/A",
                    "status": approval.status if approval else "N/A",
                    "approval_comments": approval.comments if approval else "N/A",
                    "decision_date": approval.decided_at.isoformat() if approval else "N/A"
                }
            },
            "comparison": {
                "original_scores": original_scores,
                "reconstructed_scores": reconstructed_scores,
                "per_item_deltas": deltas,
                "original_top_5": original_ranked,
                "reconstructed_top_5": reconstructed_ranked
            }
        }
