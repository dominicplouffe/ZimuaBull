from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import TimeSeriesSplit

from .constants import MODEL_DIR, MODEL_FILENAME, MODEL_METADATA_FILENAME, TARGET_COLUMN
from .dataset import Dataset


def _encode_features(df: pd.DataFrame) -> pd.DataFrame:
    categorical_columns = [col for col in df.columns if df[col].dtype == "object"]
    encoded = pd.get_dummies(df, columns=categorical_columns, drop_first=True)
    encoded = encoded.replace({np.inf: np.nan, -np.inf: np.nan})
    return encoded.fillna(encoded.median(numeric_only=True))


def train_regression_model(dataset: Dataset, n_splits: int = 5) -> tuple[GradientBoostingRegressor, dict, pd.Index]:
    features = _encode_features(dataset.features.copy())
    targets = dataset.targets.values

    if len(features) < 100:
        msg = "Not enough samples to train the model (need at least 100)."
        raise ValueError(msg)

    model = GradientBoostingRegressor(random_state=42, n_estimators=300, max_depth=3, learning_rate=0.05)

    tscv = TimeSeriesSplit(n_splits=min(n_splits, max(2, len(features) // 100)))
    scores = []
    mae_scores = []

    for train_idx, test_idx in tscv.split(features):
        X_train, X_test = features.iloc[train_idx], features.iloc[test_idx]
        y_train, y_test = targets[train_idx], targets[test_idx]
        model.fit(X_train, y_train)
        preds = model.predict(X_test)
        scores.append(r2_score(y_test, preds))
        mae_scores.append(mean_absolute_error(y_test, preds))

    # Fit on full dataset
    model.fit(features, targets)

    metrics = {
        "r2_mean": float(np.mean(scores)),
        "r2_std": float(np.std(scores)),
        "mae_mean": float(np.mean(mae_scores)),
        "mae_std": float(np.std(mae_scores)),
        "n_samples": len(features),
        "n_features": int(features.shape[1]),
        "trained_at": datetime.utcnow().isoformat() + "Z",
    }

    return model, metrics, features.columns


def save_model(model: GradientBoostingRegressor, metrics: dict, feature_columns: pd.Index) -> Path:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    model_path = MODEL_DIR / MODEL_FILENAME
    meta_path = MODEL_DIR / MODEL_METADATA_FILENAME

    payload = {
        "metrics": metrics,
        "feature_columns": list(feature_columns),
        "target": TARGET_COLUMN,
        "model_class": type(model).__name__,
    }

    joblib.dump({"model": model, "feature_columns": feature_columns.tolist()}, model_path)

    with meta_path.open("w") as meta_file:
        json.dump(payload, meta_file, indent=2)

    return model_path


def load_model():
    model_path = MODEL_DIR / MODEL_FILENAME
    if not model_path.exists():
        msg = f"Model file not found at {model_path}"
        raise FileNotFoundError(msg)
    payload = joblib.load(model_path)
    return payload["model"], payload["feature_columns"]


def prepare_features_for_inference(df: pd.DataFrame, trained_columns) -> pd.DataFrame:
    encoded = _encode_features(df.copy())
    for col in trained_columns:
        if col not in encoded.columns:
            encoded[col] = 0
    return encoded[trained_columns]
