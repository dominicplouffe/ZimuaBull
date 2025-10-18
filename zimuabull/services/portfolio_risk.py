from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np

from zimuabull.models import (
    DaySymbol,
    MarketIndex,
    MarketIndexData,
    Portfolio,
    PortfolioRiskMetrics,
    PortfolioSnapshot,
    PortfolioTransaction,
)

TRADING_DAYS_PER_YEAR = 252


@dataclass
class HoldingExposure:
    symbol_id: int
    market_value: float
    sector: str | None


def upsert_portfolio_risk_metrics(portfolio: Portfolio, as_of_date: date) -> Optional[PortfolioRiskMetrics]:
    """
    Calculate and persist risk metrics for the provided portfolio/date pair.

    Returns the PortfolioRiskMetrics instance if one could be created, otherwise None.
    """
    metrics = _calculate_portfolio_risk_metrics(portfolio, as_of_date)
    if metrics is None:
        return None

    instance, _ = PortfolioRiskMetrics.objects.update_or_create(
        portfolio=portfolio,
        date=as_of_date,
        defaults=metrics,
    )
    return instance


def _calculate_portfolio_risk_metrics(portfolio: Portfolio, as_of_date: date) -> Optional[Dict[str, object]]:
    snapshots = list(
        PortfolioSnapshot.objects.filter(
            portfolio=portfolio,
            date__lte=as_of_date,
        ).order_by("date")
    )

    if len(snapshots) < 1:
        return None

    equity_values = np.array([float(snapshot.total_value) for snapshot in snapshots], dtype=float)
    if equity_values.size == 0 or np.count_nonzero(equity_values) == 0:
        return None

    portfolio_returns = _compute_portfolio_returns(equity_values)
    as_of_snapshot = snapshots[-1]
    portfolio_value = float(as_of_snapshot.total_value)

    sharpe = _safe_sharpe_ratio(portfolio_returns)
    sortino = _safe_sortino_ratio(portfolio_returns)
    volatility = _annualized_volatility(portfolio_returns)
    max_drawdown = _max_drawdown(equity_values)
    calmar = _calmar_ratio(portfolio_returns, max_drawdown)
    beta, information_ratio = _relative_metrics(snapshots, portfolio_returns)

    exposures = _holding_exposures(portfolio, as_of_date)
    largest_position_pct, sector_concentration = _concentration_metrics(exposures, portfolio_value)

    return {
        "sharpe_ratio": sharpe,
        "sortino_ratio": sortino,
        "max_drawdown": max_drawdown,
        "volatility": volatility,
        "beta": beta,
        "largest_position_pct": largest_position_pct,
        "sector_concentration": sector_concentration,
        "calmar_ratio": calmar,
        "information_ratio": information_ratio,
    }


def _compute_portfolio_returns(equity_values: np.ndarray) -> np.ndarray:
    if equity_values.size < 2:
        return np.array([], dtype=float)

    previous_values = equity_values[:-1]
    returns = np.divide(
        equity_values[1:] - previous_values,
        previous_values,
        out=np.zeros_like(previous_values, dtype=float),
        where=previous_values != 0,
    )
    return returns


def _safe_sharpe_ratio(returns: np.ndarray) -> Optional[float]:
    if returns.size == 0:
        return None

    std = returns.std(ddof=0)
    if std == 0:
        return None

    sharpe = (returns.mean() / std) * np.sqrt(TRADING_DAYS_PER_YEAR)
    return float(sharpe)


def _safe_sortino_ratio(returns: np.ndarray) -> Optional[float]:
    if returns.size == 0:
        return None

    downside = returns[returns < 0]
    if downside.size == 0:
        return None

    downside_deviation = np.sqrt(np.mean(np.square(downside)))
    if downside_deviation == 0:
        return None

    sortino = (returns.mean() * TRADING_DAYS_PER_YEAR) / (downside_deviation * np.sqrt(TRADING_DAYS_PER_YEAR))
    return float(sortino)


def _annualized_volatility(returns: np.ndarray) -> Optional[float]:
    if returns.size == 0:
        return None

    std = returns.std(ddof=0)
    if std == 0:
        return 0.0

    return float(std * np.sqrt(TRADING_DAYS_PER_YEAR))


def _max_drawdown(equity_values: np.ndarray) -> Optional[float]:
    if equity_values.size == 0:
        return None

    cumulative_max = np.maximum.accumulate(equity_values)
    drawdowns = (equity_values / cumulative_max) - 1
    return float(abs(drawdowns.min()))


def _calmar_ratio(returns: np.ndarray, max_drawdown: Optional[float]) -> Optional[float]:
    if returns.size == 0 or not max_drawdown or max_drawdown == 0:
        return None

    cumulative_return = np.prod(1 + returns) - 1
    annualized_return = (1 + cumulative_return) ** (TRADING_DAYS_PER_YEAR / returns.size) - 1
    if max_drawdown == 0:
        return None
    return float(annualized_return / max_drawdown)


def _relative_metrics(
    snapshots: List[PortfolioSnapshot],
    portfolio_returns: np.ndarray,
) -> Tuple[Optional[float], Optional[float]]:
    if portfolio_returns.size == 0:
        return (None, None)

    benchmark_prices = _benchmark_prices_for_dates([snapshot.date for snapshot in snapshots])
    if benchmark_prices is None:
        return (None, None)

    aligned_portfolio_returns: List[float] = []
    aligned_benchmark_returns: List[float] = []

    for idx in range(1, len(snapshots)):
        bench_today = benchmark_prices[idx]
        bench_prev = benchmark_prices[idx - 1]
        if bench_today is None or bench_prev is None or bench_prev == 0:
            continue

        aligned_portfolio_returns.append(float(portfolio_returns[idx - 1]))
        aligned_benchmark_returns.append((bench_today - bench_prev) / bench_prev)

    if len(aligned_benchmark_returns) < 2:
        return (None, None)

    bench_array = np.array(aligned_benchmark_returns, dtype=float)
    port_array = np.array(aligned_portfolio_returns, dtype=float)

    bench_variance = bench_array.var(ddof=0)
    if bench_variance == 0:
        beta = None
    else:
        covariance = np.cov(port_array, bench_array, ddof=0)[0, 1]
        beta = float(covariance / bench_variance)

    tracking_error = (port_array - bench_array).std(ddof=0)
    if tracking_error == 0:
        information_ratio = None
    else:
        mean_excess = (port_array - bench_array).mean()
        information_ratio = float(
            (mean_excess * TRADING_DAYS_PER_YEAR) / (tracking_error * np.sqrt(TRADING_DAYS_PER_YEAR))
        )

    return beta, information_ratio


def _benchmark_prices_for_dates(dates: List[date]) -> Optional[List[Optional[float]]]:
    if not dates:
        return None

    index = _select_benchmark_index()
    if index is None:
        return None

    start_date = dates[0]
    end_date = dates[-1]
    records = (
        MarketIndexData.objects.filter(index=index, date__range=(start_date, end_date))
        .order_by("date")
        .values_list("date", "close")
    )
    price_map = {record_date: close for record_date, close in records}

    prices: List[Optional[float]] = []
    last_price: Optional[float] = None

    for target_date in dates:
        if target_date in price_map:
            last_price = float(price_map[target_date])
        prices.append(last_price)

    return prices


def _select_benchmark_index() -> Optional[MarketIndex]:
    preferred = MarketIndex.objects.filter(symbol="^GSPC").first()
    if preferred:
        return preferred
    return MarketIndex.objects.order_by("id").first()


def _holding_exposures(portfolio: Portfolio, snapshot_date: date) -> List[HoldingExposure]:
    transactions = PortfolioTransaction.objects.filter(
        portfolio=portfolio,
        transaction_date__lte=snapshot_date,
    ).order_by("transaction_date", "created_at")

    if not transactions.exists():
        return []

    holdings: Dict[int, Dict[str, Decimal]] = {}

    for txn in transactions:
        if txn.transaction_type == "DEPOSIT":
            continue
        if txn.transaction_type == "WITHDRAWAL":
            continue
        if txn.symbol_id is None:
            continue

        symbol_id = txn.symbol_id
        if symbol_id not in holdings:
            holdings[symbol_id] = {
                "symbol": txn.symbol,
                "quantity": Decimal("0"),
                "total_cost": Decimal("0"),
            }

        record = holdings[symbol_id]

        if txn.transaction_type == "BUY":
            quantity = Decimal(txn.quantity)
            record["quantity"] += quantity
            record["total_cost"] += Decimal(txn.quantity * txn.price)
        elif txn.transaction_type == "SELL":
            quantity = Decimal(txn.quantity)
            if record["quantity"] > 0:
                cost_per_share = record["total_cost"] / record["quantity"]
                record["quantity"] -= quantity
                record["total_cost"] -= cost_per_share * quantity
                if record["quantity"] <= 0:
                    record["quantity"] = Decimal("0")
                    record["total_cost"] = Decimal("0")

    exposures: List[HoldingExposure] = []
    for symbol_id, record in holdings.items():
        if record["quantity"] <= 0:
            continue

        symbol = record["symbol"]
        price = _get_symbol_price_at_date(symbol, snapshot_date)
        if price is None:
            continue

        market_value = float(Decimal(price) * record["quantity"])
        exposures.append(
            HoldingExposure(
                symbol_id=symbol_id,
                market_value=market_value,
                sector=symbol.sector,
            )
        )

    return exposures


def _get_symbol_price_at_date(symbol, snapshot_date: date) -> Optional[Decimal]:
    day_symbol = DaySymbol.objects.filter(symbol=symbol, date=snapshot_date).first()
    if day_symbol:
        return Decimal(str(day_symbol.close))

    day_symbol = (
        DaySymbol.objects.filter(symbol=symbol, date__lt=snapshot_date)
        .order_by("-date")
        .first()
    )
    if day_symbol:
        return Decimal(str(day_symbol.close))

    if symbol.latest_price:
        return Decimal(str(symbol.latest_price))
    if symbol.last_close:
        return Decimal(str(symbol.last_close))
    return None


def _concentration_metrics(
    exposures: Iterable[HoldingExposure],
    portfolio_value: float,
) -> Tuple[float, Dict[str, float]]:
    if portfolio_value <= 0:
        return 0.0, {}

    exposures = list(exposures)
    if not exposures:
        return 0.0, {}

    max_position = max(exposures, key=lambda exposure: exposure.market_value)
    largest_position_pct = (max_position.market_value / portfolio_value) * 100

    sector_totals: Dict[str, float] = defaultdict(float)
    for exposure in exposures:
        sector_name = exposure.sector or "Unknown"
        sector_totals[sector_name] += exposure.market_value

    sector_concentration = {
        sector: round((value / portfolio_value) * 100, 4)
        for sector, value in sector_totals.items()
        if portfolio_value > 0
    }

    return float(round(largest_position_pct, 4)), sector_concentration
