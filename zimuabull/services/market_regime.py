from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

import numpy as np
import pandas as pd

from zimuabull.models import MarketIndex, MarketIndexData, MarketRegime, Portfolio

ADX_PERIOD = 14
VOL_LOOKBACK = 20
PERCENTILE_LOOKBACK = 252

REGIME_CONFIG = {
    MarketRegime.RegimeChoices.BULL_TRENDING: {"max_positions": 6, "risk_per_trade": 0.02},
    MarketRegime.RegimeChoices.BEAR_TRENDING: {"max_positions": 2, "risk_per_trade": 0.01},
    MarketRegime.RegimeChoices.HIGH_VOL: {"max_positions": 2, "risk_per_trade": 0.008},
    MarketRegime.RegimeChoices.LOW_VOL: {"max_positions": 6, "risk_per_trade": 0.025},
    MarketRegime.RegimeChoices.RANGING: {"max_positions": 4, "risk_per_trade": 0.015},
}

EXCHANGE_INDEX_MAP = {
    "NASDAQ": "^IXIC",
    "NYSE": "^GSPC",
    "AMEX": "^GSPC",
    "NYSE ARCA": "^GSPC",
    "TSX": "^GSPTSE",
    "TSE": "^GSPTSE",
}

_INDEX_CACHE: dict[str, MarketIndex | None] = {}


@dataclass
class RegimeAdjustments:
    regime: Optional[str]
    max_positions: Optional[int]
    risk_per_trade: Optional[float]
    trend_strength: Optional[float]
    volatility_percentile: Optional[float]
    vix_level: Optional[float]


def calculate_market_regimes(
    index: MarketIndex,
    start_date: date,
    end_date: date,
) -> list[MarketRegime]:
    """Calculate regime records for the given market index and date range."""
    all_data = (
        MarketIndexData.objects.filter(
            index=index,
            date__gte=start_date - timedelta(days=PERCENTILE_LOOKBACK * 2),
            date__lte=end_date,
        )
        .order_by("date")
        .values("date", "high", "low", "close")
    )
    if not all_data:
        return []

    df = pd.DataFrame(all_data)
    df.set_index("date", inplace=True)

    adx_series = _compute_adx(df)
    vol_percentile_series = _compute_volatility_percentile(df["close"])
    slope_series = df["close"].pct_change(VOL_LOOKBACK)

    vix_index = MarketIndex.objects.filter(symbol="^VIX").first()
    vix_map: dict[date, float] = {}
    if vix_index:
        vix_records = MarketIndexData.objects.filter(
            index=vix_index,
            date__gte=start_date - timedelta(days=5),
            date__lte=end_date,
        ).values("date", "close")
        vix_map = {record["date"]: record["close"] for record in vix_records}

    regimes: list[MarketRegime] = []

    for current_date in pd.date_range(start=start_date, end=end_date, freq="D"):
        current_date = current_date.date()
        if current_date not in adx_series.index or current_date not in vol_percentile_series.index:
            continue

        trend_strength = float(adx_series.loc[current_date])
        volatility_percentile = float(vol_percentile_series.loc[current_date])
        slope = float(slope_series.loc[current_date]) if current_date in slope_series.index else 0.0

        regime = _classify_regime(trend_strength, volatility_percentile, slope)
        adjustments = REGIME_CONFIG[regime]

        regime_obj, _ = MarketRegime.objects.update_or_create(
            index=index,
            date=current_date,
            defaults={
                "regime": regime,
                "vix_level": vix_map.get(current_date),
                "trend_strength": trend_strength,
                "volatility_percentile": volatility_percentile,
                "recommended_max_positions": adjustments["max_positions"],
                "recommended_risk_per_trade": adjustments["risk_per_trade"],
            },
        )
        regimes.append(regime_obj)

    return regimes


def get_market_index_for_exchange(exchange_code: str | None) -> MarketIndex | None:
    """Return the benchmark index for a given exchange code."""
    if not exchange_code:
        symbol = "^GSPC"
    else:
        symbol = EXCHANGE_INDEX_MAP.get(exchange_code.upper(), "^GSPC")

    if symbol not in _INDEX_CACHE:
        _INDEX_CACHE[symbol] = MarketIndex.objects.filter(symbol=symbol).first()
    return _INDEX_CACHE[symbol]


def get_regime_adjustments_for_portfolio(portfolio: Portfolio, trade_date: date) -> RegimeAdjustments:
    """Return regime adjustments for the portfolio's exchange on the given date."""
    market_index = get_market_index_for_exchange(portfolio.exchange.code if portfolio.exchange else None)
    if not market_index:
        return RegimeAdjustments(None, None, None, None, None, None)

    regime = MarketRegime.objects.filter(index=market_index, date=trade_date).first()
    if not regime:
        return RegimeAdjustments(None, None, None, None, None, None)

    return RegimeAdjustments(
        regime=regime.regime,
        max_positions=regime.recommended_max_positions,
        risk_per_trade=regime.recommended_risk_per_trade,
        trend_strength=regime.trend_strength,
        volatility_percentile=regime.volatility_percentile,
        vix_level=regime.vix_level,
    )


def _compute_adx(df: pd.DataFrame) -> pd.Series:
    """Compute Average Directional Index (ADX)."""
    high = df["high"]
    low = df["low"]
    close = df["close"]

    plus_dm = high.diff()
    minus_dm = low.diff() * -1

    plus_dm = np.where((plus_dm > minus_dm) & (plus_dm > 0), plus_dm, 0.0)
    minus_dm = np.where((minus_dm > plus_dm) & (minus_dm > 0), minus_dm, 0.0)

    tr_components = pd.concat(
        [
            high - low,
            (high - close.shift()).abs(),
            (low - close.shift()).abs(),
        ],
        axis=1,
    )
    true_range = tr_components.max(axis=1)

    atr = true_range.ewm(alpha=1 / ADX_PERIOD, adjust=False).mean()
    plus_di = 100 * pd.Series(plus_dm, index=close.index).ewm(alpha=1 / ADX_PERIOD, adjust=False).mean() / atr
    minus_di = 100 * pd.Series(minus_dm, index=close.index).ewm(alpha=1 / ADX_PERIOD, adjust=False).mean() / atr

    dx = (abs(plus_di - minus_di) / (plus_di + minus_di)) * 100
    adx = dx.ewm(alpha=1 / ADX_PERIOD, adjust=False).mean()
    return adx.fillna(method="bfill").fillna(0.0)


def _compute_volatility_percentile(close: pd.Series) -> pd.Series:
    returns = close.pct_change().fillna(0.0)
    rolling_vol = returns.rolling(window=VOL_LOOKBACK).std()

    vol_percentiles = rolling_vol.rolling(window=PERCENTILE_LOOKBACK).apply(
        lambda x: 100 * pd.Series(x).rank(pct=True).iloc[-1] if len(x.dropna()) else np.nan,
        raw=False,
    )
    return vol_percentiles.fillna(method="bfill").fillna(0.0)


def _classify_regime(adx: float, volatility_percentile: float, slope: float) -> MarketRegime.RegimeChoices:
    if volatility_percentile >= 85:
        return MarketRegime.RegimeChoices.HIGH_VOL
    if volatility_percentile <= 15 and adx < 20:
        return MarketRegime.RegimeChoices.LOW_VOL

    if adx >= 25:
        if slope >= 0:
            return MarketRegime.RegimeChoices.BULL_TRENDING
        return MarketRegime.RegimeChoices.BEAR_TRENDING

    return MarketRegime.RegimeChoices.RANGING
