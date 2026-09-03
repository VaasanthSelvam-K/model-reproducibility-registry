"""
Deterministic E-Commerce Recommendation Model.
Ensures reproducible scoring given identical feature snapshots and model parameters.
"""

import pickle
import hashlib
from pathlib import Path
from typing import Dict, Any, List, Tuple
import numpy as np


class RecommenderModel:
    def __init__(
        self,
        n_factors: int = 16,
        regularization: float = 0.05,
        learning_rate: float = 0.01,
        random_seed: int = 42
    ):
        self.n_factors = n_factors
        self.regularization = regularization
        self.learning_rate = learning_rate
        self.random_seed = random_seed
        self.user_embeddings: Dict[str, np.ndarray] = {}
        self.item_embeddings: Dict[str, np.ndarray] = {}
        self.category_weights: Dict[str, float] = {
            "electronics": 1.25,
            "apparel": 1.10,
            "home": 1.05,
            "books": 1.00,
            "general": 1.00
        }
        self.bias = 0.5

    def fit(self, interactions: List[Dict[str, Any]]):
        """
        Train latent factors on interaction history using deterministic random initialization.
        """
        rng = np.random.RandomState(self.random_seed)
        users = sorted(list(set(i["user_id"] for i in interactions)))
        items = sorted(list(set(i["item_id"] for i in interactions)))

        # Deterministic initialization
        for u in users:
            self.user_embeddings[u] = rng.normal(0, 0.1, self.n_factors)
        for i in items:
            self.item_embeddings[i] = rng.normal(0, 0.1, self.n_factors)

        # Optimization epochs
        for _ in range(15):
            for row in interactions:
                u = row["user_id"]
                i = row["item_id"]
                rating = float(row.get("rating", 1.0))

                u_vec = self.user_embeddings[u]
                i_vec = self.item_embeddings[i]

                pred = float(np.dot(u_vec, i_vec)) + self.bias
                err = rating - pred

                # Update gradients
                self.user_embeddings[u] += self.learning_rate * (err * i_vec - self.regularization * u_vec)
                self.item_embeddings[i] += self.learning_rate * (err * u_vec - self.regularization * i_vec)

    def predict_score(
        self,
        user_id: str,
        item_id: str,
        user_features: Dict[str, Any],
        item_features: Dict[str, Any],
        item_category: str = "general"
    ) -> float:
        """
        Compute deterministic recommendation score combining latent factors and point-in-time features.
        """
        # Latent factor base score
        if user_id in self.user_embeddings and item_id in self.item_embeddings:
            latent_score = float(np.dot(self.user_embeddings[user_id], self.item_embeddings[item_id]))
        else:
            latent_score = 0.2

        # Feature weighting
        user_eng = user_features.get("engagement_score", 0.5)
        item_pop = item_features.get("popularity_score", 0.5)
        user_pref_cat = user_features.get("preferred_category", "general")
        cat_multiplier = 1.3 if (user_pref_cat == item_category) else 1.0

        raw_score = (self.bias + (latent_score * 0.4) + (item_pop * 0.35) + (user_eng * 0.25)) * cat_multiplier
        # Sigmoid normalization between 0.0 and 1.0, rounded deterministically to 6 decimal places
        norm_score = 1.0 / (1.0 + np.exp(-raw_score))
        return round(float(norm_score), 6)

    def recommend(
        self,
        user_id: str,
        candidate_items: List[Dict[str, Any]],
        user_features: Dict[str, Any],
        item_features_map: Dict[str, Dict[str, Any]],
        top_k: int = 5
    ) -> Tuple[Dict[str, float], List[Dict[str, Any]]]:
        """Generate ranked recommendations."""
        scores: Dict[str, float] = {}
        for item in candidate_items:
            iid = item["item_id"]
            cat = item.get("category", "general")
            ifeats = item_features_map.get(iid, {})
            score = self.predict_score(user_id, iid, user_features, ifeats, cat)
            scores[iid] = score

        ranked = sorted(
            [{"item_id": iid, "score": sc, "name": next((x["name"] for x in candidate_items if x["item_id"] == iid), iid)}
             for iid, sc in scores.items()],
            key=lambda x: x["score"],
            reverse=True
        )[:top_k]

        return scores, ranked

    def save(self, filepath: Path) -> str:
        """Serialize model to disk and return its SHA-256 hash."""
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "wb") as f:
            pickle.dump({
                "n_factors": self.n_factors,
                "regularization": self.regularization,
                "learning_rate": self.learning_rate,
                "random_seed": self.random_seed,
                "user_embeddings": self.user_embeddings,
                "item_embeddings": self.item_embeddings,
                "category_weights": self.category_weights,
                "bias": self.bias
            }, f)

        hasher = hashlib.sha256()
        with open(filepath, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()

    @classmethod
    def load(cls, filepath: Path) -> "RecommenderModel":
        """Load serialized model artifact."""
        with open(filepath, "rb") as f:
            data = pickle.load(f)

        model = cls(
            n_factors=data["n_factors"],
            regularization=data["regularization"],
            learning_rate=data["learning_rate"],
            random_seed=data["random_seed"]
        )
        model.user_embeddings = data["user_embeddings"]
        model.item_embeddings = data["item_embeddings"]
        model.category_weights = data["category_weights"]
        model.bias = data["bias"]
        return model
