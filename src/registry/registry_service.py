"""
Registry Service for managing artifacts, provenance, and audit logs.
"""

import hashlib
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from src.registry.models import (
    DatasetVersion,
    FeatureDefinition,
    ModelRecord,
    ApprovalRecord,
    DeploymentRecord,
    InferenceAuditLog
)


class RegistryService:
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def compute_file_hash(file_path: Path) -> str:
        """Compute SHA-256 hash of a file."""
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()

    @staticmethod
    def compute_dict_hash(data: Dict[str, Any]) -> str:
        """Compute SHA-256 hash of a dictionary (deterministic json)."""
        dumped = json.dumps(data, sort_keys=True)
        return hashlib.sha256(dumped.encode("utf-8")).hexdigest()

    def register_dataset(
        self,
        name: str,
        version_tag: str,
        file_path: Path,
        schema: Dict[str, str],
        record_count: int
    ) -> DatasetVersion:
        """Register a dataset version snapshot with its SHA-256 hash."""
        sha256 = self.compute_file_hash(file_path)

        existing = self.db.query(DatasetVersion).filter(
            (DatasetVersion.version_tag == version_tag) | (DatasetVersion.sha256_hash == sha256)
        ).first()
        if existing:
            return existing

        dataset = DatasetVersion(
            dataset_name=name,
            version_tag=version_tag,
            sha256_hash=sha256,
            storage_path=str(file_path),
            schema_json=json.dumps(schema),
            record_count=record_count,
            created_at=datetime.utcnow()
        )
        self.db.add(dataset)
        self.db.commit()
        self.db.refresh(dataset)
        return dataset

    def register_feature_definition(
        self,
        feature_name: str,
        entity_type: str,
        data_type: str,
        transformation_logic: str,
        description: str = "",
        version: int = 1
    ) -> FeatureDefinition:
        """Register or update a feature definition."""
        existing = self.db.query(FeatureDefinition).filter_by(
            feature_name=feature_name, version=version
        ).first()
        if existing:
            return existing

        feature_def = FeatureDefinition(
            feature_name=feature_name,
            entity_type=entity_type,
            data_type=data_type,
            description=description,
            transformation_logic=transformation_logic,
            version=version,
            created_at=datetime.utcnow()
        )
        self.db.add(feature_def)
        self.db.commit()
        self.db.refresh(feature_def)
        return feature_def

    def register_model(
        self,
        model_name: str,
        version_tag: str,
        git_commit_sha: str,
        hyperparameters: Dict[str, Any],
        metrics: Dict[str, Any],
        artifact_path: Path,
        training_dataset_id: int,
        git_branch: str = "main"
    ) -> ModelRecord:
        """Register a trained model linked to code commit, hyperparams, dataset snapshot and artifact hash."""
        artifact_sha256 = self.compute_file_hash(artifact_path)

        model = ModelRecord(
            model_name=model_name,
            version_tag=version_tag,
            git_commit_sha=git_commit_sha,
            git_branch=git_branch,
            hyperparameters_json=json.dumps(hyperparameters),
            metrics_json=json.dumps(metrics),
            artifact_path=str(artifact_path),
            artifact_sha256=artifact_sha256,
            training_dataset_id=training_dataset_id,
            created_at=datetime.utcnow()
        )
        self.db.add(model)
        self.db.commit()
        self.db.refresh(model)
        return model

    def record_approval(
        self,
        model_id: int,
        approver: str,
        status: str = "APPROVED",
        comments: str = "Model passed automated validation gates"
    ) -> ApprovalRecord:
        """Formal sign-off/approval gate record."""
        approval = ApprovalRecord(
            model_id=model_id,
            approver=approver,
            status=status,
            comments=comments,
            decided_at=datetime.utcnow()
        )
        self.db.add(approval)
        self.db.commit()
        self.db.refresh(approval)
        return approval

    def deploy_model(
        self,
        model_id: int,
        environment: str = "production",
        deployed_by: str = "mlops_orchestrator"
    ) -> DeploymentRecord:
        """Deploy model to an environment, setting previous deployments to inactive."""
        # Deactivate existing active deployments in this environment
        self.db.query(DeploymentRecord).filter_by(
            environment=environment, is_active=True
        ).update({"is_active": False})

        deployment = DeploymentRecord(
            model_id=model_id,
            environment=environment,
            is_active=True,
            deployed_by=deployed_by,
            deployed_at=datetime.utcnow()
        )
        self.db.add(deployment)
        self.db.commit()
        self.db.refresh(deployment)
        return deployment

    def log_inference(
        self,
        user_id: str,
        candidate_items: List[str],
        features_snapshot: Dict[str, Any],
        model_id: int,
        deployment_id: int,
        raw_scores: Dict[str, float],
        recommendations: List[Dict[str, Any]],
        inference_id: Optional[str] = None,
        timestamp: Optional[datetime] = None
    ) -> InferenceAuditLog:
        """Log immutable audit record for an inference request."""
        inf_id = inference_id or f"inf_{uuid.uuid4().hex[:12]}"
        ts = timestamp or datetime.utcnow()

        audit_log = InferenceAuditLog(
            inference_id=inf_id,
            timestamp=ts,
            user_id=user_id,
            candidate_items_json=json.dumps(candidate_items),
            features_snapshot_json=json.dumps(features_snapshot),
            model_id=model_id,
            deployment_id=deployment_id,
            raw_scores_json=json.dumps(raw_scores),
            recommendations_json=json.dumps(recommendations)
        )
        self.db.add(audit_log)
        self.db.commit()
        self.db.refresh(audit_log)
        return audit_log

    def get_active_deployment(self, environment: str = "production") -> Optional[DeploymentRecord]:
        """Get the currently active deployment."""
        return self.db.query(DeploymentRecord).filter_by(
            environment=environment, is_active=True
        ).first()

    def get_lineage(self, model_id: int) -> Dict[str, Any]:
        """Retrieve the complete provenance lineage DAG for a model."""
        model = self.db.query(ModelRecord).filter_by(id=model_id).first()
        if not model:
            return {}

        dataset = model.training_dataset
        approvals = [
            {"approver": a.approver, "status": a.status, "date": a.decided_at.isoformat()}
            for a in model.approvals
        ]
        deployments = [
            {"env": d.environment, "active": d.is_active, "date": d.deployed_at.isoformat()}
            for d in model.deployments
        ]

        return {
            "model": {
                "id": model.id,
                "name": model.model_name,
                "version": model.version_tag,
                "git_commit": model.git_commit_sha,
                "artifact_sha256": model.artifact_sha256,
                "hyperparameters": json.loads(model.hyperparameters_json),
                "metrics": json.loads(model.metrics_json),
            },
            "dataset": {
                "id": dataset.id,
                "name": dataset.dataset_name,
                "version": dataset.version_tag,
                "sha256": dataset.sha256_hash,
                "records": dataset.record_count,
            },
            "approvals": approvals,
            "deployments": deployments
        }
