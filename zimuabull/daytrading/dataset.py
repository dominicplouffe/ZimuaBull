from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

import pandas as pd

from zimuabull.models import FeatureSnapshot

from .constants import FEATURE_VERSION, TARGET_COLUMN


@dataclass
class Dataset:
    features: pd.DataFrame
    targets: pd.Series
    metadata: pd.DataFrame


def load_snapshots(
    start_date: date | None = None,
    end_date: date | None = None,
    feature_version: str = FEATURE_VERSION,
    require_labels: bool = True,
) -> list[FeatureSnapshot]:
    qs = FeatureSnapshot.objects.filter(feature_version=feature_version)
    if start_date:
        qs = qs.filter(trade_date__gte=start_date)
    if end_date:
        qs = qs.filter(trade_date__lte=end_date)
    if require_labels:
        qs = qs.filter(label_ready=True)

    return list(qs.select_related("symbol", "symbol__exchange"))


def build_dataset(
    snapshots: Sequence[FeatureSnapshot],
    drop_na: bool = True,
    min_non_na: float = 0.8,
) -> Dataset:
    rows = []
    meta_rows = []

    for snap in snapshots:
        feature_row = dict(snap.features)
        feature_row["previous_close"] = float(snap.previous_close or 0)
        feature_row["exchange_code"] = snap.symbol.exchange.code
        feature_row["symbol_accuracy"] = float(feature_row.get("symbol_accuracy", snap.symbol.accuracy or 0))
        rows.append(feature_row)

        meta_rows.append(
            {
                "symbol": snap.symbol.symbol,
                "exchange": snap.symbol.exchange.code,
                "trade_date": snap.trade_date,
                "intraday_return": float(snap.intraday_return) if snap.intraday_return is not None else None,
                "max_favorable_excursion": float(snap.max_favorable_excursion) if snap.max_favorable_excursion is not None else None,
                "max_adverse_excursion": float(snap.max_adverse_excursion) if snap.max_adverse_excursion is not None else None,
            }
        )

    features_df = pd.DataFrame(rows)
    metadata_df = pd.DataFrame(meta_rows)

    if TARGET_COLUMN in features_df.columns:
        msg = f"Feature column {TARGET_COLUMN} should not exist in features dictionary"
        raise ValueError(msg)

    targets = metadata_df[TARGET_COLUMN] if TARGET_COLUMN in metadata_df else metadata_df["intraday_return"]

    if drop_na:
        na_threshold = int(len(features_df.columns) * min_non_na)
        features_df = features_df.dropna(thresh=na_threshold)
        targets = targets.loc[features_df.index]
        metadata_df = metadata_df.loc[features_df.index]
        features_df = features_df.fillna(features_df.median(numeric_only=True))

    return Dataset(features=features_df, targets=targets, metadata=metadata_df)


def load_dataset(
    start_date: date | None = None,
    end_date: date | None = None,
    feature_version: str = FEATURE_VERSION,
    require_labels: bool = True,
    drop_na: bool = True,
    min_non_na: float = 0.8,
) -> Dataset:
    snapshots = load_snapshots(start_date=start_date, end_date=end_date, feature_version=feature_version, require_labels=require_labels)
    return build_dataset(snapshots, drop_na=drop_na, min_non_na=min_non_na)
