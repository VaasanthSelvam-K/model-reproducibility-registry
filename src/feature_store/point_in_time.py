"""
Point-In-Time Feature Extraction Engine.
Guarantees exact historical state reconstruction without data leakage or lookahead bias.
"""

from datetime import datetime
from typing import Dict, Any, List
from collections import Counter
from sqlalchemy.orm import Session
from sqlalchemy import func

from src.registry.models import FeatureStoreEvent


class PointInTimeFeatureStore:
    def __init__(self, db: Session):
        self.db = db

    def get_user_features(self, user_id: str, as_of_time: datetime) -> Dict[str, Any]:
        """
        Compute user features strictly using events that occurred ON OR BEFORE as_of_time.
        Zero lookahead bias guaranteed.
        """
        events: List[FeatureStoreEvent] = (
            self.db.query(FeatureStoreEvent)
            .filter(
                FeatureStoreEvent.entity_id == user_id,
                FeatureStoreEvent.entity_type == "user",
                FeatureStoreEvent.event_timestamp <= as_of_time
            )
            .order_by(FeatureStoreEvent.event_timestamp.asc())
            .all()
        )

        if not events:
            return {
                "user_id": user_id,
                "as_of_time": as_of_time.isoformat(),
                "total_events": 0,
                "view_count": 0,
                "click_count": 0,
                "purchase_count": 0,
                "total_spend": 0.0,
                "preferred_category": "electronics",
                "engagement_score": 0.1
            }

        view_count = sum(1 for e in events if e.event_type == "view")
        click_count = sum(1 for e in events if e.event_type == "click")
        purchases = [e for e in events if e.event_type == "purchase"]
        purchase_count = len(purchases)
        total_spend = sum(e.value for e in purchases)

        categories = [e.item_category for e in events if e.item_category]
        preferred_category = Counter(categories).most_common(1)[0][0] if categories else "electronics"

        # Deterministic engagement score formula
        engagement_score = round(
            min(1.0, (view_count * 0.05 + click_count * 0.1 + purchase_count * 0.3)), 4
        )

        return {
            "user_id": user_id,
            "as_of_time": as_of_time.isoformat(),
            "total_events": len(events),
            "view_count": view_count,
            "click_count": click_count,
            "purchase_count": purchase_count,
            "total_spend": round(total_spend, 2),
            "preferred_category": preferred_category,
            "engagement_score": engagement_score
        }

    def get_item_features(self, item_id: str, as_of_time: datetime) -> Dict[str, Any]:
        """
        Compute item features strictly using events that occurred ON OR BEFORE as_of_time.
        """
        events: List[FeatureStoreEvent] = (
            self.db.query(FeatureStoreEvent)
            .filter(
                FeatureStoreEvent.entity_id == item_id,
                FeatureStoreEvent.entity_type == "item",
                FeatureStoreEvent.event_timestamp <= as_of_time
            )
            .all()
        )

        if not events:
            return {
                "item_id": item_id,
                "as_of_time": as_of_time.isoformat(),
                "item_views": 1,
                "item_purchases": 0,
                "conversion_rate": 0.0,
                "popularity_score": 0.1
            }

        views = sum(1 for e in events if e.event_type == "view")
        purchases = sum(1 for e in events if e.event_type == "purchase")
        conv_rate = round(purchases / max(1, views), 4)
        popularity = round(min(1.0, (views * 0.02 + purchases * 0.15)), 4)

        return {
            "item_id": item_id,
            "as_of_time": as_of_time.isoformat(),
            "item_views": views,
            "item_purchases": purchases,
            "conversion_rate": conv_rate,
            "popularity_score": popularity
        }

    def get_inference_features(
        self, user_id: str, item_ids: List[str], as_of_time: datetime
    ) -> Dict[str, Any]:
        """Combine user and item point-in-time features for recommendation scoring."""
        user_feats = self.get_user_features(user_id, as_of_time)
        item_feats = {item_id: self.get_item_features(item_id, as_of_time) for item_id in item_ids}
        return {
            "user": user_feats,
            "items": item_feats,
            "as_of_time": as_of_time.isoformat()
        }
