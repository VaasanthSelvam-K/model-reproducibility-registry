"""
Robust Event Ingestion Engine.
Handles normal streams as well as adversarial conditions:
- Late/delayed events
- Duplicated events (idempotent deduplication)
- Out-of-order arrivals
"""

import hashlib
from datetime import datetime
from typing import Dict, Any, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from src.registry.models import FeatureStoreEvent


class EventIngestionEngine:
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def generate_event_key(
        entity_id: str,
        entity_type: str,
        event_type: str,
        value: float,
        event_timestamp: datetime
    ) -> str:
        """Generate deterministic cryptographic SHA-256 event key for deduplication."""
        raw = f"{entity_id}|{entity_type}|{event_type}|{value:.4f}|{event_timestamp.isoformat()}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def ingest_event(
        self,
        entity_id: str,
        entity_type: str,
        event_type: str,
        value: float,
        event_timestamp: datetime,
        item_category: str = "general"
    ) -> Tuple[bool, str]:
        """
        Ingests a single event idempotently.
        Returns: (success: bool, status: 'inserted' | 'duplicate_skipped' | 'error')
        """
        event_key = self.generate_event_key(
            entity_id, entity_type, event_type, value, event_timestamp
        )

        existing = self.db.query(FeatureStoreEvent).filter_by(event_key=event_key).first()
        if existing:
            return False, "duplicate_skipped"

        event = FeatureStoreEvent(
            event_key=event_key,
            entity_id=entity_id,
            entity_type=entity_type,
            event_type=event_type,
            item_category=item_category,
            value=value,
            event_timestamp=event_timestamp,
            ingested_at=datetime.utcnow()
        )
        try:
            self.db.add(event)
            self.db.commit()
            return True, "inserted"
        except IntegrityError:
            self.db.rollback()
            return False, "duplicate_skipped"

    def ingest_batch(self, events: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Ingest a batch of events (supports out-of-order arrival).
        """
        stats = {
            "total_received": len(events),
            "inserted": 0,
            "duplicate_skipped": 0,
            "delayed_processed": 0
        }

        now = datetime.utcnow()
        for ev in events:
            # Check if delayed (event timestamp significantly in past compared to current time)
            is_delayed = (now - ev["event_timestamp"]).total_seconds() > 3600

            success, status = self.ingest_event(
                entity_id=ev["entity_id"],
                entity_type=ev.get("entity_type", "user"),
                event_type=ev["event_type"],
                value=ev.get("value", 1.0),
                event_timestamp=ev["event_timestamp"],
                item_category=ev.get("item_category", "general")
            )

            if status == "inserted":
                stats["inserted"] += 1
                if is_delayed:
                    stats["delayed_processed"] += 1
            elif status == "duplicate_skipped":
                stats["duplicate_skipped"] += 1

        return stats
