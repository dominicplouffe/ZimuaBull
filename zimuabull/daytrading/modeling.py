from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import TimeSeriesSplit

from .constants import MODEL_DIR, TARGET_COLUMN, get_model_filename, get_model_metadata_filename
from .dataset import Dataset


def _encode_features(df: pd.DataFrame) -> pd.DataFrame:
    """Encode categorical features without data leakage."""
    categorical_columns = [col for col in df.columns if df[col].dtype == "object"]
    encoded = pd.get_dummies(df, columns=categorical_columns, drop_first=True)
    encoded = encoded.replace({np.inf: np.nan, -np.inf: np.nan})
    return encoded


def train_regression_model(dataset: Dataset, n_splits: int = 5) -> tuple[HistGradientBoostingRegressor, dict, pd.Index, SimpleImputer]:
    """
    Train improved regression model with proper cross-validation (no data leakage).

    Returns:
        model: Trained HistGradientBoostingRegressor
        metrics: Performance metrics dictionary
        feature_columns: Column names after encoding
        imputer: Fitted imputer for inference
    """
    # Encode categorical features once before splitting
    features = _encode_features(dataset.features.copy())
    targets = dataset.targets.values

    if len(features) < 100:
        msg = "Not enough samples to train the model (need at least 100)."
        raise ValueError(msg)

    # Initialize improved model with better hyperparameters
    model = HistGradientBoostingRegressor(
        random_state=42,
        max_iter=500,           # More trees
        max_depth=6,            # Deeper trees (2^6 = 64 leaf patterns)
        learning_rate=0.05,
        min_samples_leaf=20,    # Regularization
        max_bins=255,           # Faster training
        early_stopping=True,    # Prevent overfitting
        n_iter_no_change=20,
        validation_fraction=0.1,
        l2_regularization=1.0,  # L2 penalty
    )

    # Initialize imputer (will be fit on training data only)
    imputer = SimpleImputer(strategy="median")

    tscv = TimeSeriesSplit(n_splits=min(n_splits, max(2, len(features) // 100)))
    scores = []
    mae_scores = []

    # Cross-validation with proper imputation (no data leakage)
    for train_idx, test_idx in tscv.split(features):
        X_train = features.iloc[train_idx]
        X_test = features.iloc[test_idx]
        y_train, y_test = targets[train_idx], targets[test_idx]

        # Fit imputer ONLY on training data
        X_train_filled = pd.DataFrame(
            imputer.fit_transform(X_train),
            columns=X_train.columns,
            index=X_train.index
        )

        # Transform test data using training statistics
        X_test_filled = pd.DataFrame(
            imputer.transform(X_test),
            columns=X_test.columns,
            index=X_test.index
        )

        # Train and evaluate
        model.fit(X_train_filled, y_train)
        preds = model.predict(X_test_filled)
        scores.append(r2_score(y_test, preds))
        mae_scores.append(mean_absolute_error(y_test, preds))

    # Fit imputer and model on full dataset for production use
    features_filled = pd.DataFrame(
        imputer.fit_transform(features),
        columns=features.columns,
        index=features.index
    )
    model.fit(features_filled, targets)

    metrics = {
        "r2_mean": float(np.mean(scores)),
        "r2_std": float(np.std(scores)),
        "mae_mean": float(np.mean(mae_scores)),
        "mae_std": float(np.std(mae_scores)),
        "n_samples": len(features),
        "n_features": int(features.shape[1]),
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "model_type": "HistGradientBoostingRegressor",
    }

    return model, metrics, features.columns, imputer


def save_model(model: HistGradientBoostingRegressor, metrics: dict, feature_columns: pd.Index, imputer: SimpleImputer, version: str | None = None) -> Path:
    """Save trained model, imputer, and metadata to disk.

    Args:
        model: Trained model
        metrics: Training metrics dictionary
        feature_columns: Feature column names
        imputer: Fitted imputer
        version: Feature version (e.g., 'v2', 'v3'). Defaults to current FEATURE_VERSION.
    """
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    model_path = MODEL_DIR / get_model_filename(version)
    meta_path = MODEL_DIR / get_model_metadata_filename(version)

    payload = {
        "metrics": metrics,
        "feature_columns": list(feature_columns),
        "target": TARGET_COLUMN,
        "model_class": type(model).__name__,
    }

    # Save model, imputer, and feature columns together
    joblib.dump(
        {
            "model": model,
            "imputer": imputer,
            "feature_columns": feature_columns.tolist()
        },
        model_path
    )

    with meta_path.open("w") as meta_file:
        json.dump(payload, meta_file, indent=2)

    return model_path


def load_model(version: str | None = None):
    """Load trained model, imputer, and feature columns from disk.

    Args:
        version: Feature version (e.g., 'v2', 'v3'). Defaults to current FEATURE_VERSION.

    Returns:
        Tuple of (model, feature_columns, imputer)
    """
    model_path = MODEL_DIR / get_model_filename(version)
    if not model_path.exists():
        msg = f"Model file not found at {model_path}"
        raise FileNotFoundError(msg)
    payload = joblib.load(model_path)
    return payload["model"], payload["feature_columns"], payload["imputer"]


def prepare_features_for_inference(df: pd.DataFrame, trained_columns, imputer: SimpleImputer) -> pd.DataFrame:
    """Prepare features for prediction using saved preprocessing pipeline."""
    # Encode categorical features
    encoded = _encode_features(df.copy())

    # Add missing columns from training
    for col in trained_columns:
        if col not in encoded.columns:
            encoded[col] = 0

    # Select only trained columns in correct order
    encoded = encoded[trained_columns]

    # Apply imputation using training statistics
    encoded_filled = pd.DataFrame(
        imputer.transform(encoded),
        columns=encoded.columns,
        index=encoded.index
    )

    return encoded_filled


def analyze_feature_importance(model: HistGradientBoostingRegressor, feature_names: list) -> dict:
    """
    Analyze feature importance from trained model.

    Returns:
        Dictionary with top features and low-importance features
    """
    # HistGradientBoostingRegressor doesn't have feature_importances_
    # We'll use permutation importance instead
    print("Note: HistGradientBoostingRegressor doesn't provide built-in feature importance.")
    print("Run permutation importance separately if needed.")

    return {
        "message": "Use permutation_importance from sklearn.inspection for this model",
        "n_features": len(feature_names)
    }
