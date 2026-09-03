"""
Registry Database Models for Model-Reproducibility Registry
Links datasets, features, code commits, model artifacts, approvals, deployments, and inferences.
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    Boolean,
    Text,
    ForeignKey,
    Index
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class DatasetVersion(Base):
    """
    Cryptographic snapshot of a training/evaluation dataset.
    """
    __tablename__ = "dataset_versions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    dataset_name = Column(String(128), nullable=False, index=True)
    version_tag = Column(String(64), nullable=False, unique=True, index=True)
    sha256_hash = Column(String(64), nullable=False, unique=True)
    storage_path = Column(String(512), nullable=False)
    schema_json = Column(Text, nullable=False)
    record_count = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    models = relationship("ModelRecord", back_populates="training_dataset")


class FeatureDefinition(Base):
    """
    Versioned metadata for feature definitions.
    """
    __tablename__ = "feature_definitions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    feature_name = Column(String(128), nullable=False, index=True)
    entity_type = Column(String(64), nullable=False)  # 'user' or 'item'
    data_type = Column(String(32), nullable=False)
    description = Column(String(256), nullable=True)
    transformation_logic = Column(Text, nullable=False)
    version = Column(Integer, default=1, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class ModelRecord(Base):
    """
    Trained model metadata explicitly linked to dataset version, git commit, and artifact hash.
    """
    __tablename__ = "model_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    model_name = Column(String(128), nullable=False, index=True)
    version_tag = Column(String(64), nullable=False, unique=True, index=True)
    git_commit_sha = Column(String(40), nullable=False)
    git_branch = Column(String(64), default="main")
    hyperparameters_json = Column(Text, nullable=False)
    metrics_json = Column(Text, nullable=False)
    artifact_path = Column(String(512), nullable=False)
    artifact_sha256 = Column(String(64), nullable=False)
    training_dataset_id = Column(Integer, ForeignKey("dataset_versions.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    training_dataset = relationship("DatasetVersion", back_populates="models")
    approvals = relationship("ApprovalRecord", back_populates="model", cascade="all, delete-orphan")
    deployments = relationship("DeploymentRecord", back_populates="model", cascade="all, delete-orphan")
    inferences = relationship("InferenceAuditLog", back_populates="model")


class ApprovalRecord(Base):
    """
    Formal sign-off/approval gates for model promotion.
    """
    __tablename__ = "approval_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    model_id = Column(Integer, ForeignKey("model_records.id"), nullable=False, index=True)
    approver = Column(String(128), nullable=False)
    status = Column(String(32), nullable=False)  # 'APPROVED', 'REJECTED', 'PENDING'
    comments = Column(Text, nullable=True)
    decided_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    model = relationship("ModelRecord", back_populates="approvals")


class DeploymentRecord(Base):
    """
    Production/Staging deployment records.
    """
    __tablename__ = "deployment_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    model_id = Column(Integer, ForeignKey("model_records.id"), nullable=False, index=True)
    environment = Column(String(64), default="production", nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    deployed_by = Column(String(128), default="automated_pipeline", nullable=False)
    deployed_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    model = relationship("ModelRecord", back_populates="deployments")
    inferences = relationship("InferenceAuditLog", back_populates="deployment")


class InferenceAuditLog(Base):
    """
    Immutable audit log capturing exact inputs, features, weights, and prediction scores.
    """
    __tablename__ = "inference_audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    inference_id = Column(String(64), unique=True, nullable=False, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    user_id = Column(String(64), nullable=False, index=True)
    candidate_items_json = Column(Text, nullable=False)
    features_snapshot_json = Column(Text, nullable=False)
    model_id = Column(Integer, ForeignKey("model_records.id"), nullable=False)
    deployment_id = Column(Integer, ForeignKey("deployment_records.id"), nullable=False)
    raw_scores_json = Column(Text, nullable=False)
    recommendations_json = Column(Text, nullable=False)

    model = relationship("ModelRecord", back_populates="inferences")
    deployment = relationship("DeploymentRecord", back_populates="inferences")


class FeatureStoreEvent(Base):
    """
    Idempotent event table for point-in-time feature extraction and adversarial handling.
    """
    __tablename__ = "feature_store_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_key = Column(String(64), unique=True, nullable=False, index=True)  # SHA-256 for deduplication
    entity_id = Column(String(64), nullable=False, index=True)
    entity_type = Column(String(32), nullable=False)  # 'user' or 'item'
    event_type = Column(String(64), nullable=False)  # 'view', 'click', 'purchase', 'add_to_cart'
    item_category = Column(String(64), default="general")
    value = Column(Float, default=1.0, nullable=False)
    event_timestamp = Column(DateTime, nullable=False, index=True)
    ingested_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("idx_entity_event_time", "entity_id", "event_timestamp"),
    )
