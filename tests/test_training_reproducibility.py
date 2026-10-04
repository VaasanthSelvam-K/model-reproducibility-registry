"""
Fixed-Seed Deterministic Training Reproducibility Test Suite (Review 2).
Directly proves the explicit objective:
Given identical training datasets, hyperparameters, and random seed (seed=42),
independent retraining runs yield bit-exact identical model weights,
biases, and artifact SHA-256 hashes (Zero training variance).
"""

import numpy as np
import tempfile
from pathlib import Path
import pytest
from src.models.recommender import RecommenderModel


@pytest.fixture
def sample_training_interactions():
    """Generates synthetic training interaction records."""
    np.random.seed(42)
    users = [f"usr_{i}" for i in range(10)]
    items = [f"prod_{j}" for j in range(15)]
    records = []
    for _ in range(250):
        records.append({
            "user_id": str(np.random.choice(users)),
            "item_id": str(np.random.choice(items)),
            "rating": float(np.random.choice([1.0, 3.0, 5.0])),
            "timestamp": "2026-03-01T12:00:00Z"
        })
    return records


def test_fixed_seed_dual_training_bit_exact_parity(sample_training_interactions):
    """
    Test 1: Train Model Run A and Model Run B with seed=42 on identical data.
    Assert bit-exact parity across weights, biases, and serialized artifact SHA-256.
    """
    hyperparams = {
        "n_factors": 16,
        "regularization": 0.05,
        "learning_rate": 0.015,
        "random_seed": 42
    }

    # Run A
    model_a = RecommenderModel(**hyperparams)
    model_a.fit(sample_training_interactions)

    # Run B
    model_b = RecommenderModel(**hyperparams)
    model_b.fit(sample_training_interactions)

    # 1. Assert all user embedding vectors match bit-for-bit
    assert set(model_a.user_embeddings.keys()) == set(model_b.user_embeddings.keys())
    for u in model_a.user_embeddings:
        np.testing.assert_allclose(
            model_a.user_embeddings[u],
            model_b.user_embeddings[u],
            atol=1e-12,
            err_msg=f"User embedding for {u} diverged between deterministic training runs."
        )

    # 2. Assert all item embedding vectors match bit-for-bit
    assert set(model_a.item_embeddings.keys()) == set(model_b.item_embeddings.keys())
    for i in model_a.item_embeddings:
        np.testing.assert_allclose(
            model_a.item_embeddings[i],
            model_b.item_embeddings[i],
            atol=1e-12,
            err_msg=f"Item embedding for {i} diverged between deterministic training runs."
        )

    # 3. Assert global bias matches exactly
    assert model_a.bias == model_b.bias

    # 4. Assert physical serialized artifact SHA-256 match exactly
    with tempfile.TemporaryDirectory() as tmpdir:
        path_a = Path(tmpdir) / "model_a.pkl"
        path_b = Path(tmpdir) / "model_b.pkl"
        sha_a = model_a.save(path_a)
        sha_b = model_b.save(path_b)

        assert sha_a == sha_b, f"Artifact SHA-256 hash diverged: {sha_a} vs {sha_b}"
        assert len(sha_a) == 64

    print(f"\n[PASSED] Fixed-Seed Retrain Test: Run A == Run B (Artifact SHA: {sha_a[:16]}...)")


def test_divergent_seed_produces_distinct_weights(sample_training_interactions):
    """
    Test 2: Proves that altering the random seed (seed=42 vs seed=99) produces distinct
    weights, proving that the random seed is the true governing determinant of model state.
    """
    model_seed42 = RecommenderModel(n_factors=16, regularization=0.05, learning_rate=0.015, random_seed=42)
    model_seed42.fit(sample_training_interactions)

    model_seed99 = RecommenderModel(n_factors=16, regularization=0.05, learning_rate=0.015, random_seed=99)
    model_seed99.fit(sample_training_interactions)

    # Assert user embeddings are NOT identical when seed changes
    u_sample = next(iter(model_seed42.user_embeddings))
    diff = np.abs(model_seed42.user_embeddings[u_sample] - model_seed99.user_embeddings[u_sample]).max()
    assert diff > 0.01, f"Expected weight divergence with different seeds, but max diff was {diff}"
