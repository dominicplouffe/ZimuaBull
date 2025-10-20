from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.ensemble import (
    GradientBoostingRegressor,
    HistGradientBoostingRegressor,
    RandomForestRegressor,
    VotingRegressor,
)
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import RandomizedSearchCV, TimeSeriesSplit

from .dataset import Dataset
from .modeling import _encode_features  # pylint: disable=protected-access


@dataclass
class EnsembleTrainingResult:
    model: VotingRegressor
    metrics: Dict[str, float]
    feature_columns: pd.Index
    imputer: SimpleImputer
    base_models: Dict[str, dict]


def train_ensemble_model(
    dataset: Dataset,
    *,
    perform_search: bool = True,
    n_iter: int = 20,
    random_state: int = 42,
) -> Tuple[VotingRegressor, dict, pd.Index, SimpleImputer]:
    """Train an ensemble model with optional hyperparameter optimisation."""
    features = _encode_features(dataset.features.copy())
    targets = dataset.targets.values

    if len(features) < 200:
        raise ValueError("Ensemble training requires at least 200 samples.")

    imputer = SimpleImputer(strategy="median")
    features_filled = pd.DataFrame(
        imputer.fit_transform(features),
        columns=features.columns,
        index=features.index,
    )

    tscv = TimeSeriesSplit(
        n_splits=min(5, max(2, len(features_filled) // 200)),
    )

    base_models = {
        "hgb": (
            HistGradientBoostingRegressor(random_state=random_state),
            {
                "max_depth": [5, 7, 9],
                "learning_rate": [0.03, 0.05, 0.08],
                "min_samples_leaf": [10, 20, 30],
                "l2_regularization": [0.0, 0.5, 1.0],
            },
        ),
        "rf": (
            RandomForestRegressor(random_state=random_state, n_jobs=-1),
            {
                "n_estimators": [200, 400, 600],
                "max_depth": [6, 8, 10, None],
                "min_samples_split": [2, 5, 10],
            },
        ),
        "gbr": (
            GradientBoostingRegressor(random_state=random_state),
            {
                "n_estimators": [200, 400, 600],
                "learning_rate": [0.03, 0.05, 0.08],
                "max_depth": [3, 4, 5],
                "subsample": [0.75, 0.9, 1.0],
            },
        ),
    }

    tuned_estimators: Dict[str, dict] = {}
    estimators_for_ensemble = []
    X = features_filled.values
    y = targets

    for name, (model, param_distributions) in base_models.items():
        if perform_search:
            search = RandomizedSearchCV(
                estimator=model,
                param_distributions=param_distributions,
                n_iter=min(n_iter, len(param_distributions["max_depth"]) * 3),
                scoring="neg_mean_absolute_error",
                cv=tscv,
                n_jobs=-1,
                random_state=random_state,
                verbose=0,
            )
            search.fit(X, y)
            best_model = search.best_estimator_
            tuned_estimators[name] = search.best_params_
        else:
            model.fit(X, y)
            best_model = model
            tuned_estimators[name] = model.get_params()

        estimators_for_ensemble.append((name, best_model))

    ensemble = VotingRegressor(estimators=estimators_for_ensemble, n_jobs=-1)
    ensemble.fit(X, y)

    cv_r2_scores = []
    cv_mae_scores = []

    for train_idx, test_idx in tscv.split(X):
        X_train, X_test = X[train_idx], X[test_idx]
        y_train, y_test = y[train_idx], y[test_idx]

        fold_estimators = [
            (name, clone(estimator)) for name, estimator in estimators_for_ensemble
        ]
        fold_model = VotingRegressor(estimators=fold_estimators, n_jobs=-1)
        fold_model.fit(X_train, y_train)
        preds = fold_model.predict(X_test)
        cv_r2_scores.append(r2_score(y_test, preds))
        cv_mae_scores.append(mean_absolute_error(y_test, preds))

    metrics = {
        "r2_mean": float(np.mean(cv_r2_scores)),
        "r2_std": float(np.std(cv_r2_scores)),
        "mae_mean": float(np.mean(cv_mae_scores)),
        "mae_std": float(np.std(cv_mae_scores)),
        "n_samples": len(features_filled),
        "n_features": int(features_filled.shape[1]),
        "model_type": "EnsembleVotingRegressor",
    }

    metrics["base_models"] = tuned_estimators

    return ensemble, metrics, features_filled.columns, imputer
