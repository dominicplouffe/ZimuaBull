import math
from datetime import date, timedelta
from decimal import Decimal
from typing import Dict, Iterable, Optional, Tuple

import pandas as pd
from zimuabull.models import DaySymbol, FeatureSnapshot, Symbol
from .constants import (
    ATR_WINDOW,
    FEATURE_VERSION,
    LOOKBACK_WINDOWS,
    MIN_HISTORY_DAYS,
    VOLUME_WINDOWS,
)


def _encode_close_bucket(bucket: Optional[str]) -> int:
    if bucket == "UP":
        return 1
    if bucket == "DOWN":
        return -1
    return 0


def _obv_status_to_numeric(status: Optional[str]) -> int:
    mapping = {
        "STRONG_BUY": 2,
        "BUY": 1,
        "HOLD": 0,
        "SELL": -1,
        "STRONG_SELL": -2,
    }
    return mapping.get(status or "HOLD", 0)


def _compute_atr(df: pd.DataFrame, window: int) -> float:
    highs = df["high"]
    lows = df["low"]
    closes = df["close"]
    prev_closes = closes.shift(1)

    tr1 = highs - lows
    tr2 = (highs - prev_closes).abs()
    tr3 = (lows - prev_closes).abs()
    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = true_range.rolling(window=window).mean()
    return float(atr.iloc[-1]) if not math.isnan(atr.iloc[-1]) else float("nan")


def _safe_percent(a: float, b: float) -> float:
    if b == 0 or b is None:
        return float("nan")
    return (a - b) / b


def _history_dataframe(symbol: Symbol, end_date: date, limit: int) -> pd.DataFrame:
    qs = DaySymbol.objects.filter(symbol=symbol, date__lt=end_date).order_by("-date")[:limit]
    records = list(
        qs.values(
            "date",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "obv",
            "obv_signal",
            "obv_signal_sum",
            "price_diff",
            "thirty_price_diff",
            "thirty_close_trend",
            "rsi",
            "macd",
            "macd_signal",
            "macd_histogram",
        )
    )
    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)
    df = df.sort_values("date")
    df.set_index("date", inplace=True)
    return df


def compute_feature_row(symbol: Symbol, trade_date: date) -> Optional[Dict]:
    """
    Build a feature dictionary for `symbol` on `trade_date`.
    Utilises data strictly prior to `trade_date` to avoid look-ahead bias.
    """
    history_limit = max(MIN_HISTORY_DAYS + ATR_WINDOW + 5, 80)
    hist_df = _history_dataframe(symbol, trade_date, history_limit)
    if hist_df.empty or len(hist_df) < MIN_HISTORY_DAYS:
        return None

    latest = hist_df.iloc[-1]
    closes = hist_df["close"]
    returns = closes.pct_change()
    volumes = hist_df["volume"]

    def sanitize(value: float) -> Optional[float]:
        if value is None:
            return None
        if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            return None
        return float(value)

    features: Dict[str, Optional[float]] = {}

    for window in LOOKBACK_WINDOWS:
        if len(returns) >= window + 1:
            features[f"return_{window}d"] = sanitize(returns.iloc[-window:].sum())
            features[f"momentum_{window}d"] = sanitize((closes.iloc[-1] / closes.iloc[-window]) - 1)
        else:
            features[f"return_{window}d"] = None
            features[f"momentum_{window}d"] = None

    for window in VOLUME_WINDOWS:
        if len(volumes) >= window:
            avg_vol = volumes.iloc[-window:].mean()
            features[f"avg_volume_{window}d"] = sanitize(avg_vol)
            features[f"volume_ratio_{window}d"] = sanitize(latest["volume"] / avg_vol) if avg_vol else None
            avg_dollar = (hist_df["close"].iloc[-window:] * volumes.iloc[-window:]).mean()
            features[f"dollar_volume_avg_{window}d"] = sanitize(avg_dollar)
        else:
            features[f"avg_volume_{window}d"] = None
            features[f"volume_ratio_{window}d"] = None
            features[f"dollar_volume_avg_{window}d"] = None

    if len(returns) >= 2:
        features["volatility_10d"] = sanitize(returns.iloc[-10:].std()) if len(returns) >= 10 else None
        features["volatility_20d"] = sanitize(returns.iloc[-20:].std()) if len(returns) >= 20 else None
    else:
        features["volatility_10d"] = None
        features["volatility_20d"] = None

    atr = _compute_atr(hist_df, ATR_WINDOW)
    features["atr_14"] = sanitize(atr)

    features["thirty_day_trend"] = sanitize(latest.get("thirty_close_trend", None))
    features["obv_signal_sum"] = sanitize(latest.get("obv_signal_sum", 0))
    features["obv_status_num"] = sanitize(_obv_status_to_numeric(symbol.obv_status))
    features["close_bucket_num"] = sanitize(_encode_close_bucket(symbol.close_bucket))
    features["symbol_accuracy"] = sanitize(symbol.accuracy or 0.0)
    features["rsi"] = sanitize(latest.get("rsi", None))
    features["macd"] = sanitize(latest.get("macd", None))
    features["macd_signal"] = sanitize(latest.get("macd_signal", None))
    features["macd_histogram"] = sanitize(latest.get("macd_histogram", None))

    # price relatives
    features["price_relative_5d"] = sanitize(hist_df["close"].iloc[-1] / hist_df["close"].iloc[-5] - 1) if len(hist_df) >= 5 else None
    features["price_relative_20d"] = sanitize(hist_df["close"].iloc[-1] / hist_df["close"].iloc[-20] - 1) if len(hist_df) >= 20 else None

    return {
        "features": features,
        "previous_close": sanitize(latest["close"]),
    }


def _compute_labels(symbol: Symbol, trade_day: DaySymbol) -> Dict:
    open_price = float(trade_day.open)
    close_price = float(trade_day.close)
    high_price = float(trade_day.high)
    low_price = float(trade_day.low)

    intraday_return = _safe_percent(close_price, open_price)
    max_favorable = _safe_percent(high_price, open_price)
    max_adverse = _safe_percent(low_price, open_price)

    return {
        "open_price": open_price,
        "close_price": close_price,
        "high_price": high_price,
        "low_price": low_price,
        "intraday_return": intraday_return,
        "max_favorable_excursion": max_favorable,
        "max_adverse_excursion": max_adverse,
        "label_ready": True,
    }


def build_feature_snapshot(symbol: Symbol, trade_date: date, overwrite: bool = False) -> Optional[FeatureSnapshot]:
    """
    Create or update a FeatureSnapshot for the given symbol/date.
    """
    feature_payload = compute_feature_row(symbol, trade_date)
    if feature_payload is None:
        return None

    feature_defaults = {
        "features": feature_payload["features"],
        "previous_close": feature_payload["previous_close"],
        "feature_version": FEATURE_VERSION,
    }

    trade_day = DaySymbol.objects.filter(symbol=symbol, date=trade_date).first()
    if trade_day:
        feature_defaults.update(_compute_labels(symbol, trade_day))

    snapshot, created = FeatureSnapshot.objects.get_or_create(
        symbol=symbol,
        trade_date=trade_date,
        feature_version=FEATURE_VERSION,
        defaults=feature_defaults,
    )

    if not created and overwrite:
        for key, value in feature_defaults.items():
            setattr(snapshot, key, value)
        snapshot.save()

    return snapshot


def build_features_for_date(trade_date: date, symbols: Optional[Iterable[Symbol]] = None, overwrite: bool = False) -> int:
    """
    Generate feature snapshots for all provided symbols on the given trade_date.
    Returns the number of snapshots created/updated.
    """
    if symbols is None:
        symbols = Symbol.objects.all()

    processed = 0
    for symbol in symbols:
        snapshot = build_feature_snapshot(symbol, trade_date, overwrite=overwrite)
        if snapshot:
            processed += 1
    return processed


def backfill_features(
    start_date: date,
    end_date: Optional[date] = None,
    symbols: Optional[Iterable[Symbol]] = None,
    overwrite: bool = False,
) -> int:
    """
    Backfill features between start_date and end_date (inclusive).
    Returns number of snapshots processed.
    """
    if end_date is None:
        end_date = date.today()

    if symbols is None:
        symbols = Symbol.objects.all()

    total_processed = 0
    for day in pd.date_range(start=start_date, end=end_date, freq="D"):
        current_date = day.date()
        if current_date.weekday() >= 5:
            continue  # skip weekends
        for symbol in symbols:
            snapshot = build_feature_snapshot(symbol, current_date, overwrite=overwrite)
            if snapshot:
                total_processed += 1
    return total_processed


def update_labels_for_date(trade_date: date, symbols: Optional[Iterable[Symbol]] = None) -> int:
    """
    Populate label fields for FeatureSnapshots on the given trade_date
    using finalized DaySymbol data.
    """
    if symbols is None:
        snapshots = FeatureSnapshot.objects.filter(trade_date=trade_date, feature_version=FEATURE_VERSION).select_related("symbol")
    else:
        symbol_ids = [symbol.id for symbol in symbols]
        snapshots = FeatureSnapshot.objects.filter(
            trade_date=trade_date,
            feature_version=FEATURE_VERSION,
            symbol_id__in=symbol_ids,
        ).select_related("symbol")

    updated = 0
    for snapshot in snapshots:
        trade_day = DaySymbol.objects.filter(symbol=snapshot.symbol, date=trade_date).first()
        if not trade_day:
            continue

        labels = _compute_labels(snapshot.symbol, trade_day)

        def _to_decimal(value: Optional[float], quant: str = "0.0001") -> Optional[Decimal]:
            if value is None:
                return None
            return Decimal(str(value)).quantize(Decimal(quant))

        snapshot.open_price = _to_decimal(labels.get("open_price"))
        snapshot.close_price = _to_decimal(labels.get("close_price"))
        snapshot.high_price = _to_decimal(labels.get("high_price"))
        snapshot.low_price = _to_decimal(labels.get("low_price"))
        snapshot.intraday_return = _to_decimal(labels.get("intraday_return"))
        snapshot.max_favorable_excursion = _to_decimal(labels.get("max_favorable_excursion"))
        snapshot.max_adverse_excursion = _to_decimal(labels.get("max_adverse_excursion"))
        snapshot.label_ready = labels.get("label_ready", True)
        snapshot.save(update_fields=[
            "open_price",
            "close_price",
            "high_price",
            "low_price",
            "intraday_return",
            "max_favorable_excursion",
            "max_adverse_excursion",
            "label_ready",
            "updated_at",
        ])
        updated += 1

    return updated
